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


def precargar_velas_activos(
    activos,
    podar_cache=True,
):
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
    presupuesto_precarga_d76d = 8.0

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

    # Evitar crecimiento indefinido del buffer
    # únicamente cuando trabajamos con el TOP
    # oficialmente publicado.
    #
    # Durante la preparación de un TOP pendiente
    # conservamos también los buffers del TOP actual.
    if podar_cache:
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

        demora_precarga_d76d = (
            time.perf_counter()
            - inicio_precarga
        )

        if (
            demora_precarga_d76d
            >= presupuesto_precarga_d76d
        ):
            print(
                "D7.6D BUFFER PRECARGA "
                "INTERRUMPIDA POR PRESUPUESTO |",
                "demora:",
                round(
                    demora_precarga_d76d,
                    3,
                ),
            )
            break

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
                timeout=1.5,
                drain_timeout=2.5,
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
            print(
                "D7.6D FALLO VELAS DETALLE | activo:",
                activo,
                "| causa: SIN_CONEXION",
                flush=True,
            )
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
            print(
                "D7.6D FALLO VELAS DETALLE | activo:",
                activo,
                "| causa: BUFFER_INSUFICIENTE",
                "| buffer:",
                len(buffer_actual),
                flush=True,
            )
            estado.fallo_velas_ronda_d76d = True
            return None

        inicio_get_candles_d76d = (
            time.perf_counter()
        )

        try:
            recientes = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                4,
                time.time(),
                timeout=1.5,
                drain_timeout=2.5,
            )

        finally:
            demora_get_candles_d76d = (
                time.perf_counter()
                - inicio_get_candles_d76d
            )

            if not hasattr(
                estado,
                "telemetria_get_candles_d76d",
            ):
                estado.telemetria_get_candles_d76d = {}

            estado.telemetria_get_candles_d76d[
                activo
            ] = demora_get_candles_d76d

        if recientes is None:
            print(
                "D7.6D FALLO VELAS DETALLE | activo:",
                activo,
                "| causa: GET_CANDLES_NONE",
                flush=True,
            )
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
            print(
                "D7.6D FALLO VELAS DETALLE | activo:",
                activo,
                "| causa: DESFASE_ULTIMA_CERRADA",
                "| ultima_buffer:",
                ultima_buffer,
                "| esperada:",
                ultima_esperada,
                "| delta:",
                ultima_buffer - ultima_esperada,
                "| ahora_iq:",
                round(ahora, 3),
                "| recientes:",
                [
                    int(float(c["from"]))
                    for c in recientes_cerradas[-4:]
                    if "from" in c
                ],
                flush=True,
            )
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


def evaluar_estabilidad_activo(
    asset,
    tipo,
    timeout_candles=0.75,
    drain_timeout_candles=0.25,
):
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
            time.time(),
            timeout=timeout_candles,
            drain_timeout=drain_timeout_candles,
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
def refrescar_activos_incremental():
    """
    D7.6D — refresh incremental del universo de activos.

    Regla:
    - la cache oficial sigue operando;
    - cada ventana de mantenimiento procesa una parte;
    - nunca se publica un TOP parcial;
    - solo al terminar TODO el universo se ordena y
      reemplaza estado.activos_cache de forma atomica.
    """

    presupuesto_refresh_d76d = 12.0

    inicio_ventana_d76d = (
        time.perf_counter()
    )

    cache_previa = list(
        getattr(
            estado,
            "activos_cache",
            [],
        )
        or []
    )

    # Sin cache oficial estamos en BOOTSTRAP.
    # El mismo scanner incremental construye el
    # primer universo sin publicar resultados parciales.

    def devolver_cache_oficial():
        cache_filtrada = [
            item
            for item in cache_previa
            if (
                item["activo"]
                not in estado.activos_invalidos
                and not activo_en_cooldown(
                    item["activo"]
                )
            )
        ]

        cache_filtrada = sorted(
            cache_filtrada,
            key=lambda x: x.get(
                "score_filtro",
                0,
            ),
            reverse=True,
        )

        estado.metricas_ronda[
            "uso_cache_activos"
        ] = 1

        estado.metricas_ronda[
            "compatibles_antes_top"
        ] = len(
            cache_filtrada
        )

        return cache_filtrada[
            :MAX_ACTIVOS_ANALIZAR
        ]

    def reset_refresh_incremental():
        estado.refresh_activos_en_progreso = (
            False
        )

        estado.refresh_activos_universo = []

        estado.refresh_activos_indice = 0

        estado.refresh_activos_candidatos = []

        estado.refresh_activos_vistos = set()

        estado.refresh_activos_inicio = 0.0

    # ==========================================
    # CONEXION
    # ==========================================
    try:
        conectado = (
            estado.Iq is not None
            and estado.Iq.check_connect()
        )
    except Exception:
        conectado = False

    if not conectado:
        reset_refresh_incremental()

        print(
            "D7.6D REFRESH INCREMENTAL "
            "ABORTADO POR DESCONEXION",
            flush=True,
        )

        return []
    # ==========================================
    # D7.6D — TOP PENDIENTE DE BUFFER
    # ==========================================
    #
    # Si el scanner completo ya terminó,
    # primero terminamos de preparar las velas
    # históricas del TOP nuevo.
    #
    # Mientras tanto, activos_cache sigue siendo
    # el TOP oficial anterior.
    #
    top_pendiente = list(
        getattr(
            estado,
            "refresh_activos_top_pendiente",
            [],
        )
        or []
    )

    if top_pendiente:

        precargar_velas_activos(
            top_pendiente,
            podar_cache=False,
        )

        nombres_pendientes = {
            item["activo"]
            for item in top_pendiente
            if (
                isinstance(item, dict)
                and item.get("activo")
            )
        }

        faltantes_buffer = [
            activo
            for activo in sorted(
                nombres_pendientes
            )
            if len(
                estado.velas_cache.get(
                    activo,
                    [],
                )
            ) < 130
        ]

        if faltantes_buffer:
            print(
                "D7.6D TOP PENDIENTE BUFFER |",
                "listos:",
                len(nombres_pendientes)
                - len(faltantes_buffer),
                "/",
                len(nombres_pendientes),
                "| faltantes:",
                len(faltantes_buffer),
            )

            return []

        # ==========================================
        # PUBLICACION ATOMICA REAL
        # ==========================================
        #
        # Solamente ahora el TOP nuevo puede
        # convertirse en el TOP oficial.
        #
        estado.activos_cache = list(
            top_pendiente
        )

        estado.ultima_actualizacion_activos = (
            time.time()
        )

        estado.refresh_activos_top_pendiente = []

        print(
            "D7.6D TOP NUEVO PUBLICADO CON BUFFER |",
            "top:",
            len(estado.activos_cache),
            "| buffers:",
            len(nombres_pendientes),
        )

        return list(
            estado.activos_cache
        )
    # ==========================================
    # INICIAR NUEVO CICLO
    # ==========================================
    if not getattr(
        estado,
        "refresh_activos_en_progreso",
        False,
    ):
        try:
            abiertos = (
                estado.Iq.get_all_open_time(
                    timeout=5.0
                )
            )

        except Exception as e:
            print(
                "D7.6D REFRESH INCREMENTAL "
                "OPEN_TIME FALLIDO |",
                e,
            )

            reset_refresh_incremental()

            return devolver_cache_oficial()

        try:
            conectado = (
                estado.Iq is not None
                and estado.Iq.check_connect()
            )
        except Exception:
            conectado = False

        if not conectado:
            reset_refresh_incremental()
            return []

        if not abiertos:
            print(
                "D7.6D REFRESH INCREMENTAL "
                "SIN OPEN_TIME | "
                "SE CONSERVA CACHE OFICIAL"
            )

            reset_refresh_incremental()

            return devolver_cache_oficial()

        universo = []

        # IMPORTANTE:
        # no hacemos deduplicacion aqui.
        #
        # obtener_activos() originalmente solo agrega
        # un activo a 'vistos' cuando supera el filtro.
        # Preservamos exactamente ese comportamiento.
        for tipo in TIPOS_MERCADO:

            mercados = abiertos.get(
                tipo,
                {},
            )

            for asset, info in mercados.items():

                if not info.get(
                    "open",
                    False,
                ):
                    continue

                universo.append({
                    "activo": asset,
                    "tipo": tipo,
                })

        if not universo:
            print(
                "D7.6D REFRESH INCREMENTAL "
                "UNIVERSO VACIO | "
                "SE CONSERVA CACHE OFICIAL"
            )

            reset_refresh_incremental()

            return devolver_cache_oficial()

        estado.refresh_activos_universo = (
            universo
        )

        estado.refresh_activos_indice = 0

        estado.refresh_activos_candidatos = []

        estado.refresh_activos_vistos = set()

        estado.refresh_activos_inicio = (
            time.time()
        )

        estado.refresh_activos_en_progreso = (
            True
        )

        print(
            "D7.6D REFRESH INCREMENTAL INICIADO |",
            "universo:",
            len(universo),
        )

    # ==========================================
    # CONTINUAR CICLO EXISTENTE
    # ==========================================
    universo = (
        estado.refresh_activos_universo
    )

    total_universo = len(
        universo
    )

    while (
        estado.refresh_activos_indice
        < total_universo
    ):
        demora = (
            time.perf_counter()
            - inicio_ventana_d76d
        )

        restante = (
            presupuesto_refresh_d76d
            - demora
        )

        # Dejamos margen para devolver el control
        # antes de consumir la vela siguiente.
        if restante <= 0.55:
            print(
                "D7.6D REFRESH INCREMENTAL PAUSADO |",
                "indice:",
                estado.refresh_activos_indice,
                "/",
                total_universo,
                "| candidatos:",
                len(
                    estado.refresh_activos_candidatos
                ),
                "| demora:",
                round(
                    demora,
                    3,
                ),
            )

            return devolver_cache_oficial()

        item = universo[
            estado.refresh_activos_indice
        ]

        # Marcamos esta posicion como procesada.
        estado.refresh_activos_indice += 1

        asset = item[
            "activo"
        ]

        tipo = item[
            "tipo"
        ]

        # ------------------------------------------
        # CONEXION ENTRE ACTIVOS
        # ------------------------------------------
        try:
            conectado = (
                estado.Iq is not None
                and estado.Iq.check_connect()
            )
        except Exception:
            conectado = False

        if not conectado:
            print(
                "D7.6D REFRESH INCREMENTAL "
                "ABORTADO DURANTE SCAN |",
                "indice:",
                estado.refresh_activos_indice,
                "/",
                total_universo,
            )

            reset_refresh_incremental()

            return []

        estado.metricas_ronda[
            "mercados_abiertos_recorridos"
        ] += 1

        # MISMA LOGICA DE 'vistos'
        # que obtener_activos().
        if (
            asset
            in estado.refresh_activos_vistos
        ):
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

        reserva_drenaje_d76d = 0.25

        presupuesto_candles_d76d = max(
            0.0,
            restante - 0.05,
        )

        timeout_activo_d76d = min(
            0.75,
            max(
                0.25,
                presupuesto_candles_d76d
                - reserva_drenaje_d76d,
            ),
        )

        drenaje_activo_d76d = min(
            2.5,
            max(
                reserva_drenaje_d76d,
                presupuesto_candles_d76d
                - timeout_activo_d76d,
            ),
        )

        try:
            evaluado = (
                evaluar_estabilidad_activo(
                    asset,
                    tipo,
                    timeout_candles=(
                        timeout_activo_d76d
                    ),
                    drain_timeout_candles=(
                        drenaje_activo_d76d
                    ),
                )
            )

        except ConnectionError:
            print(
                "D7.6D REFRESH INCREMENTAL "
                "ABORTADO POR CONEXION |",
                asset,
            )

            reset_refresh_incremental()

            return []

        if evaluado is None:
            estado.metricas_ronda[
                "descartados_sin_datos"
            ] += 1

            continue

        if (
            evaluado.get(
                "score_filtro",
                0,
            )
            < MIN_SCORE_ACTIVO
        ):
            estado.metricas_ronda[
                "descartados_score"
            ] += 1

            continue

        estado.refresh_activos_candidatos.append(
            evaluado
        )

        # Igual que el scanner original:
        # solo entra en vistos si fue aceptado.
        estado.refresh_activos_vistos.add(
            asset
        )

    # ==========================================
    # UNIVERSO COMPLETO
    # ==========================================
    candidatos = list(
        estado.refresh_activos_candidatos
    )

    candidatos = sorted(
        candidatos,
        key=lambda x: x.get(
            "score_filtro",
            0,
        ),
        reverse=True,
    )

    estado.metricas_ronda[
        "compatibles_antes_top"
    ] = len(
        candidatos
    )

    top_nuevo = candidatos[
        :MAX_ACTIVOS_ANALIZAR
    ]

    demora_ciclo = (
        time.time()
        - float(
            getattr(
                estado,
                "refresh_activos_inicio",
                time.time(),
            )
            or time.time()
        )
    )

    if top_nuevo:

        # ==========================================
        # D7.6D — TOP COMPLETO PENDIENTE DE BUFFER
        # ==========================================
        #
        # El universo terminó al 100%, pero todavía
        # NO publicamos el nuevo TOP.
        #
        # Primero deben existir buffers históricos
        # suficientes para TODOS sus activos.
        #
        estado.refresh_activos_top_pendiente = list(
            top_nuevo
        )

        print(
            "D7.6D REFRESH INCREMENTAL COMPLETO |",
            "universo:",
            total_universo,
            "| compatibles:",
            len(candidatos),
            "| top:",
            len(top_nuevo),
            "| ciclo:",
            round(
                demora_ciclo,
                2,
            ),
            "s",
            "| estado: PENDIENTE_BUFFER",
        )

        # No devolvemos todavía el TOP nuevo.
        # activos_cache continúa siendo el TOP
        # oficial anterior.
        resultado = []

    else:
        print(
            "D7.6D REFRESH INCREMENTAL COMPLETO "
            "SIN TOP VALIDO | "
            "SE CONSERVA CACHE OFICIAL"
        )

        resultado = devolver_cache_oficial()

    reset_refresh_incremental()

    return resultado

def obtener_activos(
    solo_cache=False,
):
    """
    Obtiene y ordena los mejores activos.

    Cambio de infraestructura:
    si IQ se desconecta durante la actualización,
    se aborta la ronda y se devuelve [] para que
    bot.py vuelva al inicio del while y reconecte.

    La selección y los scores permanecen iguales.
    """
    # ==========================================
    # D7.6D — PRESUPUESTO TOTAL DEL SCANNER
    # ==========================================
    #
    # Un refresh completo nunca puede apropiarse
    # de una vela completa.
    #
    # Si el presupuesto se agota:
    # - NO usamos universo parcial;
    # - NO actualizamos activos_cache;
    # - reutilizamos la última cache completa.
    #
    inicio_scan_d76d = (
        time.perf_counter()
    )

    cache_previa_d76d = list(
        getattr(
            estado,
            "activos_cache",
            [],
        )
        or []
    )
    # ==========================================
    # D7.6D — BOOTSTRAP TOP PENDIENTE DE BUFFER
    # ==========================================
    #
    # Si el scanner inicial ya calculó un TOP pero
    # todavía no existe cache oficial, NO repetimos
    # el scanner completo.
    #
    # Continuamos preparando exactamente ese TOP
    # hasta que todos sus activos tengan >=130 velas.
    top_pendiente_bootstrap_d76d = list(
        getattr(
            estado,
            "refresh_activos_top_pendiente",
            [],
        )
        or []
    )

    if (
        not cache_previa_d76d
        and top_pendiente_bootstrap_d76d
    ):
        nombres_pendientes_d76d = {
            item["activo"]
            for item in top_pendiente_bootstrap_d76d
            if (
                isinstance(item, dict)
                and item.get("activo")
            )
        }

        faltantes_buffer_d76d = [
            activo
            for activo in nombres_pendientes_d76d
            if len(
                getattr(
                    estado,
                    "velas_cache",
                    {},
                ).get(
                    activo,
                    [],
                )
            ) < 130
        ]

        # Solo cuando TODOS tienen buffer se publica.
        if not faltantes_buffer_d76d:
            estado.activos_cache = list(
                top_pendiente_bootstrap_d76d
            )

            estado.ultima_actualizacion_activos = (
                time.time()
            )

            estado.refresh_activos_top_pendiente = []

            print(
                "D7.6D BOOTSTRAP TOP PUBLICADO "
                "CON BUFFER |",
                "top:",
                len(estado.activos_cache),
                "| buffers:",
                len(nombres_pendientes_d76d),
            )

            return list(
                estado.activos_cache
            )

        # En ventana crítica nunca devolver un TOP
        # todavía incompleto.
        if solo_cache:
            return []

        print(
            "D7.6D BOOTSTRAP TOP PENDIENTE BUFFER |",
            "listos:",
            (
                len(nombres_pendientes_d76d)
                - len(faltantes_buffer_d76d)
            ),
            "/",
            len(nombres_pendientes_d76d),
            "| faltantes:",
            len(faltantes_buffer_d76d),
        )

        # Fuera de 0-10 bot.py puede seguir llamando
        # precargar_velas_activos() sobre este mismo TOP.
        return list(
            top_pendiente_bootstrap_d76d
        )
    # ==========================================
    # D7.6D — BOOTSTRAP VS REFRESH
    # ==========================================
    #
    # Sin cache previa BootIQ todavía no puede
    # operar, por lo que permitimos más tiempo
    # únicamente para construir el primer
    # universo COMPLETO.
    #
    # Una vez existe cache:
    # cualquier refresh vuelve al presupuesto
    # estricto de 12 segundos.
    #
    if cache_previa_d76d:
        presupuesto_scan_d76d = 12.0
    else:
        presupuesto_scan_d76d = 60.0

    def fallback_cache_scan_d76d(
        motivo
    ):
        print(
            "D7.6D SCANNER ABORTADO |",
            motivo,
            "| modo:",
            (
                "REFRESH"
                if cache_previa_d76d
                else "BOOTSTRAP"
            ),
            "| demora:",
            round(
                time.perf_counter()
                - inicio_scan_d76d,
                3,
            ),
            "| cache previa:",
            len(cache_previa_d76d),
        )

        estado.metricas_ronda[
            "uso_cache_activos"
        ] = 1

        estado.metricas_ronda[
            "fallback_cache_api"
        ] = 1

        cache_filtrada = [
            item
            for item
            in cache_previa_d76d
            if (
                item["activo"]
                not in estado.activos_invalidos
                and not activo_en_cooldown(
                    item["activo"]
                )
            )
        ]

        cache_filtrada = sorted(
            cache_filtrada,
            key=lambda x: x.get(
                "score_filtro",
                0,
            ),
            reverse=True,
        )

        estado.metricas_ronda[
            "compatibles_antes_top"
        ] = len(
            cache_filtrada
        )

        return cache_filtrada[
            :MAX_ACTIVOS_ANALIZAR
        ]
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
        estado.activos_cache
        and (
            solo_cache
            or (
                time.time()
                - estado.ultima_actualizacion_activos
                < 120
            )
        )
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
    # ==========================================
    # D7.6D — MODO SOLO CACHE
    # ==========================================
    #
    # Usado exclusivamente por la ventana
    # operativa 0-10.
    #
    # Si no existe cache, jamás iniciar scanner
    # desde la ventana crítica.
    #
    if solo_cache:
        return []
    activos = []
    vistos = set()

    # ==========================================
    # MERCADOS ABIERTOS
    # ==========================================
    try:
        abiertos = (
            estado.Iq.get_all_open_time(
                timeout=5.0
            )
        )

        # D7.6D — recuperación acotada solamente
        # durante cold-start.
        #
        # Si ya existe cache oficial, no hacemos
        # un segundo bloqueo de hasta 5 segundos:
        # se conserva la cache y el refresh podrá
        # intentarse posteriormente.
        binary_open_d76d = (
            abiertos.get("binary", {})
            if abiertos
            else {}
        )

        turbo_open_d76d = (
            abiertos.get("turbo", {})
            if abiertos
            else {}
        )

        open_time_util_d76d = bool(
            binary_open_d76d
            or turbo_open_d76d
        )

        if (
            not open_time_util_d76d
            and not getattr(
                estado,
                "activos_cache",
                [],
            )
        ):
            print(
                "D7.6D BOOTSTRAP OPEN_TIME "
                "REINTENTO | timeout: 5.0s"
            )

            time.sleep(0.20)

            abiertos = (
                estado.Iq.get_all_open_time(
                    timeout=5.0
                )
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

    demora_scan_d76d = (
        time.perf_counter()
        - inicio_scan_d76d
    )

    if (
        demora_scan_d76d
        >= presupuesto_scan_d76d
    ):
        return fallback_cache_scan_d76d(
            "PRESUPUESTO AGOTADO "
            "EN OPEN_TIME"
        )
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

            # ==========================================
            # D7.6D — PRESUPUESTO ANTES DE CADA ACTIVO
            # ==========================================
            demora_scan_d76d = (
                time.perf_counter()
                - inicio_scan_d76d
            )

            restante_scan_d76d = (
                presupuesto_scan_d76d
                - demora_scan_d76d
            )

            if restante_scan_d76d <= 0.55:
                return fallback_cache_scan_d76d(
                    "PRESUPUESTO TOTAL AGOTADO"
                )

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
                reserva_drenaje_d76d = 0.25

                presupuesto_candles_d76d = max(
                    0.0,
                    restante_scan_d76d - 0.05,
                )

                timeout_activo_d76d = min(
                    0.75,
                    max(
                        0.25,
                        presupuesto_candles_d76d
                        - reserva_drenaje_d76d,
                    ),
                )

                drenaje_activo_d76d = min(
                    2.5,
                    max(
                        reserva_drenaje_d76d,
                        presupuesto_candles_d76d
                        - timeout_activo_d76d,
                    ),
                )

                evaluado = (
                    evaluar_estabilidad_activo(
                        asset,
                        tipo,
                        timeout_candles=(
                            timeout_activo_d76d
                        ),
                        drain_timeout_candles=(
                            drenaje_activo_d76d
                        ),
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
    demora_scan_d76d = (
        time.perf_counter()
        - inicio_scan_d76d
    )

    if (
        demora_scan_d76d
        >= presupuesto_scan_d76d
    ):
        return fallback_cache_scan_d76d(
            "PRESUPUESTO AGOTADO "
            "AL FINAL DEL SCANNER"
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
        if not cache_previa_d76d:
            # Bootstrap:
            # el TOP ya está calculado, pero todavía
            # NO es operable hasta completar buffers.
            estado.refresh_activos_top_pendiente = (
                list(activos)
            )

            print(
                "D7.6D BOOTSTRAP TOP CALCULADO |",
                "top:",
                len(activos),
                "| estado: PENDIENTE_BUFFER",
            )

        else:
            # Mantener comportamiento existente aquí.
            estado.activos_cache = list(
                activos
            )

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
