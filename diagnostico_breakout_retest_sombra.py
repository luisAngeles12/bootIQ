"""Diagnóstico histórico de breakout/retest: nunca autoriza entradas."""

from zonas import zonas_reales


def diagnosticar_breakout_retest_sombra(opens, closes, highs, lows):
    """Reconstruye niveles anteriores a la ruptura con velas ya cerradas.

    Las dos velas finales representan ruptura y retest. Los niveles y su
    tolerancia se calculan exclusivamente con velas anteriores a ambas.
    No sustituye br_call/br_put ni participa en la autorización.
    """
    neutral = {
        "br_call_sombra": 0,
        "br_put_sombra": 0,
        "br_call_nivel_sombra": None,
        "br_put_nivel_sombra": None,
    }
    n = len(closes)
    if n < 16 or any(len(s) != n for s in (opens, highs, lows)):
        return neutral

    highs_previos = highs[:-2]
    lows_previos = lows[:-2]
    volatilidad_previa = sum(
        h - l for h, l in zip(highs_previos[-14:], lows_previos[-14:])
    ) / 14
    if volatilidad_previa <= 0:
        return neutral

    tolerancia = volatilidad_previa * 0.45
    zonas = zonas_reales(
        highs_previos[-100:],
        lows_previos[-100:],
        minimo_toques=3,
        tolerancia_base=tolerancia,
    )

    cierre_previo, cierre_ruptura, cierre_retest = closes[-3:]
    low_retest, high_retest = lows[-1], highs[-1]

    call = [
        z for z in zonas
        if cierre_previo <= z["precio"] + z["tolerancia"]
        and cierre_ruptura > z["precio"] + z["tolerancia"]
        and abs(low_retest - z["precio"]) <= z["tolerancia"]
        and cierre_retest > z["precio"]
    ]
    put = [
        z for z in zonas
        if cierre_previo >= z["precio"] - z["tolerancia"]
        and cierre_ruptura < z["precio"] - z["tolerancia"]
        and abs(high_retest - z["precio"]) <= z["tolerancia"]
        and cierre_retest < z["precio"]
    ]

    result = dict(neutral)
    if call:
        nivel = min(call, key=lambda z: (abs(low_retest - z["precio"]), -z["fuerza"]))
        result["br_call_sombra"] = 1
        result["br_call_nivel_sombra"] = nivel["precio"]
    if put:
        nivel = min(put, key=lambda z: (abs(high_retest - z["precio"]), -z["fuerza"]))
        result["br_put_sombra"] = -1
        result["br_put_nivel_sombra"] = nivel["precio"]
    return result
