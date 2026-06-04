from iqoptionapi.stable_api import IQ_Option
import time
import pandas as pd
import numpy as np
import os
from datetime import datetime
import warnings
from iqoptionapi.constants import ACTIVES

warnings.filterwarnings("ignore")

email = "luisangelestejada@gmail.com"
password = "R@putim120799"

modo_cuenta = "PRACTICE"

monto_base = 10
tiempo_expiracion = 1

CANDLE_TIME = 60
CANDLE_NUMBER = 180
MAX_OPERACIONES_ABIERTAS = 5
operaciones_abiertas = []
stop_loss = -100
puntaje_minimo = 6
historial_csv = "historial_bot.csv"

activos_invalidos = set()
cooldown_activos = {}
activos_cache = []
ultima_actualizacion_activos = 0

print("Conectando a IQ Option...")

Iq = IQ_Option(email, password)

while True:
    try:
        Iq.connect()
    except Exception as e:
        print("Advertencia conectando:", e)

    time.sleep(5)

    if Iq.check_connect():
        break

    print("Reintentando conexión...")

Iq.change_balance(modo_cuenta)
balance_inicial = Iq.get_balance()

print("Conectado correctamente")
print("Balance inicial:", balance_inicial)


def segundo_actual():
    return int(time.localtime().tm_sec)


def esperar_zona_analisis():
    while True:
        s = segundo_actual()

        if 50 <= s <= 56:
            return

        if s < 50:
            espera = 50 - s
        else:
            espera = 60 - s + 50

        print("Esperando zona de análisis:", espera, "segundos")
        time.sleep(min(espera, 5))


def esperar_inicio_vela():
    while True:
        s = segundo_actual()

        if 0 <= s <= 3:
            return True

        if s > 56:
            time.sleep(0.15)
        else:
            return False


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
    return float(
        pd.Series(prices, dtype="float64")
        .ewm(span=period, adjust=False)
        .mean()
        .iloc[-1]
    )


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

    rangos = []

    for i in range(-period, 0):
        rangos.append(highs[i] - lows[i])

    return sum(rangos) / len(rangos)


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


def detectar_zonas(highs, lows, precision=5):
    niveles = []

    for h in highs:
        niveles.append(round(h, precision))

    for l in lows:
        niveles.append(round(l, precision))

    conteo = {}

    for nivel in niveles:
        conteo[nivel] = conteo.get(nivel, 0) + 1

    zonas = []

    for precio, veces in conteo.items():
        if veces >= 3:
            zonas.append(precio)

    return sorted(zonas)


def soporte_resistencia(price, highs, lows):
    zonas = detectar_zonas(highs, lows)

    soportes = [z for z in zonas if z < price]
    resistencias = [z for z in zonas if z > price]

    soporte = max(soportes) if soportes else min(lows[-80:])
    resistencia = min(resistencias) if resistencias else max(highs[-80:])

    return float(soporte), float(resistencia)


def patron_velas(opens, closes, highs, lows):
    o1, c1 = opens[-1], closes[-1]
    o2, c2 = opens[-2], closes[-2]

    h1, l1 = highs[-1], lows[-1]

    cuerpo = abs(c1 - o1)
    rango = h1 - l1

    if rango == 0:
        return 0, "sin patrón"

    cuerpo_relativo = cuerpo / rango

    mecha_superior = h1 - max(o1, c1)
    mecha_inferior = min(o1, c1) - l1

    if cuerpo_relativo <= 0.18:
        return 99, "doji/indecisión"

    if c2 < o2 and c1 > o1 and c1 > o2 and o1 < c2 and cuerpo_relativo >= 0.40:
        return 1, "envolvente alcista"

    if c2 > o2 and c1 < o1 and c1 < o2 and o1 > c2 and cuerpo_relativo >= 0.40:
        return -1, "envolvente bajista"

    if mecha_inferior > cuerpo * 2 and c1 > o1:
        return 1, "rechazo alcista"

    if mecha_superior > cuerpo * 2 and c1 < o1:
        return -1, "rechazo bajista"

    return 0, "sin patrón"


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


def hay_agotamiento(opens, closes, highs, lows):
    fuertes_alcistas = 0
    fuertes_bajistas = 0

    for i in range(-3, 0):
        rango = highs[i] - lows[i]
        cuerpo = abs(closes[i] - opens[i])

        if rango == 0:
            continue

        fuerza = cuerpo / rango

        if fuerza >= 0.70 and closes[i] > opens[i]:
            fuertes_alcistas += 1

        if fuerza >= 0.70 and closes[i] < opens[i]:
            fuertes_bajistas += 1

    if fuertes_alcistas >= 3:
        return True

    if fuertes_bajistas >= 3:
        return True

    return False


def guardar_historial(data):
    ruta = os.path.abspath(historial_csv)
    print("Guardando historial en:", ruta)

    columnas = [
        "fecha", "activo", "tipo", "direccion",
        "puntaje", "patron", "rsi", "resultado"
    ]

    df = pd.DataFrame([data], columns=columnas)

    if os.path.exists(historial_csv):
        df.to_csv(historial_csv, mode="a", header=False, index=False)
    else:
        df.to_csv(historial_csv, index=False)
def cargar_historial():
    if not os.path.exists(historial_csv):
        return None

    try:
        columnas = [
            "fecha",
            "activo",
            "tipo",
            "direccion",
            "puntaje",
            "patron",
            "rsi",
            "resultado"
        ]

        df = pd.read_csv(historial_csv)

        if "tipo" not in df.columns:
            df = pd.read_csv(historial_csv, names=columnas)

        return df

    except Exception as e:
        print("Error cargando historial:", e)
        return None
def winrate_activo(activo):
    df = cargar_historial()

    if df is None:
        return 0.5

    df = df[df["activo"] == activo]

    if len(df) < 5:
        return 0.5

    ganadas = len(df[df["resultado"] > 0])
    return ganadas / len(df)


def winrate_patron(patron):
    df = cargar_historial()

    if df is None:
        return 0.5

    df = df[df["patron"] == patron]

    if len(df) < 5:
        return 0.5

    ganadas = len(df[df["resultado"] > 0])
    return ganadas / len(df)


def perdidas_recientes_activo(activo, cantidad=3):
    df = cargar_historial()

    if df is None:
        return False

    df = df[df["activo"] == activo]

    if len(df) < cantidad:
        return False

    ultimas = df.tail(cantidad)

    return all(ultimas["resultado"] < 0)


def ajustar_por_memoria(activo, patron, puntaje):
    wr_activo = winrate_activo(activo)
    wr_patron = winrate_patron(patron)

    if wr_activo >= 0.65:
        puntaje += 1

    if wr_activo <= 0.35:
        puntaje -= 2

    if wr_patron >= 0.65:
        puntaje += 1

    if wr_patron <= 0.35:
        puntaje -= 1

    return puntaje


def activo_en_cooldown(activo):
    if activo not in cooldown_activos:
        return False

    if time.time() - cooldown_activos[activo] > 60:
        del cooldown_activos[activo]
        return False

    return True


def obtener_velas(activo):
    try:
        candles = Iq.get_candles(
            activo,
            CANDLE_TIME,
            CANDLE_NUMBER,
            time.time()
        )

        if not candles or len(candles) < 130:
            return None

        candles = sorted(candles, key=lambda x: x["from"])

        candles = candles[:-1]

        return {
            "open": [float(c["open"]) for c in candles],
            "close": [float(c["close"]) for c in candles],
            "high": [float(c["max"]) for c in candles],
            "low": [float(c["min"]) for c in candles]
        }

    except Exception as e:
        texto = str(e).lower()

        if "not found" in texto or "consts" in texto:
            activos_invalidos.add(activo)

        return None


def obtener_activos():
    global activos_cache
    global ultima_actualizacion_activos

    if time.time() - ultima_actualizacion_activos < 300 and activos_cache:
        return [
            item for item in activos_cache
            if item["activo"] not in activos_invalidos
            and not activo_en_cooldown(item["activo"])
        ]

    activos = []

    try:
        data = Iq.get_all_open_time()
    except Exception as e:
        print("Error obteniendo activos:", e)
        return activos_cache

    tipos = ["turbo", "binary", "digital"]

    for tipo in tipos:
        if tipo not in data:
            continue

        for asset, info in data[tipo].items():
            try:
                if not info.get("open"):
                    continue

                if asset in activos_invalidos:
                    continue

                if activo_en_cooldown(asset):
                    continue

                if "/" in asset:
                    continue

                if asset not in ACTIVES:
                    activos_invalidos.add(asset)
                    continue

                test = Iq.get_candles(asset, CANDLE_TIME, 5, time.time())

                if test and len(test) >= 5:
                    activos.append({
                        "activo": asset,
                        "tipo": tipo
                    })

            except Exception as e:
                texto = str(e).lower()

                if "not found" in texto or "consts" in texto:
                    activos_invalidos.add(asset)

                continue

    activos_cache = activos
    ultima_actualizacion_activos = time.time()

    print("Activos compatibles actualizados:", len(activos_cache))

    return activos_cache
def rechazo_real(opens, closes, highs, lows):
    o = opens[-1]
    c = closes[-1]
    h = highs[-1]
    l = lows[-1]

    cuerpo = abs(c - o)
    rango = h - l

    if rango == 0:
        return 0, "sin rechazo"

    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l

    if mecha_inf >= cuerpo * 1.8 and c > o:
        return 1, "rechazo comprador fuerte"

    if mecha_sup >= cuerpo * 1.8 and c < o:
        return -1, "rechazo vendedor fuerte"

    return 0, "sin rechazo"


def absorcion(opens, closes, highs, lows):
    r, nombre = rechazo_real(opens, closes, highs, lows)

    if r == 1:
        return 1, "absorción compradora"

    if r == -1:
        return -1, "absorción vendedora"

    return 0, "sin absorción"
def zonas_reales(highs, lows, precision=5, minimo_toques=3, tolerancia_base=None):
    niveles = []

    for h in highs:
        niveles.append(round(h, precision))

    for l in lows:
        niveles.append(round(l, precision))

    niveles = sorted(niveles)

    if not niveles:
        return []

    zonas = []

    for nivel in niveles:
        agregado = False

        for zona in zonas:
            if abs(nivel - zona["precio"]) <= zona["tolerancia"]:
                zona["toques"] += 1
                zona["precios"].append(nivel)
                zona["precio"] = sum(zona["precios"]) / len(zona["precios"])
                agregado = True
                break

        if not agregado:
            tolerancia = tolerancia_base if tolerancia_base is not None else abs(nivel) * 0.00008

            zonas.append({
                "precio": nivel,
                "toques": 1,
                "precios": [nivel],
                "tolerancia": tolerancia
            })

    zonas_fuertes = []

    for zona in zonas:
        if zona["toques"] >= minimo_toques:
            zonas_fuertes.append(zona)

    return zonas_fuertes


def soporte_resistencia_zonas(price, highs, lows, vol):
    zonas = zonas_reales(highs, lows, minimo_toques=3, tolerancia_base=vol * 0.8)

    soportes = [z for z in zonas if z["precio"] < price]
    resistencias = [z for z in zonas if z["precio"] > price]

    soporte = max(soportes, key=lambda z: z["precio"]) if soportes else {
        "precio": min(lows[-80:]),
        "toques": 1,
        "tolerancia": vol * 0.8
    }

    resistencia = min(resistencias, key=lambda z: z["precio"]) if resistencias else {
        "precio": max(highs[-80:]),
        "toques": 1,
        "tolerancia": vol * 0.8
    }

    return soporte, resistencia


def triple_rechazo(highs, lows, zona, tipo="soporte", cantidad=20):
    toques = 0

    if zona is None:
        return False

    precio_zona = zona["precio"]
    tolerancia = zona["tolerancia"]

    for i in range(-cantidad, 0):
        if tipo == "soporte":
            if abs(lows[i] - precio_zona) <= tolerancia:
                toques += 1

        if tipo == "resistencia":
            if abs(highs[i] - precio_zona) <= tolerancia:
                toques += 1

    return toques >= 3


def falsa_ruptura(opens, closes, highs, lows, zona, tipo="soporte"):
    if zona is None:
        return 0, "sin falsa ruptura"

    precio_zona = zona["precio"]
    tolerancia = zona["tolerancia"]

    o = opens[-1]
    c = closes[-1]
    h = highs[-1]
    l = lows[-1]

    cuerpo = abs(c - o)
    rango = h - l

    if rango == 0:
        return 0, "sin falsa ruptura"

    fuerza = cuerpo / rango
    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l

    if tipo == "soporte":
        rompio_abajo = l < precio_zona - tolerancia
        cerro_arriba = c > precio_zona
        rechazo_fuerte = mecha_inf >= cuerpo * 2
        vela_fuerte = c > o and fuerza >= 0.45

        if rompio_abajo and cerro_arriba and rechazo_fuerte and vela_fuerte:
            return 1, "falsa ruptura alcista confirmada"

    if tipo == "resistencia":
        rompio_arriba = h > precio_zona + tolerancia
        cerro_abajo = c < precio_zona
        rechazo_fuerte = mecha_sup >= cuerpo * 2
        vela_fuerte = c < o and fuerza >= 0.45

        if rompio_arriba and cerro_abajo and rechazo_fuerte and vela_fuerte:
            return -1, "falsa ruptura bajista confirmada"

    return 0, "sin falsa ruptura"
def breakout_retest(opens, closes, highs, lows, zona, tipo="resistencia"):
    if zona is None:
        return 0, "sin breakout retest"

    precio_zona = zona["precio"]
    tolerancia = zona["tolerancia"]

    cierre_actual = closes[-1]
    cierre_anterior = closes[-2]
    low_actual = lows[-1]
    high_actual = highs[-1]

    if tipo == "resistencia":
        rompimiento_previo = cierre_anterior > precio_zona + tolerancia
        retest = abs(low_actual - precio_zona) <= tolerancia
        confirma = cierre_actual > precio_zona

        if rompimiento_previo and retest and confirma:
            return 1, "breakout retest alcista"

    if tipo == "soporte":
        rompimiento_previo = cierre_anterior < precio_zona - tolerancia
        retest = abs(high_actual - precio_zona) <= tolerancia
        confirma = cierre_actual < precio_zona

        if rompimiento_previo and retest and confirma:
            return -1, "breakout retest bajista"

    return 0, "sin breakout retest"


def rango_lateral(highs, lows, closes, vol, cantidad=20):
    rango = max(highs[-cantidad:]) - min(lows[-cantidad:])

    if vol == 0:
        return True

    if rango <= vol * 3:
        return True

    return False
def contexto_operacion(
    direccion,
    tendencia,
    estructura,
    patron,
    rechazo,
    zona_call,
    zona_put,
    rsi,
    extension
):
    if direccion == "call":
        if patron == -1:
            return False, "bloqueado: patrón bajista"

        if zona_put and not zona_call:
            return False, "bloqueado: está en resistencia"

        if extension == 1:
            return False, "bloqueado: movimiento alcista extendido"

        if rsi > 62:
            return False, "bloqueado: RSI alto para call"

        if tendencia == -1 and not zona_call and rechazo != 1:
            return False, "bloqueado: call contra tendencia sin rechazo"

        return True, "contexto válido para call"

    if direccion == "put":
        if patron == 1:
            return False, "bloqueado: patrón alcista"

        if zona_call and not zona_put:
            return False, "bloqueado: está en soporte"

        if extension == -1:
            return False, "bloqueado: movimiento bajista extendido"

        if rsi < 38:
            return False, "bloqueado: RSI bajo para put"

        if tendencia == 1 and not zona_put and rechazo != -1:
            return False, "bloqueado: put contra tendencia sin rechazo"

        return True, "contexto válido para put"

    return False, "sin dirección"

def velas_consecutivas_direccion(opens, closes, cantidad=3):
    verdes = 0
    rojas = 0

    for i in range(-cantidad, 0):
        if closes[i] > opens[i]:
            verdes += 1
        elif closes[i] < opens[i]:
            rojas += 1

    if verdes == cantidad:
        return 1

    if rojas == cantidad:
        return -1

    return 0
def vela_confirma_direccion(opens, closes, highs, lows, direccion):
    o = opens[-1]
    c = closes[-1]
    h = highs[-1]
    l = lows[-1]

    rango = h - l
    cuerpo = abs(c - o)

    if rango == 0:
        return False

    fuerza = cuerpo / rango

    if direccion == "call":
        return c > o and fuerza >= 0.45

    if direccion == "put":
        return c < o and fuerza >= 0.45

    return False

def cuerpo_y_mechas(o, c, h, l):
    cuerpo = abs(c - o)
    rango = h - l

    if rango == 0:
        return 0, 0, 0, 0

    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l
    fuerza = cuerpo / rango

    return cuerpo, mecha_sup, mecha_inf, fuerza


def pin_bar(opens, closes, highs, lows):
    o = opens[-1]
    c = closes[-1]
    h = highs[-1]
    l = lows[-1]

    cuerpo, mecha_sup, mecha_inf, fuerza = cuerpo_y_mechas(o, c, h, l)

    if cuerpo == 0:
        return 0, "sin pin bar"

    if mecha_inf >= cuerpo * 2.5 and mecha_sup <= cuerpo * 1.2:
        return 1, "pin bar alcista"

    if mecha_sup >= cuerpo * 2.5 and mecha_inf <= cuerpo * 1.2:
        return -1, "pin bar bajista"

    return 0, "sin pin bar"


def martillo_shooting_star(opens, closes, highs, lows):
    o = opens[-1]
    c = closes[-1]
    h = highs[-1]
    l = lows[-1]

    cuerpo, mecha_sup, mecha_inf, fuerza = cuerpo_y_mechas(o, c, h, l)

    if cuerpo == 0:
        return 0, "sin martillo"

    if mecha_inf >= cuerpo * 2 and mecha_sup <= cuerpo and c > o:
        return 1, "martillo alcista"

    if mecha_sup >= cuerpo * 2 and mecha_inf <= cuerpo and c < o:
        return -1, "shooting star bajista"

    return 0, "sin martillo"


def inside_bar(opens, closes, highs, lows):
    h1 = highs[-1]
    l1 = lows[-1]
    h2 = highs[-2]
    l2 = lows[-2]

    if h1 < h2 and l1 > l2:
        return 1, "inside bar"

    return 0, "sin inside bar"


def master_candle(highs, lows, lookback=4):
    h_master = highs[-lookback - 1]
    l_master = lows[-lookback - 1]

    dentro = 0

    for i in range(-lookback, 0):
        if highs[i] <= h_master and lows[i] >= l_master:
            dentro += 1

    if dentro == lookback:
        return True, h_master, l_master, "master candle"

    return False, None, None, "sin master candle"


def ruptura_master_candle(closes, highs, lows):
    es_master, h_master, l_master, nombre = master_candle(highs, lows, 4)

    if not es_master:
        return 0, "sin ruptura master"

    if closes[-1] > h_master:
        return 1, "ruptura alcista de master candle"

    if closes[-1] < l_master:
        return -1, "ruptura bajista de master candle"

    return 0, "sin ruptura master"


def morning_evening_star(opens, closes, highs, lows):
    o1, c1 = opens[-3], closes[-3]
    o2, c2 = opens[-2], closes[-2]
    o3, c3 = opens[-1], closes[-1]

    h2, l2 = highs[-2], lows[-2]

    cuerpo1 = abs(c1 - o1)
    cuerpo2 = abs(c2 - o2)
    cuerpo3 = abs(c3 - o3)

    rango2 = h2 - l2

    if rango2 == 0:
        return 0, "sin estrella"

    vela2_pequena = cuerpo2 / rango2 <= 0.30

    if c1 < o1 and vela2_pequena and c3 > o3 and c3 > ((o1 + c1) / 2):
        return 1, "morning star alcista"

    if c1 > o1 and vela2_pequena and c3 < o3 and c3 < ((o1 + c1) / 2):
        return -1, "evening star bajista"

    return 0, "sin estrella"


def patron_price_action_avanzado(opens, closes, highs, lows):
    patrones = []

    # Primero patrones de reversa más fuertes
    p, n = morning_evening_star(opens, closes, highs, lows)
    if p != 0:
        patrones.append((p, n, 5))

    p, n = pin_bar(opens, closes, highs, lows)
    if p != 0:
        patrones.append((p, n, 5))

    p, n = martillo_shooting_star(opens, closes, highs, lows)
    if p != 0:
        patrones.append((p, n, 4))

    # Luego envolventes
    p, n = patron_velas(opens, closes, highs, lows)
    if p != 0 and p != 99:
        patrones.append((p, n, 3))

    # Luego ruptura de master candle
    p, n = ruptura_master_candle(closes, highs, lows)
    if p != 0:
        patrones.append((p, n, 4))

    if not patrones:
        return 0, "sin patrón", 0

    patrones = sorted(patrones, key=lambda x: x[2], reverse=True)

    return patrones[0]
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


def entrada_pullback(
    direccion,
    price,
    ema21,
    soporte,
    resistencia,
    vol,
    patron,
    rechazo
):
    cerca_ema = abs(price - ema21) <= vol * 1.2

    if direccion == "call":
        cerca_soporte = abs(price - soporte) <= vol * 1.5

        if (cerca_ema or cerca_soporte) and (patron == 1 or rechazo == 1):
            return True

    if direccion == "put":
        cerca_resistencia = abs(resistencia - price) <= vol * 1.5

        if (cerca_ema or cerca_resistencia) and (patron == -1 or rechazo == -1):
            return True

    return False
def detectar_estrategias_price_action(
    patron,
    nombre_patron,
    rechazo,
    nombre_rechazo,
    zona_call,
    zona_put,
    falsa_call,
    nombre_falsa_call,
    falsa_put,
    nombre_falsa_put,
    br_call,
    nombre_br_call,
    br_put,
    nombre_br_put,
    triple_soporte,
    triple_resistencia,
    entrada_pullback_call,
    entrada_pullback_put,
    micro,
    rsi
):
    senales_call = []
    senales_put = []

    if falsa_call == 1:
        senales_call.append(("falsa ruptura alcista", 5, nombre_falsa_call))

    if falsa_put == -1:
        senales_put.append(("falsa ruptura bajista", 5, nombre_falsa_put))

    if br_call == 1:
        senales_call.append(("breakout retest alcista", 4, nombre_br_call))

    if br_put == -1:
        senales_put.append(("breakout retest bajista", 4, nombre_br_put))

    if rechazo == 1 and zona_call:
        senales_call.append(("rechazo comprador en soporte", 4, nombre_rechazo))

    if rechazo == -1 and zona_put:
        senales_put.append(("rechazo vendedor en resistencia", 4, nombre_rechazo))

    if triple_soporte:
        senales_call.append(("triple rechazo en soporte", 3, "triple rechazo en soporte"))

    if triple_resistencia:
        senales_put.append(("triple rechazo en resistencia", 3, "triple rechazo en resistencia"))

    if entrada_pullback_call:
        senales_call.append(("pullback alcista", 3, "pullback válido para compra"))

    if entrada_pullback_put:
        senales_put.append(("pullback bajista", 3, "pullback válido para venta"))

    # Envolvente alcista queda más restringida porque te está perdiendo mucho
    if patron == 1 and zona_call and rechazo == 1 and rsi <= 55:
        senales_call.append(("envolvente alcista confirmada", 3, nombre_patron))

    if patron == -1 and zona_put and rechazo == -1 and rsi >= 45:
        senales_put.append(("envolvente bajista confirmada", 3, nombre_patron))

    if patron == 1 and "pin bar" in nombre_patron and zona_call:
        senales_call.append(("pin bar alcista", 4, nombre_patron))

    if patron == -1 and "pin bar" in nombre_patron and zona_put:
        senales_put.append(("pin bar bajista", 4, nombre_patron))

    if patron == 1 and "martillo" in nombre_patron and zona_call:
        senales_call.append(("martillo alcista", 4, nombre_patron))

    if patron == -1 and "shooting star" in nombre_patron and zona_put:
        senales_put.append(("shooting star bajista", 4, nombre_patron))

    if micro == 1 and zona_call and 42 <= rsi <= 58:
        senales_call.append(("micro tendencia alcista en zona", 2, "micro tendencia alcista"))

    if micro == -1 and zona_put and 42 <= rsi <= 58:
        senales_put.append(("micro tendencia bajista en zona", 2, "micro tendencia bajista"))

    return senales_call, senales_put
def confirmacion_suficiente(opens, closes, highs, lows, direccion, patron, rechazo):
    o = opens[-1]
    c = closes[-1]
    h = highs[-1]
    l = lows[-1]

    rango = h - l
    cuerpo = abs(c - o)

    if rango == 0:
        return False

    fuerza = cuerpo / rango
    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l

    if direccion == "call":
        if c > o and fuerza >= 0.35:
            return True

        if rechazo == 1 and mecha_inf >= cuerpo * 1.8:
            return True

        if patron == 1 and fuerza >= 0.30:
            return True

    if direccion == "put":
        if c < o and fuerza >= 0.35:
            return True

        if rechazo == -1 and mecha_sup >= cuerpo * 1.8:
            return True

        if patron == -1 and fuerza >= 0.30:
            return True

    return False
    
def analizar_activo(activo):
    data = obtener_velas(activo)

    if data is None:
        return None

    opens = data["open"]
    closes = data["close"]
    highs = data["high"]
    lows = data["low"]

    price = closes[-1]
    rsi = calcular_rsi(closes)

    if rsi is None:
        return None

    if rsi > 70 or rsi < 30:
        return None

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)

    tendencia = tendencia_regresion(closes, 80)
    estructura = estructura_mercado(highs, lows, 30)

    patron, nombre_patron, fuerza_patron = patron_price_action_avanzado(
        opens, closes, highs, lows
    )

    rechazo, nombre_rechazo = rechazo_real(opens, closes, highs, lows)

    vol = volatilidad(highs, lows, 14)

    if vol <= 0:
        return None

    soporte_zona, resistencia_zona = soporte_resistencia_zonas(
        price, highs, lows, vol
    )

    soporte = soporte_zona["precio"]
    resistencia = resistencia_zona["precio"]

    bb_superior, bb_media, bb_inferior = bollinger_bands(closes, 20, 2)

    if bb_superior is None:
        return None

    distancia_ema = abs(price - ema21)

    if distancia_ema > vol * 4:
        return None

    cerca_soporte = abs(price - soporte) <= soporte_zona["tolerancia"] * 1.8
    cerca_resistencia = abs(resistencia - price) <= resistencia_zona["tolerancia"] * 1.8

    cerca_banda_inferior = price <= bb_inferior + (vol * 1.1)
    cerca_banda_superior = price >= bb_superior - (vol * 1.1)

    triple_soporte = triple_rechazo(highs, lows, soporte_zona, "soporte", 25)
    triple_resistencia = triple_rechazo(highs, lows, resistencia_zona, "resistencia", 25)

    falsa_call, nombre_falsa_call = falsa_ruptura(
        opens, closes, highs, lows, soporte_zona, "soporte"
    )

    falsa_put, nombre_falsa_put = falsa_ruptura(
        opens, closes, highs, lows, resistencia_zona, "resistencia"
    )

    br_call, nombre_br_call = breakout_retest(
        opens, closes, highs, lows, resistencia_zona, "resistencia"
    )

    br_put, nombre_br_put = breakout_retest(
        opens, closes, highs, lows, soporte_zona, "soporte"
    )

    zona_call = (
        cerca_soporte
        or cerca_banda_inferior
        or triple_soporte
        or falsa_call == 1
        or br_call == 1
    )

    zona_put = (
        cerca_resistencia
        or cerca_banda_superior
        or triple_resistencia
        or falsa_put == -1
        or br_put == -1
    )

    extension = movimiento_extendido(opens, closes, 5)
    micro = micro_tendencia(opens, closes, 6)

    entrada_pullback_call = entrada_pullback(
        "call", price, ema21, soporte, resistencia, vol, patron, rechazo
    )

    entrada_pullback_put = entrada_pullback(
        "put", price, ema21, soporte, resistencia, vol, patron, rechazo
    )

    if falsa_call == 1 and tendencia == -1 and estructura == -1:
        falsa_call = 0

    if falsa_put == -1 and tendencia == 1 and estructura == 1:
        falsa_put = 0

    senales_call, senales_put = detectar_estrategias_price_action(
        patron,
        nombre_patron,
        rechazo,
        nombre_rechazo,
        zona_call,
        zona_put,
        falsa_call,
        nombre_falsa_call,
        falsa_put,
        nombre_falsa_put,
        br_call,
        nombre_br_call,
        br_put,
        nombre_br_put,
        triple_soporte,
        triple_resistencia,
        entrada_pullback_call,
        entrada_pullback_put,
        micro,
        rsi
    )

    # Entrada por zona aunque no haya patrón fuerte
    if zona_call and 38 <= rsi <= 58 and tendencia >= 0:
        senales_call.append(("zona compra", 4, "zona de compra con RSI válido"))

    if zona_put and 42 <= rsi <= 62 and tendencia <= 0:
        senales_put.append(("zona venta", 4, "zona de venta con RSI válido"))

    # Rechazo real aunque el patrón principal diga sin patrón
    if rechazo == 1 and zona_call:
        senales_call.append(("rechazo alcista", 4, nombre_rechazo))

    if rechazo == -1 and zona_put:
        senales_put.append(("rechazo bajista", 4, nombre_rechazo))

    if not senales_call and not senales_put:
        return None

    # No perseguir precio extendido
    if extension == 1:
        senales_call = []

    if extension == -1:
        senales_put = []

    # No comprar en resistencia ni vender en soporte
    if cerca_resistencia or cerca_banda_superior:
        senales_call = []

    if cerca_soporte or cerca_banda_inferior:
        senales_put = []

    if not senales_call and not senales_put:
        return None

    call_valido, razon_call_contexto = contexto_operacion(
        "call", tendencia, estructura, patron, rechazo, zona_call, zona_put, rsi, extension
    )

    put_valido, razon_put_contexto = contexto_operacion(
        "put", tendencia, estructura, patron, rechazo, zona_call, zona_put, rsi, extension
    )

    puntaje_call = 0
    puntaje_put = 0

    razones_call = []
    razones_put = []

    for nombre, puntos, razon in senales_call:
        puntaje_call += puntos
        razones_call.append(razon)

    for nombre, puntos, razon in senales_put:
        puntaje_put += puntos
        razones_put.append(razon)

    if tendencia == 1:
        puntaje_call += 2
        razones_call.append("tendencia alcista")

    if tendencia == -1:
        puntaje_put += 2
        razones_put.append("tendencia bajista")

    if estructura == 1:
        puntaje_call += 1
        razones_call.append("estructura alcista")

    if estructura == -1:
        puntaje_put += 1
        razones_put.append("estructura bajista")

    if ema9 > ema21:
        puntaje_call += 1
        razones_call.append("EMA favorece compra")

    if ema9 < ema21:
        puntaje_put += 1
        razones_put.append("EMA favorece venta")

    if 40 <= rsi <= 60:
        puntaje_call += 1
        puntaje_put += 1

    puntaje_call = ajustar_por_memoria(activo, nombre_patron, puntaje_call)
    puntaje_put = ajustar_por_memoria(activo, nombre_patron, puntaje_put)

    if (
        call_valido
        and senales_call
        and puntaje_call >= puntaje_minimo
        and puntaje_call > puntaje_put
    ):
        razones_call.append(razon_call_contexto)

        return {
            "activo": activo,
            "direccion": "call",
            "puntaje": puntaje_call,
            "patron": razones_call[0],
            "rsi": round(rsi, 2),
            "razon": ", ".join(razones_call)
        }

    if (
        put_valido
        and senales_put
        and puntaje_put >= puntaje_minimo
        and puntaje_put > puntaje_call
    ):
        razones_put.append(razon_put_contexto)

        return {
            "activo": activo,
            "direccion": "put",
            "puntaje": puntaje_put,
            "patron": razones_put[0],
            "rsi": round(rsi, 2),
            "razon": ", ".join(razones_put)
        }

    return None
def revisar_operaciones_abiertas():
    global operaciones_abiertas

    if not operaciones_abiertas:
        return

    pendientes = []

    for op in operaciones_abiertas:
        tiempo_abierta = time.time() - op["hora_apertura"]
        tiempo_cierre = (tiempo_expiracion * 60) + 15

        if tiempo_abierta < tiempo_cierre:
            pendientes.append(op)
            continue

        resultado = None

        try:
            if op["tipo"] in ["turbo", "binary"]:
                resultado = Iq.check_win_v3(op["order_id"])

            elif op["tipo"] == "digital":
                for _ in range(25):
                    check, win = Iq.check_win_digital_v2(op["order_id"])

                    if check:
                        resultado = win
                        break

                    time.sleep(0.5)

        except Exception as e:
            print("Error revisando resultado:", op["activo"], op["tipo"], e)

        if resultado is None:
            resultado = Iq.get_balance() - op["balance_antes"]

        data_historial = {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "activo": op["activo"],
            "tipo": op["tipo"],
            "direccion": op["direccion"],
            "puntaje": op["puntaje"],
            "patron": op["patron"],
            "rsi": op["rsi"],
            "resultado": round(resultado, 2)
        }

        print("Guardando historial:", data_historial)
        guardar_historial(data_historial)

        print("OPERACIÓN CERRADA:", op["activo"], op["tipo"], op["direccion"])
        print("Resultado:", round(resultado, 2))

    operaciones_abiertas = pendientes
def abrir_operacion(senal):
    activo = senal["activo"]
    direccion = senal["direccion"]
    tipo = senal.get("tipo", "turbo")

    try:
        balance_antes = Iq.get_balance()

        if tipo in ["turbo", "binary"]:
            check, order_id = Iq.buy(
                monto_base,
                activo,
                direccion,
                tiempo_expiracion
            )

        elif tipo == "digital":
            check, order_id = Iq.buy_digital_spot_v2(
                activo,
                monto_base,
                direccion,
                tiempo_expiracion
            )
        else:
            print("Tipo no soportado:", tipo)
            return False

        if not check:
            print("Operación rechazada:", activo, tipo)
            cooldown_activos[activo] = time.time()
            return False

        op = {
            "order_id": order_id,
            "activo": activo,
            "tipo": tipo,
            "direccion": direccion,
            "puntaje": senal["puntaje"],
            "patron": senal["patron"],
            "rsi": senal["rsi"],
            "razon": senal["razon"],
            "hora_apertura": time.time(),
            "balance_antes": balance_antes
        }

        operaciones_abiertas.append(op)

        print("OPERACIÓN ABIERTA:", activo, tipo, direccion)
        print("ID:", order_id)
        print("Operaciones abiertas:", len(operaciones_abiertas))

        cooldown_activos[activo] = time.time()
        return True

    except Exception as e:
        print("Error abriendo operación:", activo, tipo, e)
        cooldown_activos[activo] = time.time()
        return False
while True:
    revisar_operaciones_abiertas()

    if not Iq.check_connect():
        print("Reconectando...")

        try:
            Iq.connect()
        except Exception:
            pass

        time.sleep(5)
        continue

    balance_actual = Iq.get_balance()
    ganancia_neta = balance_actual - balance_inicial

    print("\nBalance actual:", balance_actual)
    print("Ganancia neta:", round(ganancia_neta, 2))
    print("Operaciones abiertas:", len(operaciones_abiertas))

    if ganancia_neta <= stop_loss:
        print("Stop loss alcanzado. Bot detenido.")
        break

    if len(operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
        print("Límite de operaciones abiertas alcanzado. Esperando cierre...")
        time.sleep(2)
        continue

    segundo = segundo_actual()

    if not (50 <= segundo <= 56):
        time.sleep(1)
        continue

    print("\nAnalizando mercado para próxima vela...")

    activos = obtener_activos()

    print("Activos compatibles:", len(activos))

    senales = []

    for item in activos:
        try:
            activo = item["activo"]
            tipo = item["tipo"]

            ya_abierto = any(op["activo"] == activo for op in operaciones_abiertas)

            if ya_abierto:
                continue

            senal = analizar_activo(activo)

            if senal is not None:
                senal["tipo"] = tipo
                senales.append(senal)

        except Exception as e:
            print("Error analizando", item, e)

    print("Señales preparadas:", len(senales))

    for s in senales[:5]:
        print(
            s["activo"],
            s["tipo"],
            s["direccion"],
            "puntaje:", s["puntaje"],
            "| patrón:", s["patron"],
            "| RSI:", s["rsi"]
        )

    if not senales:
        time.sleep(1)
        continue

    senales = sorted(
        senales,
        key=lambda x: x["puntaje"],
        reverse=True
    )

    print("Esperando apertura de próxima vela...")

    if not esperar_inicio_vela():
        print("Se perdió la zona de entrada.")
        continue

    abiertas_ahora = 0

    for senal in senales:
        if len(operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
            break

        activo_ya_abierto = any(op["activo"] == senal["activo"] for op in operaciones_abiertas)

        if activo_ya_abierto:
            continue

        if abrir_operacion(senal):
            abiertas_ahora += 1

        time.sleep(0.3)

    print("Operaciones abiertas en esta ronda:", abiertas_ahora)

    time.sleep(1)