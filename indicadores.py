import pandas as pd
import numpy as np
def pendiente_ema(prices, period=21, lookback=8):
    if len(prices) < period + lookback:
        return 0

    serie = pd.Series(prices, dtype="float64")
    ema_vals = serie.ewm(span=period, adjust=False).mean()

    actual = ema_vals.iloc[-1]
    previa = ema_vals.iloc[-lookback]

    if previa == 0:
        return 0

    pendiente = (actual - previa) / previa

    if pendiente > 0.00008:
        return 1
    if pendiente < -0.00008:
        return -1

    return 0
def estructura_reciente(highs, lows, lookback=12):
    if len(highs) < lookback or len(lows) < lookback:
        return 0

    h = highs[-lookback:]
    l = lows[-lookback:]

    maximos_suben = h[-1] > h[0]
    minimos_suben = l[-1] > l[0]

    maximos_bajan = h[-1] < h[0]
    minimos_bajan = l[-1] < l[0]

    if maximos_suben and minimos_suben:
        return 1

    if maximos_bajan and minimos_bajan:
        return -1

    return 0
def fuerza_impulso(opens, closes, highs, lows, lookback=8):
    if len(closes) < lookback:
        return 0

    cuerpos = []
    rangos = []

    for i in range(-lookback, 0):
        rango = highs[i] - lows[i]
        cuerpo = abs(closes[i] - opens[i])

        if rango > 0:
            cuerpos.append(cuerpo)
            rangos.append(rango)

    if not rangos:
        return 0

    ratio = sum(cuerpos) / sum(rangos)

    return ratio
def calcular_rsi(prices, period=14):
    """RSI de Wilder usando exclusivamente cierres disponibles.

    Devuelve 50 si no existe movimiento en ninguna dirección.
    La semilla utiliza los primeros `period` cambios, y las
    observaciones posteriores reciben suavizado de Wilder.
    """
    if period < 1 or len(prices) < period + 1:
        return None

    serie = pd.Series(prices, dtype="float64")
    if not np.isfinite(serie.to_numpy()).all():
        return None

    cambios = serie.diff().iloc[1:]
    ganancias = cambios.clip(lower=0.0)
    perdidas = (-cambios).clip(lower=0.0)

    ganancia_media = float(ganancias.iloc[:period].mean())
    perdida_media = float(perdidas.iloc[:period].mean())

    for ganancia, perdida in zip(
        ganancias.iloc[period:],
        perdidas.iloc[period:],
    ):
        ganancia_media = ((period - 1) * ganancia_media + float(ganancia)) / period
        perdida_media = ((period - 1) * perdida_media + float(perdida)) / period

    if ganancia_media == 0.0 and perdida_media == 0.0:
        return 50.0
    if perdida_media == 0.0:
        return 100.0
    if ganancia_media == 0.0:
        return 0.0

    rs = ganancia_media / perdida_media
    return float(100.0 - (100.0 / (1.0 + rs)))

def ema(prices, period):
    return float(pd.Series(prices, dtype="float64").ewm(span=period, adjust=False).mean().iloc[-1])


def bollinger_bands(prices, period=20, std=2):
    serie = pd.Series(prices, dtype="float64")
    media = serie.rolling(period).mean()
    desviacion = serie.rolling(period).std()
    superior = media + desviacion * std
    inferior = media - desviacion * std
    if pd.isna(superior.iloc[-1]) or pd.isna(inferior.iloc[-1]):
        return None, None, None
    return float(superior.iloc[-1]), float(media.iloc[-1]), float(inferior.iloc[-1])


def volatilidad(highs, lows, period=14):
    if len(highs) < period:
        return 0
    return sum(highs[i] - lows[i] for i in range(-period, 0)) / period


def tendencia_regresion(prices, velas=80):
    
    data = np.array(prices[-velas:], dtype=float)
    if len(data) < velas:
        return 0
    x = np.arange(len(data))
    slope = np.polyfit(x, data, 1)[0]
    promedio = np.mean(data)
    if promedio == 0:
        return 0
    fuerza = slope / promedio
    if fuerza > 0.000025:
        return 1
    if fuerza < -0.000025:
        return -1
    return 0


def estructura_mercado(highs, lows, periodo=30):
    if len(highs) < periodo or len(lows) < periodo:
        return 0
    h = highs[-periodo:]
    l = lows[-periodo:]
    max_anterior = max(h[:15])
    max_actual = max(h[15:])
    min_anterior = min(l[:15])
    min_actual = min(l[15:])
    if max_actual > max_anterior and min_actual > min_anterior:
        return 1
    if max_actual < max_anterior and min_actual < min_anterior:
        return -1
    return 0


def micro_tendencia(opens, closes, cantidad=6):
    if len(opens) < cantidad or len(closes) < cantidad:
        return 0

    ult_opens = opens[-cantidad:]
    ult_closes = closes[-cantidad:]

    alcistas = 0
    bajistas = 0
    cierres_subiendo = 0
    cierres_bajando = 0
    cuerpos_fuertes_alcistas = 0
    cuerpos_fuertes_bajistas = 0

    for i in range(cantidad):
        o = ult_opens[i]
        c = ult_closes[i]
        cuerpo = abs(c - o)

        if c > o:
            alcistas += 1
            if cuerpo > 0:
                cuerpos_fuertes_alcistas += 1

        elif c < o:
            bajistas += 1
            if cuerpo > 0:
                cuerpos_fuertes_bajistas += 1

        if i > 0:
            if ult_closes[i] > ult_closes[i - 1]:
                cierres_subiendo += 1
            elif ult_closes[i] < ult_closes[i - 1]:
                cierres_bajando += 1

    if alcistas >= 4 and cierres_subiendo >= 3 and cuerpos_fuertes_alcistas >= 3:
        return 1

    if bajistas >= 4 and cierres_bajando >= 3 and cuerpos_fuertes_bajistas >= 3:
        return -1

    return 0

def movimiento_extendido(opens, closes, cantidad=5):
    if len(opens) < cantidad or len(closes) < cantidad:
        return 0

    ult_opens = opens[-cantidad:]
    ult_closes = closes[-cantidad:]

    alcistas = 0
    bajistas = 0
    avance_total = ult_closes[-1] - ult_closes[0]

    for o, c in zip(ult_opens, ult_closes):
        if c > o:
            alcistas += 1
        elif c < o:
            bajistas += 1

    if alcistas >= 4 and avance_total > 0:
        return 1

    if bajistas >= 4 and avance_total < 0:
        return -1

    return 0