"""Tres detectores exploratorios de price action; nunca autorizan operaciones.

Requieren barras completas de 1m contiguas y estado de mercado externo.
Niveles siempre construidos ANTES de las velas que se juzgan.
"""
from math import isfinite


def _validar(minutos, minimo=24):
    if len(minutos) < minimo:
        return False, "SIN_DATOS"
    prev = None
    for vela in minutos:
        try:
            t = int(vela["from"])
            fin = int(vela["end"])
            o, h, l, c = (float(vela[k]) for k in ("open", "high", "low", "close"))
        except (KeyError, ValueError, TypeError, OverflowError):
            return False, "VELA_INVALIDA"
        if fin - t != 60 or not all(isfinite(x) for x in (o, h, l, c)):
            return False, "VELA_INVALIDA"
        if l > min(o, c) or h < max(o, c):
            return False, "VELA_INVALIDA"
        if prev is not None and t - prev != 60:
            return False, "HUECO_TEMPORAL"
        prev = t
    return True, "OK"


def _salida(nombre, razon, direccion=None, nivel=None):
    return {
        "estrategia": nombre,
        "estado": "CANDIDATO_SOMBRA" if direccion else "SIN_SENAL",
        "direccion": direccion,
        "nivel_previo": nivel,
        "razon": razon,
        "operable": False,
    }


def ruptura_retest(minutos, regimen):
    """20 barras nivel, luego ruptura, retest y confirmacion."""
    nombre = "RUPTURA_RETEST"
    valido, razon = _validar(minutos)
    if not valido:
        return _salida(nombre, razon)
    if regimen not in ("TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"):
        return _salida(nombre, "REGIMEN_INCOMPATIBLE")
    contexto, ruptura, retest, confirmacion = minutos[-23:-3], *minutos[-3:]
    resistencia = max(v["high"] for v in contexto)
    soporte = min(v["low"] for v in contexto)
    if regimen == "TENDENCIA_ALCISTA":
        if (ruptura["close"] > resistencia
                and retest["low"] <= resistencia
                and retest["close"] >= resistencia
                and confirmacion["close"] > max(retest["close"], resistencia)):
            return _salida(nombre, "RUPTURA_Y_RETEST_ALCISTA", "call", resistencia)
    else:
        if (ruptura["close"] < soporte
                and retest["high"] >= soporte
                and retest["close"] <= soporte
                and confirmacion["close"] < min(retest["close"], soporte)):
            return _salida(nombre, "RUPTURA_Y_RETEST_BAJISTA", "put", soporte)
    return _salida(nombre, "SECUENCIA_NO_CONFIRMADA")


def rechazo_zona(minutos, regimen):
    """Contexto anterior 20 barras + penetracion y cierre de recuperacion."""
    nombre = "RECHAZO_ZONA"
    valido, razon = _validar(minutos, 22)
    if not valido:
        return _salida(nombre, razon)
    if regimen != "RANGO":
        return _salida(nombre, "REGIMEN_INCOMPATIBLE")
    contexto, penetracion, cierre = minutos[-22:-2], *minutos[-2:]
    soporte = min(v["low"] for v in contexto)
    resistencia = max(v["high"] for v in contexto)
    if (penetracion["low"] < soporte and penetracion["close"] <= soporte
            and cierre["close"] > soporte and cierre["close"] > cierre["open"]):
        return _salida(nombre, "RECUPERACION_SOPORTE", "call", soporte)
    if (penetracion["high"] > resistencia and penetracion["close"] >= resistencia
            and cierre["close"] < resistencia and cierre["close"] < cierre["open"]):
        return _salida(nombre, "RECUPERACION_RESISTENCIA", "put", resistencia)
    return _salida(nombre, "SIN_RECUPERACION")


def continuacion_tendencia(minutos, regimen):
    """Retroceso en barra previa, confirmacion posterior, nivel SMA20 previo."""
    nombre = "CONTINUACION_TENDENCIA"
    valido, razon = _validar(minutos, 22)
    if not valido:
        return _salida(nombre, razon)
    if regimen not in ("TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"):
        return _salida(nombre, "REGIMEN_INCOMPATIBLE")
    contexto, retroceso, confirmacion = minutos[-22:-2], *minutos[-2:]
    media_previa = sum(v["close"] for v in contexto) / len(contexto)
    if regimen == "TENDENCIA_ALCISTA":
        if (retroceso["close"] < retroceso["open"]
                and retroceso["low"] <= media_previa
                and confirmacion["close"] > retroceso["high"]):
            return _salida(nombre, "CONTINUACION_ALCISTA", "call", media_previa)
    else:
        if (retroceso["close"] > retroceso["open"]
                and retroceso["high"] >= media_previa
                and confirmacion["close"] < retroceso["low"]):
            return _salida(nombre, "CONTINUACION_BAJISTA", "put", media_previa)
    return _salida(nombre, "SIN_CONFIRMACION")


def diagnosticar_estrategias(minutos, regimen):
    return [
        ruptura_retest(minutos, regimen),
        rechazo_zona(minutos, regimen),
        continuacion_tendencia(minutos, regimen),
    ]
