import pandas as pd
import numpy as np

def calcular_rsi(prices, period=14):
    if len(prices) < period + 2:
        return None
    serie = pd.Series(prices, dtype="float64")
    delta = serie.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    if pd.isna(loss.iloc[-1]) or loss.iloc[-1] == 0:
        return None
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    if pd.isna(rsi.iloc[-1]):
        return None
    return float(rsi.iloc[-1])


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
    alcistas = 0
    bajistas = 0
    for i in range(-cantidad, 0):
        if closes[i] > opens[i]:
            alcistas += 1
        elif closes[i] < opens[i]:
            bajistas += 1
    if alcistas >= 4:
        return 1
    if bajistas >= 4:
        return -1
    return 0


def movimiento_extendido(opens, closes, cantidad=5):
    alcistas = 0
    bajistas = 0
    for i in range(-cantidad, 0):
        if closes[i] > opens[i]:
            alcistas += 1
        elif closes[i] < opens[i]:
            bajistas += 1
    if alcistas >= 4:
        return 1
    if bajistas >= 4:
        return -1
    return 0
