"""Criterio de aceptación F3 para candidato PRECONGELADO; solo offline.

Recibe únicamente señales que el candidato habría seleccionado, no busca
combinaciones ni activa trading. No sustituye umbrales del motor operativo.
"""
from collections import Counter
from datetime import datetime, timezone
from math import isfinite, sqrt

OBJETIVO_WR = 57.0
CORTE_UTC = datetime(2026, 10, 26, tzinfo=timezone.utc).timestamp()


def _wilson(wins, n):
    if not n:
        return 0.0
    z = 1.96
    p = wins / n
    return 100 * (p+z*z/(2*n)-z*sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)


def _marca(fila):
    try:
        val = fila.get("fecha_senal") or fila.get("fecha")
        return float(val)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Señal sin fecha epoch válida")


def evaluar_meta_sostenida(ventanas, *, payout_neto, minimo_total=100,
                           minimo_por_dia=30, minimo_dias=3):
    if payout_neto is None:
        raise ValueError("Payout neto observado obligatorio")
    try:
        payout = float(payout_neto)
    except (ValueError, TypeError):
        raise ValueError("Payout neto inválido")
    if not isfinite(payout) or payout <= 0:
        raise ValueError("Payout neto inválido")
    if min(minimo_total, minimo_por_dia, minimo_dias) <= 0:
        raise ValueError("Mínimos inválidos")

    if not ventanas:
        raise ValueError("Se requieren ventanas")
    nombres, fechas, identidades = set(), set(), set()
    conteo = Counter()
    detalle = []
    pnls = []
    for nombre, filas in ventanas:
        if not nombre or nombre in nombres:
            raise ValueError("Ventana sin nombre o duplicada")
        nombres.add(nombre)
        filas = list(filas)
        if not filas:
            raise ValueError("Ventana vacía")
        dias = set()
        w = l = 0
        for fila in filas:
            if not isinstance(fila, dict):
                raise ValueError("Fila inválida")
            marca = _marca(fila)
            if marca < CORTE_UTC:
                raise ValueError("Señal previa a la congelación")
            dia = datetime.fromtimestamp(marca, timezone.utc).date().isoformat()
            dias.add(dia)
            identificador = (marca, fila.get("activo"), fila.get("patron"), fila.get("direccion"))
            if identificador in identidades:
                raise ValueError("Señal duplicada entre ventanas")
            identidades.add(identificador)
            resultado = str(fila.get("resultado") or "").upper()
            estado = str(fila.get("estado_operacion") or "").upper()
            if estado not in ("OPERADA", "OPERADA_DIRECTA", "CERRADA") or resultado not in ("WIN", "LOSS"):
                raise ValueError("Se requieren operaciones PRACTICE cerradas")
            if str(fila.get("tipo_cuenta") or "").upper() != "PRACTICE":
                raise ValueError("Se exige evidencia explícita PRACTICE")
            try:
                pnl = float(fila["pnl_real_cerrado"])
            except (KeyError, ValueError, TypeError):
                raise ValueError("PNL monetario cerrado obligatorio")
            if not isfinite(pnl):
                raise ValueError("PNL no finito")
            pnls.append(pnl)
            w += resultado == "WIN"
            l += resultado == "LOSS"
        if len(dias) != 1:
            raise ValueError("Cada ventana debe representar un día UTC")
        dia = next(iter(dias))
        if dia in fechas:
            raise ValueError("Ventanas comparten día UTC")
        fechas.add(dia)
        n = w + l
        conteo["win"] += w
        conteo["loss"] += l
        detalle.append({"ventana": nombre, "dia": dia, "n": n,
                        "win": w, "loss": l, "wr": round(100*w/n, 2),
                        "suficiente": n >= minimo_por_dia})
    n = conteo["win"]+conteo["loss"]
    wr = 100*conteo["win"]/n
    inferior = _wilson(conteo["win"], n)
    suficiente = (n >= minimo_total and
                  sum(x["suficiente"] for x in detalle) >= minimo_dias)
    estable = (suficiente and all(x["wr"] > OBJETIVO_WR
              for x in detalle if x["suficiente"]) and
              wr > OBJETIVO_WR and inferior > OBJETIVO_WR)
    pnl = round(sum(pnls), 2)
    return {"meta": OBJETIVO_WR, "ventanas": sorted(detalle, key=lambda x:x["dia"]),
            "n": n, "win": conteo["win"], "loss": conteo["loss"],
            "wr": round(wr, 2), "wilson_inferior_95": round(inferior, 2),
            "payout_neto_declarado": payout,
            "pnl_real_cerrado": pnl, "cobertura_suficiente": suficiente,
            "estabilidad_estadistica": estable,
            "objetivo_57_sostenido_verificado": bool(estable and pnl > 0),
            "autoriza_real": False}
