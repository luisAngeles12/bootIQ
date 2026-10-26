"""Auditoría económica PASIVA de estrategias. No autoriza operaciones.

Separar el porcentaje de aciertos de la ganancia neta observada.
Las señales canceladas tienen solo resultado hipotético: no son ganancias.
"""
from collections import Counter
from datetime import datetime, timezone
from math import isfinite, sqrt


ESTADOS_EJECUTADOS = frozenset({"OPERADA_DIRECTA", "OPERADA_PROTOCOLO", "OPERADA", "CERRADA"})
META_WR = 59.0


def punto_equilibrio(payout_neto):
    """Pago neto por victoria / importe arriesgado. 0.70 => 58.82%."""
    ratio = float(payout_neto)
    if not isfinite(ratio) or ratio <= 0:
        raise ValueError("El payout neto debe ser positivo y finito")
    return round(100 / (1 + ratio), 4)


def _wilson_min_95(wins, n):
    if not n:
        return 0.0
    z = 1.96
    p = wins / n
    return 100 * (p + z*z/(2*n) - z*sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1+z*z/n)


def _dia_utc(valor):
    """Normaliza fechas ISO y epoch a días UTC, sin suponer huso local."""
    if valor in (None, ""):
        return None
    try:
        raw = str(valor).strip()
        if isinstance(valor, (int, float)) or raw.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(valor), timezone.utc).date().isoformat()
        fecha = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.astimezone(timezone.utc).date().isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def evaluar_rentabilidad(filas, payout_neto=None):
    """Diagnóstico retrospectivo, sin inferir pagos o ejecuciones ausentes.

    Un payout explícito permite calcular el break-even teórico, no demostrar
    PNL observado. Solo PNL monetario cerrado y explícito prueba rentabilidad.
    """
    filas = list(filas)
    evaluadas = []
    ignoradas = Counter()
    mercados = set()
    fechas = set()
    mercados_por_dia = {}
    ganancias = perdidas = 0
    pnl = 0.0
    pnl_completo = True
    identidades_ejecutadas = {}
    conflictos_order_id = set()
    for r in filas:
        if not isinstance(r, dict):
            ignoradas["INVALIDA"] += 1
            continue
        if str(r.get("estado_operacion", "")).upper() not in ESTADOS_EJECUTADOS:
            ignoradas["NO_EJECUTADA"] += 1
            continue
        resultado = str(r.get("resultado", "")).upper()
        if resultado not in ("WIN", "LOSS"):
            ignoradas["SIN_CIERRE_WIN_LOSS"] += 1
            continue
        order_id = str(r.get("order_id") or "").strip()
        if order_id:
            firma = (resultado, str(r.get("pnl_real_cerrado", "")).strip())
            if order_id in identidades_ejecutadas:
                if identidades_ejecutadas[order_id] != firma:
                    conflictos_order_id.add(order_id)
                    ignoradas["CONFLICTO_ORDER_ID"] += 1
                else:
                    ignoradas["DUPLICADO_ORDER_ID"] += 1
                continue
            identidades_ejecutadas[order_id] = firma
        evaluadas.append(r)
        ganancias += resultado == "WIN"
        perdidas += resultado == "LOSS"
        if r.get("activo"):
            mercados.add(r["activo"])
        dia = _dia_utc(r.get("fecha_senal") or r.get("fecha"))
        if dia:
            fechas.add(dia)
            if r.get("activo"):
                mercados_por_dia.setdefault(dia, set()).add(r["activo"])
        try:
            valor = float(r["pnl_real_cerrado"])
            if not isfinite(valor):
                raise ValueError("PNL no finito")
            pnl += valor
        except (KeyError, TypeError, ValueError):
            pnl_completo = False
    n = len(evaluadas)
    # Identidades contradictorias impiden certificar WR y PNL.
    datos_confiables = not conflictos_order_id
    identidad_verificable = bool(n and datos_confiables
                                and len(identidades_ejecutadas) == n)
    wr = 100 * ganancias / n if n and datos_confiables else None
    inferior = _wilson_min_95(ganancias, n) if datos_confiables else None
    evidencia_estadistica = bool(
        identidad_verificable and n >= 100 and len(fechas) >= 3
        and inferior is not None and inferior >= META_WR)
    rentabilidad_certificada = bool(
        evidencia_estadistica and pnl_completo and pnl > 0)
    break_even = punto_equilibrio(payout_neto) if payout_neto is not None else None
    return {
        "observaciones": len(filas),
        "operaciones_cerradas": n,
        "order_ids_distintos": len(identidades_ejecutadas),
        "identidades_conflictivas": len(conflictos_order_id),
        "identidad_100pct_verificable": identidad_verificable,
        "wins": ganancias,
        "losses": perdidas,
        "winrate_observado": round(wr, 2) if wr is not None else None,
        "mercados_distintos": len(mercados),
        "maximo_mercados": 20,
        # 20 limita el universo simultáneo, NO los distintos de varios días.
        # Sin instantáneas por ronda, >20 acumulados no prueba infracción.
        "mercados_dentro_del_maximo": True if len(mercados) <= 20 else None,
        "capacidad_simultanea_verificable": len(mercados) <= 20,
        "mercados_por_dia": {dia: len(m) for dia, m in sorted(mercados_por_dia.items())},
        "fechas_con_operaciones": len(fechas),
        "ignoradas": dict(ignoradas),
        "payout_neto_explicito": payout_neto,
        "break_even_teorico": break_even,
        "supera_59_observado": bool(wr is not None and wr >= META_WR),
        "wilson_inferior_95": round(inferior, 2) if inferior is not None else None,
        "cobertura_estadistica_retrospectiva_59": evidencia_estadistica,
        "pnl_positivo_con_cobertura_retrospectiva": rentabilidad_certificada,
        "supera_break_even_teorico": bool(
            wr is not None and break_even is not None and wr > break_even),
        "pnl_real_cerrado": round(pnl, 2) if n and pnl_completo and datos_confiables else None,
        "rentabilidad_observada_positiva": (
            pnl > 0 if n and pnl_completo and identidad_verificable else None),
        "autoriza_operacion": False,
    }
