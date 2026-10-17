import time
import math
import estado
from config import CANDLE_TIME, TIEMPO_EXPIRACION


def segundo_actual():
    """
    Segundo actual de la vela usando IQ Option como reloj oficial.

    Fallback al reloj local únicamente si el timestamp
    del broker no está disponible.
    """

    try:
        if estado.Iq is not None:

            timestamp_iq = float(
                estado.Iq.get_server_timestamp()
            )

            if timestamp_iq > 0:
                return int(
                    timestamp_iq % 60
                )

    except Exception:
        pass

    return int(
        time.time() % 60
    )


def esperar_inicio_vela():
    while True:
        s = segundo_actual()

        if 0 <= s <= 3:
            return True

        if s > 56:
            time.sleep(0.05)
            continue

        return False


def _timestamp_iq_para_capacidad():
    try:
        if estado.Iq is not None:
            ts = float(
                estado.Iq.get_server_timestamp()
            )
            if ts > 10_000_000_000:
                ts /= 1000.0
            if ts > 0:
                return ts
    except Exception:
        pass

    return time.time()


def operacion_ocupa_slot(op, ahora_iq=None):
    """
    True únicamente mientras la posición sigue viva en IQ.

    Una operación puede permanecer en estado.operaciones_abiertas
    después de expirar mientras se recupera su resultado. Esa
    espera administrativa no debe consumir MAX_OPERACIONES_ABIERTAS.
    """
    if not isinstance(op, dict):
        return False

    if ahora_iq is None:
        ahora_iq = _timestamp_iq_para_capacidad()

    try:
        expiracion = float(
            op.get("expiracion_iq", 0)
            or 0
        )
    except Exception:
        expiracion = 0.0

    if expiracion <= 0:
        try:
            hora_apertura = float(
                op.get("hora_apertura", 0)
                or 0
            )

            duracion_buckets = max(
                1,
                int(
                    math.ceil(
                        (
                            float(TIEMPO_EXPIRACION)
                            * 60.0
                        )
                        / float(CANDLE_TIME)
                    )
                ),
            )

            bucket_apertura = int(
                hora_apertura
                // float(CANDLE_TIME)
            )

            expiracion = (
                bucket_apertura
                + duracion_buckets
            ) * float(CANDLE_TIME)

        except Exception:
            return True

    return float(ahora_iq) < expiracion


def contar_operaciones_activas():
    ahora_iq = _timestamp_iq_para_capacidad()

    return sum(
        1
        for op in estado.operaciones_abiertas
        if operacion_ocupa_slot(
            op,
            ahora_iq=ahora_iq,
        )
    )


def activo_con_operacion_activa(activo):
    ahora_iq = _timestamp_iq_para_capacidad()

    return any(
        str(op.get("activo", "")) == str(activo)
        and operacion_ocupa_slot(
            op,
            ahora_iq=ahora_iq,
        )
        for op in estado.operaciones_abiertas
        if isinstance(op, dict)
    )


def activo_en_cooldown(activo):
    if activo not in estado.cooldown_activos:
        return False

    if time.time() - estado.cooldown_activos[activo] > 20:
        del estado.cooldown_activos[activo]
        return False

    return True


def estrategia_en_cooldown(patron):
    if not hasattr(estado, "cooldown_estrategias"):
        estado.cooldown_estrategias = {}

    if patron not in estado.cooldown_estrategias:
        return False

    if time.time() >= estado.cooldown_estrategias[patron]:
        del estado.cooldown_estrategias[patron]
        return False

    return True

def registrar_bloqueo(motivo):
    import estado

    if not hasattr(estado, "metricas_ronda"):
        estado.metricas_ronda = {
            "mercados_analizados": 0,
            "uso_cache_activos": 0,
            "fallback_cache_api": 0,
            "mercados_abiertos_recorridos": 0,
            "duplicados_omitidos": 0,
            "descartados_invalidos": 0,
            "descartados_cooldown": 0,
            "activos_evaluados_filtro": 0,
            "descartados_sin_datos": 0,
            "scan_candles_none": 0,
            "scan_velas_insuficientes": 0,
            "scan_formato_op": 0,
            "scan_formato_combinado": 0,
            "scan_calidad": 0,
            "scan_score": 0,
            "scan_tendencia_indefinida": 0,
            "scan_tendencia_debil": 0,
            "scan_rango_debil": 0,
            "scan_invalido_api": 0,
            "scan_excepcion": 0,
            "descartados_score": 0,
            "compatibles_antes_top": 0,
            "senales_detectadas": 0,
            "activos_con_candidatas": 0,
            "candidatas_generadas": 0,
            "familias_generadas": {},
            "candidatas_evaluadas_cerebro": 0,
            "candidatas_que_continuan": 0,
            "senales_aprobadas": 0,
            "cerebro_no_operar": 0,
            "cerebro_sin_autorizacion": 0,
            "autorizadas_directa": 0,
            "autorizadas_protocolo": 0,
            "directas_no_ejecutadas": 0,
            "entradas_abiertas": 0,
            "bloqueos": {}
        }

    if motivo not in estado.metricas_ronda["bloqueos"]:
        estado.metricas_ronda["bloqueos"][motivo] = 0

    estado.metricas_ronda["bloqueos"][motivo] += 1


def imprimir_resumen_ronda(metricas=None):
    import estado
    if metricas is None:
        metricas = estado.metricas_ronda

    print("\n===== RESUMEN DE RONDA =====")
    mercados = metricas.get("mercados_analizados", 0)
    detectadas = metricas.get("senales_detectadas", 0)
    aprobadas = metricas.get("senales_aprobadas", 0)

    uso_cache = metricas.get(
        "uso_cache_activos",
        0
    )

    if uso_cache:
        print("Origen universo: CACHE")

        print(
            "Fallback caché por API:",
            metricas.get(
                "fallback_cache_api",
                0
            )
        )

        print(
            "Compatibles disponibles en caché:",
            metricas.get(
                "compatibles_antes_top",
                0
            )
        )

    else:
        print("Origen universo: ESCANEO COMPLETO")

        print(
            "Mercados abiertos recorridos:",
            metricas.get(
                "mercados_abiertos_recorridos",
                0
            )
        )

        print(
            "Duplicados omitidos:",
            metricas.get(
                "duplicados_omitidos",
                0
            )
        )

        print(
            "Descartados inválidos:",
            metricas.get(
                "descartados_invalidos",
                0
            )
        )

        print(
            "Descartados cooldown:",
            metricas.get(
                "descartados_cooldown",
                0
            )
        )

        print(
            "Evaluados por filtro:",
            metricas.get(
                "activos_evaluados_filtro",
                0
            )
        )

        print(
            "Descartados totales evaluar_estabilidad:",
            metricas.get(
                "descartados_sin_datos",
                0
            )
        )

        print(
            "  get_candles None:",
            metricas.get(
                "scan_candles_none",
                0
            )
        )

        print(
            "  Menos de 80 velas:",
            metricas.get(
                "scan_velas_insuficientes",
                0
            )
        )

        print(
            "  Formato -op:",
            metricas.get(
                "scan_formato_op",
                0
            )
        )

        print(
            "  Formato combinado:",
            metricas.get(
                "scan_formato_combinado",
                0
            )
        )

        print(
            "  Calidad no apta:",
            metricas.get(
                "scan_calidad",
                0
            )
        )

        print(
            "  Score diagnóstico <52:",
            metricas.get(
                "scan_score",
                0
            )
        )

        print(
            "  Tendencia indefinida:",
            metricas.get(
                "scan_tendencia_indefinida",
                0
            )
        )

        print(
            "  Tendencia débil:",
            metricas.get(
                "scan_tendencia_debil",
                0
            )
        )

        print(
            "  Rango débil:",
            metricas.get(
                "scan_rango_debil",
                0
            )
        )

        print(
            "  Inválido API:",
            metricas.get(
                "scan_invalido_api",
                0
            )
        )

        print(
            "  Excepción:",
            metricas.get(
                "scan_excepcion",
                0
            )
        )

        print(
            "Descartados por score:",
            metricas.get(
                "descartados_score",
                0
            )
        )

        print(
            "Compatibles antes del TOP:",
            metricas.get(
                "compatibles_antes_top",
                0
            )
        )

    print("Mercados seleccionados:", mercados)

    print(
        "Activos con candidatas:",
        metricas.get(
            "activos_con_candidatas",
            0
        )
    )

    print(
        "Candidatas generadas:",
        metricas.get(
            "candidatas_generadas",
            0
        )
    )

    familias_generadas = metricas.get(
        "familias_generadas",
        {}
    )

    if familias_generadas:
        print("Familias generadas:")

        for patron, cantidad in sorted(
            familias_generadas.items(),
            key=lambda item: (
                -item[1],
                item[0]
            )
        ):
            print(
                "  ",
                patron,
                ":",
                cantidad
            )
    else:
        print(
            "Familias generadas: ninguna"
        )

    print(
        "Candidatas evaluadas por Cerebro:",
        metricas.get(
            "candidatas_evaluadas_cerebro",
            0
        )
    )

    print(
        "Candidatas que continúan:",
        metricas.get(
            "candidatas_que_continuan",
            0
        )
    )

    print(
        "Sin señal final devuelta a bot:",
        max(mercados - detectadas, 0)
    )

    print("Señales finales a bot:", detectadas)

    print(
        "Cerebro NO_OPERAR:",
        metricas.get(
            "cerebro_no_operar",
            0
        )
    )

    print(
        "Cerebro sin autorización:",
        metricas.get(
            "cerebro_sin_autorizacion",
            0
        )
    )

    print("Señales aprobadas REALES:", aprobadas)

    print(
        "Autorizadas DIRECTA:",
        metricas.get(
            "autorizadas_directa",
            0
        )
    )

    print(
        "Autorizadas PROTOCOLO:",
        metricas.get(
            "autorizadas_protocolo",
            0
        )
    )

    print(
        "DIRECTAS no ejecutadas:",
        metricas.get(
            "directas_no_ejecutadas",
            0
        )
    )

    print(
        "Entradas DIRECTAS abiertas:",
        metricas.get(
            "entradas_abiertas",
            0
        )
    )

    bloqueos = metricas.get("bloqueos", {})

    if bloqueos:
        print("Bloqueos principales:")
        for motivo, total in sorted(bloqueos.items(), key=lambda x: x[1], reverse=True):
            print("-", motivo + ":", total)

    print("============================\n")


def reiniciar_metricas_ronda():
    import estado

    estado.metricas_ronda = {
        "mercados_analizados": 0,
        "uso_cache_activos": 0,
        "fallback_cache_api": 0,
        "mercados_abiertos_recorridos": 0,
        "duplicados_omitidos": 0,
        "descartados_invalidos": 0,
        "descartados_cooldown": 0,
        "activos_evaluados_filtro": 0,
        "descartados_sin_datos": 0,
        "scan_candles_none": 0,
        "scan_velas_insuficientes": 0,
        "scan_formato_op": 0,
        "scan_formato_combinado": 0,
        "scan_calidad": 0,
        "scan_score": 0,
        "scan_tendencia_indefinida": 0,
        "scan_tendencia_debil": 0,
        "scan_rango_debil": 0,
        "scan_invalido_api": 0,
        "scan_excepcion": 0,
        "descartados_score": 0,
        "compatibles_antes_top": 0,
        "senales_detectadas": 0,
        "activos_con_candidatas": 0,
        "candidatas_generadas": 0,
        "familias_generadas": {},
        "candidatas_evaluadas_cerebro": 0,
        "candidatas_que_continuan": 0,
        "senales_aprobadas": 0,
        "cerebro_no_operar": 0,
        "cerebro_sin_autorizacion": 0,
        "autorizadas_directa": 0,
        "autorizadas_protocolo": 0,
        "directas_no_ejecutadas": 0,
        "entradas_abiertas": 0,
        "bloqueos": {}
    }

def registrar_bloqueo(motivo):
    import estado

    if not hasattr(estado, "metricas_ronda"):
        estado.metricas_ronda = {
            "mercados_analizados": 0,
            "uso_cache_activos": 0,
            "fallback_cache_api": 0,
            "mercados_abiertos_recorridos": 0,
            "duplicados_omitidos": 0,
            "descartados_invalidos": 0,
            "descartados_cooldown": 0,
            "activos_evaluados_filtro": 0,
            "descartados_sin_datos": 0,
            "scan_candles_none": 0,
            "scan_velas_insuficientes": 0,
            "scan_formato_op": 0,
            "scan_formato_combinado": 0,
            "scan_calidad": 0,
            "scan_score": 0,
            "scan_tendencia_indefinida": 0,
            "scan_tendencia_debil": 0,
            "scan_rango_debil": 0,
            "scan_invalido_api": 0,
            "scan_excepcion": 0,
            "descartados_score": 0,
            "compatibles_antes_top": 0,
            "senales_detectadas": 0,
            "activos_con_candidatas": 0,
            "candidatas_generadas": 0,
            "familias_generadas": {},
            "candidatas_evaluadas_cerebro": 0,
            "candidatas_que_continuan": 0,
            "senales_aprobadas": 0,
            "cerebro_no_operar": 0,
            "cerebro_sin_autorizacion": 0,
            "autorizadas_directa": 0,
            "autorizadas_protocolo": 0,
            "directas_no_ejecutadas": 0,
            "entradas_abiertas": 0,
            "bloqueos": {}
        }

    if motivo not in estado.metricas_ronda["bloqueos"]:
        estado.metricas_ronda["bloqueos"][motivo] = 0

    estado.metricas_ronda["bloqueos"][motivo] += 1