import time

import estado
from config import CANDLE_TIME, CANDLE_NUMBER, TIPOS_MERCADO
from utils import activo_en_cooldown
from conexion import reconectar_iq
from contexto_mercado import detectar_tipo_mercado, diagnostico_calidad_mercado, diagnostico_tendencia_avanzada

MAX_ACTIVOS_ANALIZAR = 20
MIN_SCORE_ACTIVO = 55


def _timestamp_servidor_iq():
    """
    Timestamp de referencia para decidir qué velas
    están realmente cerradas.
    """
    try:
        ts = estado.Iq.get_server_timestamp()
        ts = float(ts)

        # Protección por si alguna versión devuelve ms.
        if ts > 10_000_000_000:
            ts /= 1000.0

        return ts

    except Exception:
        return time.time()


def _solo_velas_cerradas(candles):
    """
    Conserva únicamente periodos realmente cerrados.

    D7.6C:
    no dependemos de borrar ciegamente candles[-1].
    La vela cuyo 'from' coincide con el periodo actual
    todavía está abierta y se excluye.
    """
    if not candles:
        return []

    ahora = _timestamp_servidor_iq()

    inicio_vela_actual = (
        int(ahora // CANDLE_TIME)
        * CANDLE_TIME
    )

    cerradas = []

    for c in candles:
        try:
            desde = int(float(c["from"]))

            if desde >= inicio_vela_actual:
                continue

            cerradas.append(c)

        except Exception:
            continue

    cerradas = sorted(
        cerradas,
        key=lambda x: int(float(x["from"]))
    )

    return cerradas


def _datos_desde_velas(candles):
    if not candles or len(candles) < 130:
        return None

    return {
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


def precargar_velas_activos(activos):
    """
    D7.6C — carga pesada FUERA de 0-10.

    Cada activo nuevo recibe la misma profundidad que
    usaba LIVE originalmente:

        CANDLE_NUMBER = 3000 solicitadas
        -> aproximadamente 2999 cerradas.

    Los activos ya precargados no vuelven a descargar
    las 3000 velas.
    """
    if not hasattr(estado, "velas_cache"):
        estado.velas_cache = {}

    if not activos:
        return {
            "nuevos": 0,
            "reutilizados": 0,
            "errores": 0,
        }

    inicio_precarga = time.perf_counter()

    nombres_actuales = set()

    for item in activos:
        try:
            if isinstance(item, dict):
                activo = item.get("activo")
            else:
                activo = str(item)

            if activo:
                nombres_actuales.add(activo)

        except Exception:
            pass

    # Evitar crecimiento indefinido del buffer.
    estado.velas_cache = {
        activo: velas
        for activo, velas
        in estado.velas_cache.items()
        if activo in nombres_actuales
    }

    nuevos = 0
    reutilizados = 0
    errores = 0

    objetivo_cerradas = max(
        130,
        CANDLE_NUMBER - 1,
    )

    for activo in sorted(nombres_actuales):
        existentes = estado.velas_cache.get(
            activo,
            [],
        )

        if len(existentes) >= 130:
            reutilizados += 1
            continue

        try:
            conectado = (
                estado.Iq is not None
                and estado.Iq.check_connect()
            )

            if not conectado:
                errores += 1
                continue

            candles = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                CANDLE_NUMBER,
                time.time(),
            )

            cerradas = _solo_velas_cerradas(
                candles
            )

            if len(cerradas) < 130:
                errores += 1
                continue

            estado.velas_cache[activo] = (
                cerradas[-objetivo_cerradas:]
            )

            nuevos += 1

        except Exception:
            errores += 1

    demora = (
        time.perf_counter()
        - inicio_precarga
    )

    print(
        "D7.6C BUFFER VELAS PRECALENTADO |",
        "nuevos:", nuevos,
        "| reutilizados:", reutilizados,
        "| errores:", errores,
        "| activos buffer:",
        len(estado.velas_cache),
        "| segundos:",
        round(demora, 3),
    )

    return {
        "nuevos": nuevos,
        "reutilizados": reutilizados,
        "errores": errores,
    }


def obtener_velas(activo):
    """
    D7.6C — LIVE incremental.

    Dentro de la ventana operativa no descarga 3000
    velas nuevamente.

    Usa:
        buffer histórico de ~2999 cerradas
        +
        4 velas recientes de IQ.

    Después fusiona por timestamp y vuelve a conservar
    exactamente la misma profundidad histórica.
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
            estado.fallo_velas_ronda_d76d = True
            return None

        if not hasattr(estado, "velas_cache"):
            estado.velas_cache = {}

        buffer_actual = estado.velas_cache.get(
            activo,
            [],
        )

        # Regla D7.6C:
        # la descarga pesada debe haber ocurrido antes
        # mediante precargar_velas_activos().
        if len(buffer_actual) < 130:
            estado.fallo_velas_ronda_d76d = True
            return None

        recientes = estado.Iq.get_candles(
            activo,
            CANDLE_TIME,
            4,
            time.time(),
            timeout=1.5,
        )

        if recientes is None:
            estado.fallo_velas_ronda_d76d = True
            return None

        recientes_cerradas = (
            _solo_velas_cerradas(recientes)
        )

        # Fusionar sin duplicar timestamps.
        por_timestamp = {}

        for c in buffer_actual:
            try:
                por_timestamp[
                    int(float(c["from"]))
                ] = c
            except Exception:
                continue

        for c in recientes_cerradas:
            try:
                por_timestamp[
                    int(float(c["from"]))
                ] = c
            except Exception:
                continue

        fusionadas = [
            por_timestamp[k]
            for k in sorted(por_timestamp)
        ]

        objetivo_cerradas = max(
            130,
            CANDLE_NUMBER - 1,
        )

        fusionadas = fusionadas[
            -objetivo_cerradas:
        ]

        if len(fusionadas) < 130:
            return None

        # ------------------------------------------------
        # PARIDAD TEMPORAL
        # ------------------------------------------------
        ahora = _timestamp_servidor_iq()

        inicio_actual = (
            int(ahora // CANDLE_TIME)
            * CANDLE_TIME
        )

        ultima_esperada = (
            inicio_actual
            - CANDLE_TIME
        )

        ultima_buffer = int(
            float(
                fusionadas[-1]["from"]
            )
        )

        # Nunca analizar una vela vieja como si fuese
        # la última cerrada.
        if ultima_buffer != ultima_esperada:
            estado.fallo_velas_ronda_d76d = True
            return None

        estado.velas_cache[activo] = fusionadas

        return _datos_desde_velas(
            fusionadas
        )

    except Exception as e:
        texto = str(e).lower()

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

            # Timeout/dato no disponible, pero websocket vivo.
            estado.metricas_ronda[
                "scan_candles_none"
            ] += 1

            return None

        if len(candles) < 80:
            estado.metricas_ronda[
                "scan_velas_insuficientes"
            ] += 1
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
            estado.metricas_ronda[
                "scan_formato_op"
            ] += 1
            return None

        # Evitar activos combinados.
        if "/" in asset:
            estado.metricas_ronda[
                "scan_formato_combinado"
            ] += 1
            return None

        # Solo trabajar mercados limpios o normales.
        if calidad not in [
            "LIMPIO",
            "NORMAL"
        ]:
            estado.metricas_ronda[
                "scan_calidad"
            ] += 1
            return None

        # Score mínimo real del diagnóstico.
        if score < 52:
            estado.metricas_ronda[
                "scan_score"
            ] += 1
            return None

        # Evitar mercados sin dirección clara.
        if estado_tendencia == "INDEFINIDA":
            estado.metricas_ronda[
                "scan_tendencia_indefinida"
            ] += 1
            return None

        # Evitar tendencias débiles solo cuando
        # el score también es insuficiente.
        if (
            "DEBIL" in estado_tendencia
            and score < 62
        ):
            estado.metricas_ronda[
                "scan_tendencia_debil"
            ] += 1
            return None

        # Evitar rangos sin tendencia fuerte/normal.
        if (
            tipo_mercado == "RANGO"
            and "FUERTE" not in estado_tendencia
            and "NORMAL" not in estado_tendencia
        ):
            estado.metricas_ronda[
                "scan_rango_debil"
            ] += 1
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

            estado.metricas_ronda[
                "scan_invalido_api"
            ] += 1

            return None

        estado.metricas_ronda[
            "scan_excepcion"
        ] += 1

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
        < 120
        and estado.activos_cache
    ):
        estado.metricas_ronda[
            "uso_cache_activos"
        ] = 1

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

        estado.metricas_ronda[
            "compatibles_antes_top"
        ] = len(activos_cache_filtrados)

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
        estado.metricas_ronda[
            "uso_cache_activos"
        ] = 1

        estado.metricas_ronda[
            "fallback_cache_api"
        ] = 1

        estado.metricas_ronda[
            "compatibles_antes_top"
        ] = len(estado.activos_cache)

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
        estado.metricas_ronda[
            "uso_cache_activos"
        ] = 1

        estado.metricas_ronda[
            "fallback_cache_api"
        ] = 1

        estado.metricas_ronda[
            "compatibles_antes_top"
        ] = len(estado.activos_cache)

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

            estado.metricas_ronda[
                "mercados_abiertos_recorridos"
            ] += 1

            if asset in vistos:
                estado.metricas_ronda[
                    "duplicados_omitidos"
                ] += 1
                continue

            if (
                asset
                in estado.activos_invalidos
            ):
                estado.metricas_ronda[
                    "descartados_invalidos"
                ] += 1
                continue

            if activo_en_cooldown(
                asset
            ):
                estado.metricas_ronda[
                    "descartados_cooldown"
                ] += 1
                continue

            estado.metricas_ronda[
                "activos_evaluados_filtro"
            ] += 1

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
                estado.metricas_ronda[
                    "descartados_sin_datos"
                ] += 1
                continue

            if (
                evaluado.get(
                    "score_filtro",
                    0
                )
                < MIN_SCORE_ACTIVO
            ):
                estado.metricas_ronda[
                    "descartados_score"
                ] += 1
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

    estado.metricas_ronda[
        "compatibles_antes_top"
    ] = len(activos)

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