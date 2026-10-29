"""Nucleo de contexto de mercado de BootIQ V3 (solo lectura).

Arquitectura nueva: velas cerradas 1s -> barras completas 1m -> estado
de mercado. No importa conexion, ordenes, ni memorias anteriores.
Los umbrales iniciales son descriptivos y NO validados para operar.
"""
from collections import defaultdict
from math import isfinite
from statistics import median


def consolidar_minutos(velas_1s):
    """Solo minutos UTC COMPLETOS de 60 velas consecutivas, sin anticipacion."""
    grupos = defaultdict(list)
    for t, vela in sorted(velas_1s.items()):
        if not isinstance(t, int) or int(vela["from"]) != t:
            raise ValueError("TIMESTAMP_INVALIDO")
        o, h, l, c = (float(vela[k]) for k in ("open", "max", "min", "close"))
        if not all(isfinite(v) for v in (o, h, l, c)):
            raise ValueError("PRECIO_NO_FINITO")
        if l > min(o, c) or h < max(o, c):
            raise ValueError("OHLC_INVALIDO")
        grupos[(t // 60) * 60].append((t, o, h, l, c))
    minutos = []
    for t, grupo in sorted(grupos.items()):
        if len(grupo) != 60 or [v[0] for v in grupo] != list(range(t, t + 60)):
            continue  # una vela incompleta no debe construir contexto
        minutos.append({
            "from": t,
            "end": t + 60,
            "open": grupo[0][1],
            "high": max(v[2] for v in grupo),
            "low": min(v[3] for v in grupo),
            "close": grupo[-1][4],
        })
    return minutos


def diagnosticar_contexto(minutos, periodo=20):
    """Contexto descriptivo; nunca devuelve una autorizacion de operacion."""
    if not 5 <= periodo <= 120:
        raise ValueError("PERIODO_INVALIDO")
    if len(minutos) < periodo:
        return {"estado": "SIN_DATOS", "operable": False,
                "razon": "CALENTAMIENTO_INSUFICIENTE"}
    ultimas = minutos[-periodo:]
    if any(b["from"] - a["from"] != 60 for a, b in zip(ultimas, ultimas[1:])):
        return {"estado": "SUCIO", "operable": False,
                "razon": "HUECO_EN_MINUTOS"}
    cierres = [float(x["close"]) for x in ultimas]
    recorridos = [abs(b - a) for a, b in zip(cierres, cierres[1:])]
    distancia = abs(cierres[-1] - cierres[0])
    movimiento = sum(recorridos)
    eficiencia = distancia / movimiento if movimiento else 0.0
    rangos = [float(x["high"]) - float(x["low"]) for x in ultimas]
    if any(not isfinite(v) or v < 0 for v in rangos):
        return {"estado": "SUCIO", "operable": False, "razon": "RANGO_INVALIDO"}
    rango_mediano = median(rangos)
    if rango_mediano <= 0:
        return {"estado": "SUCIO", "operable": False, "razon": "SIN_MOVIMIENTO"}
    if rangos[-1] > 3 * rango_mediano:
        estado = "CAOTICO"
    elif eficiencia >= 0.60:
        estado = "TENDENCIA_ALCISTA" if cierres[-1] > cierres[0] else "TENDENCIA_BAJISTA"
    elif eficiencia <= 0.25:
        estado = "RANGO"
    else:
        estado = "MIXTO"
    return {
        "estado": estado,
        "eficiencia_tendencia": round(eficiencia, 4),
        "rango_mediano": rango_mediano,
        "rango_ultimo": rangos[-1],
        "velas_contexto": periodo,
        "operable": False,
        "razon": "DIAGNOSTICO_EXPLORATORIO_NO_ESTRATEGIA_VALIDADA",
    }
