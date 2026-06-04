import time
import estado
from config import CANDLE_TIME, CANDLE_NUMBER
from utils import activo_en_cooldown
from conexion import reconectar_iq

def obtener_velas(activo):

    try:
        if not estado.Iq.check_connect():
            reconectar_iq()
            return None

        candles = estado.Iq.get_candles(
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
            "low": [float(c["min"]) for c in candles],
        }

    except Exception as e:
        texto = str(e).lower()

        if (
            "need reconnect" in texto
            or "connection is already closed" in texto
            or "websocket" in texto
        ):
            reconectar_iq()
            return None

        if "not found" in texto or "consts" in texto:
            estado.activos_invalidos.add(activo)

        return None


def obtener_activos():

    if time.time() - estado.ultima_actualizacion_activos < 300 and estado.activos_cache:
        return [
            item for item in estado.activos_cache
            if item["activo"] not in estado.activos_invalidos
            and not activo_en_cooldown(item["activo"])
        ]

    activos = []
    vistos = set()

    activos_permitidos = [
        "EURUSD-OTC",
        "EURGBP-OTC",
        "EURJPY-OTC",
        "GBPUSD-OTC",
        "GBPJPY-OTC",
        "AUDCAD-OTC",
        "USDCHF-OTC",
        "USDHKD-OTC",
        "USDINR-OTC",
        "USDSGD-OTC",
        "USDZAR-OTC"
    ]

    for asset in activos_permitidos:
        try:
            if asset in vistos:
                continue

            if asset in estado.activos_invalidos:
                continue

            if activo_en_cooldown(asset):
                continue

            candles = estado.Iq.get_candles(
                asset,
                CANDLE_TIME,
                10,
                time.time()
            )

            if candles and len(candles) >= 5:
                activos.append({
                    "activo": asset,
                    "tipo": "turbo"
                })
                vistos.add(asset)

        except Exception as e:
            texto = str(e).lower()

            if (
                "need reconnect" in texto
                or "connection is already closed" in texto
                or "websocket" in texto
            ):
                reconectar_iq()
                return estado.activos_cache

            if "not found" in texto or "consts" in texto:
                estado.activos_invalidos.add(asset)

            continue

    if activos:
        estado.activos_cache = activos
        estado.ultima_actualizacion_activos = time.time()

    print("Activos OTC compatibles actualizados:", len(estado.activos_cache))

    return estado.activos_cache