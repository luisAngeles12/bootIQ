import time

import estado
from config import CANDLE_TIME, CANDLE_NUMBER, TIPOS_MERCADO
from utils import activo_en_cooldown
from conexion import reconectar_iq
from contexto_mercado import detectar_tipo_mercado, diagnostico_calidad_mercado, diagnostico_tendencia_avanzada

MAX_ACTIVOS_ANALIZAR =20
MIN_SCORE_ACTIVO = 65


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

        return None


def evaluar_estabilidad_activo(asset, tipo):
    try:
        candles = estado.Iq.get_candles(
            asset,
            CANDLE_TIME,
            120,
            time.time()
        )

        if not candles or len(candles) < 80:
            return None

        candles = sorted(candles, key=lambda x: x["from"])
        candles = candles[:-1]

        candles_contexto = []

        for c in candles:
            candles_contexto.append({
                "from": c["from"],
                "open": float(c["open"]),
                "close": float(c["close"]),
                "max": float(c["max"]),
                "min": float(c["min"])
            })

        tipo_mercado, razon_mercado = detectar_tipo_mercado(candles_contexto)
        diagnostico = diagnostico_calidad_mercado(candles_contexto)
        tendencia = diagnostico_tendencia_avanzada(candles_contexto)

        calidad = diagnostico.get("calidad", "SIN_DATOS")
        score = diagnostico.get("score", 0)

        estado_tendencia = tendencia.get("estado_tendencia", "INDEFINIDA")
        fuerza_tendencia = tendencia.get("fuerza_tendencia", 0)

        # =========================
        # FILTRO DURO DE ACTIVOS
        # =========================

        # Evitar activos tipo -op por ahora.
        # En tu reporte muchos -op entran pero no son los más estables.
        if "-op" in asset:
            return None

        # Evitar activos combinados tipo TESLA/FORD, GOOGLE/MSFT, etc.
        if "/" in asset:
            return None

        # Solo trabajar mercados limpios o normales.
        if calidad not in ["LIMPIO", "NORMAL"]:
            return None

        # Score mínimo real del diagnóstico de mercado.
        if score < 58:
            return None

        # Evitar mercados sin dirección clara.
        if estado_tendencia == "INDEFINIDA":
            return None

        # Evitar tendencias débiles.
        if "DEBIL" in estado_tendencia:
            return None

        # Evitar agotamiento como filtro inicial.
        # Si está agotada, puede servir para contra tendencia,
        # pero no para elegir los mejores activos base.
        if "AGOTADA" in estado_tendencia:
            return None

        # Evitar rangos sin tendencia fuerte/normal.
        if tipo_mercado == "RANGO" and "FUERTE" not in estado_tendencia and "NORMAL" not in estado_tendencia:
            return None

        # =========================
        # SCORE FINAL DE SELECCIÓN
        # =========================
        score_filtro = score

        if calidad == "LIMPIO":
            score_filtro += 25

        if calidad == "NORMAL":
            score_filtro += 15

        if "FUERTE" in estado_tendencia:
            score_filtro += 25

        if "NORMAL" in estado_tendencia:
            score_filtro += 15

        if tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]:
            score_filtro += 15

        if tipo_mercado == "RANGO":
            score_filtro -= 5

        # Premiar activos OTC simples.
        if "-OTC" in asset:
            score_filtro += 5

        return {
            "activo": asset,
            "tipo": tipo,
            "score_filtro": score_filtro,
            "tipo_mercado": tipo_mercado,
            "calidad_mercado": calidad,
            "score_mercado": score,
            "estado_tendencia": estado_tendencia,
            "fuerza_tendencia": fuerza_tendencia
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
            estado.activos_invalidos.add(asset)
            return None

        return None

def obtener_activos():
    # Usar caché reciente, pero siempre limitado y limpio.
    if time.time() - estado.ultima_actualizacion_activos < 300 and estado.activos_cache:
        activos_cache_filtrados = [
            item for item in estado.activos_cache
            if item["activo"] not in estado.activos_invalidos
            and not activo_en_cooldown(item["activo"])
        ]

        activos_cache_filtrados = sorted(
            activos_cache_filtrados,
            key=lambda x: x.get("score_filtro", 0),
            reverse=True
        )

        return activos_cache_filtrados[:MAX_ACTIVOS_ANALIZAR]

    activos = []
    vistos = set()

    try:
        abiertos = estado.Iq.get_all_open_time()
    except Exception as e:
        print("Error obteniendo mercados abiertos:", e)
        return estado.activos_cache[:MAX_ACTIVOS_ANALIZAR]

    for tipo in TIPOS_MERCADO:
        mercados = abiertos.get(tipo, {})

        for asset, info in mercados.items():
            if not info.get("open", False):
                continue

            if asset in vistos:
                continue

            if asset in estado.activos_invalidos:
                continue

            if activo_en_cooldown(asset):
                continue

            evaluado = evaluar_estabilidad_activo(asset, tipo)

            if evaluado is None:
                continue

            if evaluado.get("score_filtro", 0) < MIN_SCORE_ACTIVO:
                continue

            activos.append(evaluado)
            vistos.add(asset)

    activos = sorted(
        activos,
        key=lambda x: x.get("score_filtro", 0),
        reverse=True
    )

    activos = activos[:MAX_ACTIVOS_ANALIZAR]

    if activos:
        estado.activos_cache = activos
        estado.ultima_actualizacion_activos = time.time()

    print("Activos compatibles filtrados:", len(activos))
    print("Activos reales analizados:")

    for item in activos:
        print(
            item["activo"],
            "|",
            item.get("tipo", "N/A"),
            "| filtro:",
            item.get("score_filtro", 0),
            "| mercado:",
            item.get("tipo_mercado", "N/A"),
            "| calidad:",
            item.get("calidad_mercado", "N/A"),
            "| score mercado:",
            item.get("score_mercado", 0),
            "| tendencia:",
            item.get("estado_tendencia", "N/A"),
            "| fuerza:",
            round(item.get("fuerza_tendencia", 0), 2)
        )

    print("Activos ignorados/no soportados:", len(estado.activos_invalidos))

    return activos