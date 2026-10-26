"""Auditoría económica PASIVA de estrategias. No autoriza operaciones.

Separar el porcentaje de aciertos de la ganancia neta observada.
Las señales canceladas tienen solo resultado hipotético: no son ganancias.
"""
from collections import Counter
from math import isfinite


ESTADOS_EJECUTADOS = frozenset({"OPERADA_DIRECTA", "OPERADA", "CERRADA"})
META_WR = 59.0


def punto_equilibrio(payout_neto):
    """Pago neto por victoria / importe arriesgado. 0.70 => 58.82%."""
    ratio = float(payout_neto)
    if not isfinite(ratio) or ratio <= 0:
        raise ValueError("El payout neto debe ser positivo y finito")
    return round(100 / (1 + ratio), 4)


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
    ganancias = perdidas = 0
    pnl = 0.0
    pnl_completo = True
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
        evaluadas.append(r)
        ganancias += resultado == "WIN"
        perdidas += resultado == "LOSS"
        if r.get("activo"):
            mercados.add(r["activo"])
        fecha = str(r.get("fecha_senal", "") or r.get("fecha", ""))
        if fecha:
            fechas.add(fecha[:10] if len(fecha) >= 10 and "-" in fecha[:10] else fecha)
        try:
            valor = float(r["pnl_real_cerrado"])
            if not isfinite(valor):
                raise ValueError("PNL no finito")
            pnl += valor
        except (KeyError, TypeError, ValueError):
            pnl_completo = False
    n = len(evaluadas)
    wr = 100 * ganancias / n if n else None
    break_even = punto_equilibrio(payout_neto) if payout_neto is not None else None
    return {
        "observaciones": len(filas),
        "operaciones_cerradas": n,
        "wins": ganancias,
        "losses": perdidas,
        "winrate_observado": round(wr, 2) if wr is not None else None,
        "mercados_distintos": len(mercados),
        "maximo_mercados": 20,
        "mercados_dentro_del_maximo": len(mercados) <= 20,
        "fechas_con_operaciones": len(fechas),
        "ignoradas": dict(ignoradas),
        "payout_neto_explicito": payout_neto,
        "break_even_teorico": break_even,
        "supera_59_observado": bool(wr is not None and wr >= META_WR),
        "supera_break_even_teorico": bool(
            wr is not None and break_even is not None and wr > break_even),
        "pnl_real_cerrado": round(pnl, 2) if n and pnl_completo else None,
        "rentabilidad_observada_positiva": (
            pnl > 0 if n and pnl_completo else None),
        "autoriza_operacion": False,
    }
