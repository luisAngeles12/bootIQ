import time

import estado
from config import CANDLE_TIME, CANDLE_NUMBER, TIPOS_MERCADO
from utils import activo_en_cooldown
from conexion import reconectar_iq
from contexto_mercado import detectar_tipo_mercado, diagnostico_calidad_mercado, diagnostico_tendencia_avanzada

MAX_ACTIVOS_ANALIZAR = 20
MIN_SCORE_ACTIVO = 55


def obtener_velas(activo):
    """
    Obtiene las velas usadas por estrategia.py.

    Regla de conexión:
    - mercado.py NO reconecta;
    - si el websocket está caído, devuelve None;
    - bot.py será quien detecte la caída y llame reconectar_iq().
    """

    try:
        try:
            conectado = (
                estado.Iq is not None
                and estado.Iq.check_connect()
            )
        except Exception:
            conectado = False

        if not conectado:
            return None

        candles = estado.Iq.get_candles(
            activo,
            CANDLE_TIME,
            CANDLE_NUMBER,
            time.time()
        )

        # Si get_candles devolvió None porque la conexión
        # se perdió, no intentar ninguna reconexión aquí.
        if candles is None:
            return None

        if len(candles) < 130:
            return None

        candles = sorted(
            candles,
            key=lambda x: x["from"]
        )

        # Eliminar la vela todavía abierta.
        candles = candles[:-1]

        return {
            # PASO 5.5A — conservar el timestamp exacto
            # de cada vela cerrada analizada por estrategia.py.
            "from": [
                int(float(c["from"]))
                for c in candles
            ],
        
            "open": [
                float(c["open"])
                for c in candles
            ],
            "close": [
                float(c["close"])
                for c in candles
            ],
            "high": [
                float(c["max"])
                for c in candles
            ],
            "low": [
                float(c["min"])
                for c in candles
            ],
        }

    except Exception as e:
        texto = str(e).lower()

        # Una caída de conexión no convierte el activo
        # en inválido y tampoco se reconecta desde aquí.
        if (
            "need reconnect" in texto
            or "connection is already closed" in texto
            or "websocket" in texto
            or "connection" in texto
        ):
            return None

        if (
            "not found" in texto
            or "consts" in texto
        ):
            estado.activos_invalidos.add(
                activo
            )
            return None

        return None


def evaluar_estabilidad_activo(asset, tipo):
    """
    Evalúa un activo para el filtro inicial.

    Si el websocket se pierde durante el scanner:
    - lanza ConnectionError;
    - obtener_activos() aborta toda la ronda;
    - bot.py recupera el control y reconecta.

    NO cambia:
    - filtros;
    - scores;
    - tendencia;
    - calidad;
    - ranking de activos.
    """

    try:
        # ------------------------------------------
        # CONEXIÓN ANTES DE PEDIR VELAS
        # ------------------------------------------
        try:
            conectado = (
                estado.Iq is not None
                and estado.Iq.check_connect()
            )
        except Exception:
            conectado = False

        if not conectado:
            raise ConnectionError(
                "IQ_DESCONECTADO_DURANTE_SCAN"
            )

        candles = estado.Iq.get_candles(
            asset,
            CANDLE_TIME,
            120,
            time.time()
        )

        # get_candles puede devolver None tanto por un
        # timeout puntual como por una desconexión.
        # Solo abortamos todo el scanner si realmente
        # el websocket quedó desconectado.
        if candles is None:
            try:
                conectado = (
                    estado.Iq is not None
                    and estado.Iq.check_connect()
                )
            except Exception:
                conectado = False

            if not conectado:
                raise ConnectionError(
                    "IQ_DESCONECTADO_DURANTE_SCAN"
                )

            # Timeout/dato no disponible, pero websocket vivo:
            # simplemente este activo no participa en esta ronda.
            return None

        if len(candles) < 80:
            return None

        candles = sorted(
            candles,
            key=lambda x: x["from"]
        )

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

        tipo_mercado, razon_mercado = (
            detectar_tipo_mercado(
                candles_contexto
            )
        )

        diagnostico = (
            diagnostico_calidad_mercado(
                candles_contexto
            )
        )

        tendencia = (
            diagnostico_tendencia_avanzada(
                candles_contexto
            )
        )

        calidad = diagnostico.get(
            "calidad",
            "SIN_DATOS"
        )

        score = diagnostico.get(
            "score",
            0
        )

        estado_tendencia = tendencia.get(
            "estado_tendencia",
            "INDEFINIDA"
        )

        fuerza_tendencia = tendencia.get(
            "fuerza_tendencia",
            0
        )

        # =========================
        # FILTRO DURO DE ACTIVOS
        # =========================

        # Evitar activos tipo -op por ahora.
        if "-op" in asset:
            return None

        # Evitar activos combinados.
        if "/" in asset:
            return None

        # Solo trabajar mercados limpios o normales.
        if calidad not in [
            "LIMPIO",
            "NORMAL"
        ]:
            return None

        # Score mínimo real del diagnóstico.
        if score < 52:
            return None

        # Evitar mercados sin dirección clara.
        if estado_tendencia == "INDEFINIDA":
            return None

        # Evitar tendencias débiles solo cuando
        # el score también es insuficiente.
        if (
            "DEBIL" in estado_tendencia
            and score < 62
        ):
            return None

        # Evitar rangos sin tendencia fuerte/normal.
        if (
            tipo_mercado == "RANGO"
            and "FUERTE" not in estado_tendencia
            and "NORMAL" not in estado_tendencia
        ):
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

        if tipo_mercado in [
            "TENDENCIA_ALCISTA",
            "TENDENCIA_BAJISTA"
        ]:
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

    except ConnectionError:
        # MUY IMPORTANTE:
        # no convertir la desconexión en "activo malo".
        # Se propaga para abortar obtener_activos().
        raise

    except Exception as e:
        texto = str(e).lower()

        if (
            "need reconnect" in texto
            or "connection is already closed" in texto
            or "websocket" in texto
            or "connection" in texto
        ):
            raise ConnectionError(
                "IQ_DESCONECTADO_DURANTE_SCAN"
            ) from e

        if (
            "not found" in texto
            or "consts" in texto
        ):
            estado.activos_invalidos.add(
                asset
            )
            return None

        return None


def obtener_activos():
    """
    Obtiene y ordena los mejores activos.

    Cambio de infraestructura:
    si IQ se desconecta durante la actualización,
    se aborta la ronda y se devuelve [] para que
    bot.py vuelva al inicio del while y reconecte.

    La selección y los scores permanecen iguales.
    """

    # ==========================================
    # NO ESCANEAR CON WEBSOCKET CAÍDO
    # ==========================================
    try:
        conectado = (
            estado.Iq is not None
            and estado.Iq.check_connect()
        )
    except Exception:
        conectado = False

    if not conectado:
        print(
            "ESCANEO DE ACTIVOS ABORTADO: "
            "IQ Option está desconectado.",
            flush=True
        )
        return []

    # ==========================================
    # CACHÉ RECIENTE
    # ==========================================
    if (
        time.time()
        - estado.ultima_actualizacion_activos
        < 300
        and estado.activos_cache
    ):
        activos_cache_filtrados = [
            item
            for item in estado.activos_cache
            if (
                item["activo"]
                not in estado.activos_invalidos
                and not activo_en_cooldown(
                    item["activo"]
                )
            )
        ]

        activos_cache_filtrados = sorted(
            activos_cache_filtrados,
            key=lambda x: x.get(
                "score_filtro",
                0
            ),
            reverse=True
        )

        return activos_cache_filtrados[
            :MAX_ACTIVOS_ANALIZAR
        ]

    activos = []
    vistos = set()

    # ==========================================
    # MERCADOS ABIERTOS
    # ==========================================
    try:
        abiertos = (
            estado.Iq.get_all_open_time()
        )

    except Exception as e:
        print(
            "Error obteniendo mercados abiertos:",
            e
        )

        try:
            conectado = (
                estado.Iq is not None
                and estado.Iq.check_connect()
            )
        except Exception:
            conectado = False

        if not conectado:
            print(
                "ESCANEO ABORTADO POR "
                "DESCONEXIÓN DE IQ OPTION.",
                flush=True
            )
            return []

        # Si la conexión sigue viva pero la consulta
        # puntual falló, conservar la caché conocida.
        return estado.activos_cache[
            :MAX_ACTIVOS_ANALIZAR
        ]

    # get_all_open_time puede devolver estructura vacía
    # después de un timeout. Primero confirmar que la
    # conexión siga realmente viva.
    try:
        conectado = (
            estado.Iq is not None
            and estado.Iq.check_connect()
        )
    except Exception:
        conectado = False

    if not conectado:
        print(
            "ESCANEO ABORTADO: conexión perdida "
            "al consultar mercados abiertos.",
            flush=True
        )
        return []

    if not abiertos:
        return estado.activos_cache[
            :MAX_ACTIVOS_ANALIZAR
        ]

    # ==========================================
    # EVALUAR ACTIVOS
    # ==========================================
    for tipo in TIPOS_MERCADO:

        mercados = abiertos.get(
            tipo,
            {}
        )

        for asset, info in mercados.items():

            # Si el websocket murió entre dos activos,
            # cortar inmediatamente. No llamar
            # get_candles decenas de veces desconectado.
            try:
                conectado = (
                    estado.Iq is not None
                    and estado.Iq.check_connect()
                )
            except Exception:
                conectado = False

            if not conectado:
                print(
                    "ESCANEO ABORTADO DURANTE FILTRO "
                    "DE ACTIVOS: conexión IQ perdida.",
                    flush=True
                )
                return []

            if not info.get(
                "open",
                False
            ):
                continue

            if asset in vistos:
                continue

            if (
                asset
                in estado.activos_invalidos
            ):
                continue

            if activo_en_cooldown(
                asset
            ):
                continue

            try:
                evaluado = (
                    evaluar_estabilidad_activo(
                        asset,
                        tipo
                    )
                )

            except ConnectionError:
                print(
                    "ESCANEO ABORTADO DURANTE "
                    "get_candles: conexión IQ perdida.",
                    flush=True
                )
                return []

            if evaluado is None:
                continue

            if (
                evaluado.get(
                    "score_filtro",
                    0
                )
                < MIN_SCORE_ACTIVO
            ):
                continue

            activos.append(
                evaluado
            )

            vistos.add(
                asset
            )

    # ==========================================
    # MISMO RANKING / MISMO TOP 20
    # ==========================================
    activos = sorted(
        activos,
        key=lambda x: x.get(
            "score_filtro",
            0
        ),
        reverse=True
    )

    activos = activos[
        :MAX_ACTIVOS_ANALIZAR
    ]

    if activos:
        estado.activos_cache = activos
        estado.ultima_actualizacion_activos = (
            time.time()
        )

    print(
        "Activos compatibles filtrados:",
        len(activos)
    )

    print(
        "Activos reales analizados:"
    )

    for item in activos:
        print(
            item["activo"],
            "|",
            item.get(
                "tipo",
                "N/A"
            ),
            "| filtro:",
            item.get(
                "score_filtro",
                0
            ),
            "| mercado:",
            item.get(
                "tipo_mercado",
                "N/A"
            ),
            "| calidad:",
            item.get(
                "calidad_mercado",
                "N/A"
            ),
            "| score mercado:",
            item.get(
                "score_mercado",
                0
            ),
            "| tendencia:",
            item.get(
                "estado_tendencia",
                "N/A"
            ),
            "| fuerza:",
            round(
                item.get(
                    "fuerza_tendencia",
                    0
                ),
                2
            )
        )

    print(
        "Activos ignorados/no soportados:",
        len(
            estado.activos_invalidos
        )
    )

    return activos