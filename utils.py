import time
import estado


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


def activo_en_cooldown(activo):
    if activo not in estado.cooldown_activos:
        return False

    if time.time() >= estado.cooldown_activos[activo]:
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


def imprimir_resumen_ronda():
    import estado

    print("\n===== RESUMEN DE RONDA =====")
    mercados = estado.metricas_ronda.get("mercados_analizados", 0)
    detectadas = estado.metricas_ronda.get("senales_detectadas", 0)
    aprobadas = estado.metricas_ronda.get("senales_aprobadas", 0)

    uso_cache = estado.metricas_ronda.get(
        "uso_cache_activos",
        0
    )

    if uso_cache:
        print("Origen universo: CACHE")

        print(
            "Fallback caché por API:",
            estado.metricas_ronda.get(
                "fallback_cache_api",
                0
            )
        )

        print(
            "Compatibles disponibles en caché:",
            estado.metricas_ronda.get(
                "compatibles_antes_top",
                0
            )
        )

    else:
        print("Origen universo: ESCANEO COMPLETO")

        print(
            "Mercados abiertos recorridos:",
            estado.metricas_ronda.get(
                "mercados_abiertos_recorridos",
                0
            )
        )

        print(
            "Duplicados omitidos:",
            estado.metricas_ronda.get(
                "duplicados_omitidos",
                0
            )
        )

        print(
            "Descartados inválidos:",
            estado.metricas_ronda.get(
                "descartados_invalidos",
                0
            )
        )

        print(
            "Descartados cooldown:",
            estado.metricas_ronda.get(
                "descartados_cooldown",
                0
            )
        )

        print(
            "Evaluados por filtro:",
            estado.metricas_ronda.get(
                "activos_evaluados_filtro",
                0
            )
        )

        print(
            "Descartados totales evaluar_estabilidad:",
            estado.metricas_ronda.get(
                "descartados_sin_datos",
                0
            )
        )

        print(
            "  get_candles None:",
            estado.metricas_ronda.get(
                "scan_candles_none",
                0
            )
        )

        print(
            "  Menos de 80 velas:",
            estado.metricas_ronda.get(
                "scan_velas_insuficientes",
                0
            )
        )

        print(
            "  Formato -op:",
            estado.metricas_ronda.get(
                "scan_formato_op",
                0
            )
        )

        print(
            "  Formato combinado:",
            estado.metricas_ronda.get(
                "scan_formato_combinado",
                0
            )
        )

        print(
            "  Calidad no apta:",
            estado.metricas_ronda.get(
                "scan_calidad",
                0
            )
        )

        print(
            "  Score diagnóstico <52:",
            estado.metricas_ronda.get(
                "scan_score",
                0
            )
        )

        print(
            "  Tendencia indefinida:",
            estado.metricas_ronda.get(
                "scan_tendencia_indefinida",
                0
            )
        )

        print(
            "  Tendencia débil:",
            estado.metricas_ronda.get(
                "scan_tendencia_debil",
                0
            )
        )

        print(
            "  Rango débil:",
            estado.metricas_ronda.get(
                "scan_rango_debil",
                0
            )
        )

        print(
            "  Inválido API:",
            estado.metricas_ronda.get(
                "scan_invalido_api",
                0
            )
        )

        print(
            "  Excepción:",
            estado.metricas_ronda.get(
                "scan_excepcion",
                0
            )
        )

        print(
            "Descartados por score:",
            estado.metricas_ronda.get(
                "descartados_score",
                0
            )
        )

        print(
            "Compatibles antes del TOP:",
            estado.metricas_ronda.get(
                "compatibles_antes_top",
                0
            )
        )

    print("Mercados seleccionados:", mercados)

    print(
        "Activos con candidatas:",
        estado.metricas_ronda.get(
            "activos_con_candidatas",
            0
        )
    )

    print(
        "Candidatas generadas:",
        estado.metricas_ronda.get(
            "candidatas_generadas",
            0
        )
    )

    familias_generadas = estado.metricas_ronda.get(
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
        estado.metricas_ronda.get(
            "candidatas_evaluadas_cerebro",
            0
        )
    )

    print(
        "Candidatas que continúan:",
        estado.metricas_ronda.get(
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
        estado.metricas_ronda.get(
            "cerebro_no_operar",
            0
        )
    )

    print(
        "Cerebro sin autorización:",
        estado.metricas_ronda.get(
            "cerebro_sin_autorizacion",
            0
        )
    )

    print("Señales aprobadas REALES:", aprobadas)

    print(
        "Autorizadas DIRECTA:",
        estado.metricas_ronda.get(
            "autorizadas_directa",
            0
        )
    )

    print(
        "Autorizadas PROTOCOLO:",
        estado.metricas_ronda.get(
            "autorizadas_protocolo",
            0
        )
    )

    print(
        "DIRECTAS no ejecutadas:",
        estado.metricas_ronda.get(
            "directas_no_ejecutadas",
            0
        )
    )

    print(
        "Entradas DIRECTAS abiertas:",
        estado.metricas_ronda.get(
            "entradas_abiertas",
            0
        )
    )

    bloqueos = estado.metricas_ronda.get("bloqueos", {})

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