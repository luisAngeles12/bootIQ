import time
import estado
from motor_candidatos import ordenar_candidatas_v3
from config import (
    MOSTRAR_ESTADISTICAS_CADA_RONDAS,
    STOP_LOSS,
    STOP_WIN,
    MAX_OPERACIONES_ABIERTAS,
    VENTANA_ENTRADA_INICIO,
    VENTANA_ENTRADA_FIN,
    CANDLE_TIME
)
from utils import segundo_actual, registrar_bloqueo, imprimir_resumen_ronda, reiniciar_metricas_ronda
from conexion import conectar, reconectar_iq
from historial import asegurar_historial_csv, cargar_operaciones_pendientes
from mercado import (
    obtener_activos,
    precargar_velas_activos,
    refrescar_activos_incremental,
)
from estrategia import analizar_activo
from entrada import (
    guardar_senal_pendiente,
    procesar_senales_pendientes,
    motivo_pendiente_por_accion_precio
)
from operaciones import revisar_operaciones_abiertas, abrir_operacion
from estadisticas import (
    imprimir_estadisticas,
    activos_bloqueables,
)


def main():

    conectar()
    asegurar_historial_csv()
    cargar_operaciones_pendientes()

    ronda_estadisticas = 0
    operaciones_desde_resumen_mercado = 0

    # D7.6A — precarga del universo fuera de la ventana
    # operativa. Evita consumir los segundos 0-10 haciendo
    # el scanner completo.
    ultima_precarga_activos = 0.0

    # D7.6C — una sola ronda LIVE por vela.
    ultima_ronda_live_d76c = None
    ultima_impresion_estado = 0
    ultima_impresion_resumen = 0

    # Controlar la frecuencia real de consultas al broker.
    # El balance se consulta como máximo una vez cada 10 segundos.
    ultima_consulta_balance = 0
    balance_inicial_conocido = getattr(
        estado,
        "balance_inicial",
        None,
    )

    balance_actual = (
        float(balance_inicial_conocido)
        if balance_inicial_conocido is not None
        else None
    )

    # Nuevo: reporte general de mercados cada 5 minutos.
    if not hasattr(estado, "ultimo_reporte_mercados"):
        estado.ultimo_reporte_mercados = 0

    if not hasattr(estado, "snapshot_mercados"):
        estado.snapshot_mercados = {}

    while True:

        # ==========================================
        # CONEXIÓN IQ — PRIMERA PRIORIDAD
        # ==========================================
        # Nunca usar la API si el websocket está caído.
        try:
            conectado = (
                estado.Iq is not None
                and estado.Iq.check_connect()
            )
        except Exception:
            conectado = False

        if not conectado:
            if not reconectar_iq():
                print(
                    "IQ Option sigue desconectado. "
                    "BootIQ pausa análisis y operaciones.",
                    flush=True
                )
                time.sleep(5)
                continue

            # La sesión acaba de reconstruirse.
            # Dar tiempo a websocket, timesync y suscripciones
            # para estabilizarse antes de volver a usar la API.
            print(
                "Conexión recuperada. "
                "Esperando estabilización de la sesión...",
                flush=True
            )
            time.sleep(3)

            # Volver al inicio del loop para validar
            # nuevamente check_connect() antes de usar IQ.
            continue

        # ==========================================
        # API CONFIRMADA COMO DISPONIBLE
        # ==========================================

        segundo_loop_d76d = segundo_actual()

        # ==========================================
        # D7.6D — RESULTADOS FUERA DE VENTANA CRITICA
        # ==========================================
        #
        # La consulta del resultado puede bloquear
        # esperando respuestas de IQ.
        #
        # Se ejecuta en ventana de mantenimiento,
        # lejos de los segundos 0-10 reservados para:
        #
        # estrategia -> Cerebro -> ranking -> orden.
        #
        if (
            20
            <= segundo_loop_d76d
            <= 24
        ):
            revisar_operaciones_abiertas()

        # Las señales pendientes/protocolo sí deben
        # conservar su evaluación temporal normal.
        inicio_protocolos_d76d = (
            time.perf_counter()
        )

        segundo_protocolos_antes = (
            segundo_actual()
        )

        procesar_senales_pendientes(
            abrir_operacion
        )

        demora_protocolos_d76d = (
            time.perf_counter()
            - inicio_protocolos_d76d
        )

        segundo_protocolos_despues = (
            segundo_actual()
        )

        if demora_protocolos_d76d >= 0.25:
            print(
                "D7.6D TIMING PROTOCOLOS |",
                "antes:",
                segundo_protocolos_antes,
                "| despues:",
                segundo_protocolos_despues,
                "| demora:",
                round(
                    demora_protocolos_d76d,
                    3
                ),
            )

        ahora = time.time()

        # ==========================================
        # BALANCE — CONSULTA CONTROLADA
        # ==========================================
        # No consultar get_balance() en cada vuelta del loop.
        # Una consulta cada 10 segundos es suficiente para
        # STOP_WIN / STOP_LOSS y reduce carga del websocket.
        # ==========================================
        # D7.6D — BALANCE FUERA DE VENTANA CRITICA
        # ==========================================
        #
        # get_balance() puede bloquear hasta 10 s.
        # Solo se permite entre segundos 20-45,
        # lejos de la próxima entrada 0-10.
        segundo_mantenimiento_d76d = segundo_actual()

        if (
            20 <= segundo_mantenimiento_d76d <= 45
            and ahora
            - ultima_consulta_balance
            >= 10
        ):
            try:
                inicio_balance_d76d = (
                    time.perf_counter()
                )

                segundo_balance_antes = (
                    segundo_actual()
                )

                nuevo_balance = (
                    estado.Iq.get_balance()
                )

                demora_balance_d76d = (
                    time.perf_counter()
                    - inicio_balance_d76d
                )

                segundo_balance_despues = (
                    segundo_actual()
                )

                print(
                    "D7.6D TIMING BALANCE |",
                    "antes:",
                    segundo_balance_antes,
                    "| despues:",
                    segundo_balance_despues,
                    "| demora:",
                    round(
                        demora_balance_d76d,
                        3
                    ),
                )

                if nuevo_balance is not None:
                    nuevo_balance = float(
                        nuevo_balance
                    )

                    if estado.balance_inicial is None:
                        estado.balance_inicial = (
                            nuevo_balance
                        )

                        print(
                            "Balance inicial recuperado:",
                            estado.balance_inicial,
                            flush=True,
                        )

                    balance_actual = nuevo_balance

                ultima_consulta_balance = ahora

            except Exception as e:
                print(
                    "No se pudo actualizar balance:",
                    e,
                    flush=True
                )

                # Un timeout puntual de balance no implica
                # necesariamente que el websocket esté muerto.
                try:
                    conectado_balance = (
                        estado.Iq is not None
                        and estado.Iq.check_connect()
                    )
                except Exception:
                    conectado_balance = False

                ultima_consulta_balance = ahora

                if not conectado_balance:
                    if reconectar_iq():
                        print(
                            "Conexión recuperada. "
                            "Esperando estabilización de la sesión...",
                            flush=True
                        )
                        time.sleep(3)
                    else:
                        time.sleep(5)

                    continue

        if (
            balance_actual is not None
            and estado.balance_inicial is not None
        ):
            ganancia_neta = (
                balance_actual
                - estado.balance_inicial
            )
        else:
            ganancia_neta = 0.0

        # ==========================================
        # REPORTE GENERAL DE MERCADOS CADA 5 MIN
        # ==========================================
        if (
            ahora
            - estado.ultimo_reporte_mercados
            >= 300
        ):
            if estado.snapshot_mercados:

                inicio_reporte_mercados_d76d = (
                    time.perf_counter()
                )

                segundo_reporte_antes = (
                    segundo_actual()
                )

                print("\n" + "=" * 80)
                print("REPORTE GENERAL DE MERCADOS")
                print("=" * 80)

                for activo, info in sorted(
                    estado.snapshot_mercados.items()
                ):
                    print(
                        activo,
                        "|",
                        info.get(
                            "tipo",
                            "INDEFINIDO"
                        ),
                        "|",
                        info.get(
                            "calidad",
                            "SIN_DATOS"
                        ),
                        "| score:",
                        info.get(
                            "score",
                            0
                        ),
                        "|",
                        info.get(
                            "tendencia",
                            "INDEFINIDA"
                        ),
                        "| fuerza:",
                        round(
                            info.get(
                                "fuerza",
                                0
                            ),
                            2
                        )
                    )

                print("=" * 80 + "\n")

                demora_reporte_mercados_d76d = (
                    time.perf_counter()
                    - inicio_reporte_mercados_d76d
                )

                segundo_reporte_despues = (
                    segundo_actual()
                )

                print(
                    "D7.6D TIMING REPORTE MERCADOS |",
                    "antes:",
                    segundo_reporte_antes,
                    "| despues:",
                    segundo_reporte_despues,
                    "| demora:",
                    round(
                        demora_reporte_mercados_d76d,
                        3
                    ),
                )

            estado.ultimo_reporte_mercados = ahora

        # Imprime balance solo cada 20 segundos
        # para no llenar la terminal.
        if (
            ahora
            - ultima_impresion_estado
            >= 20
        ):
            print(
                "\nBalance:",
                round(
                    (
                        balance_actual
                        if balance_actual is not None
                        else 0.0
                    ),
                    2
                ),
                "| Neto:",
                round(
                    ganancia_neta,
                    2
                ),
                "| Abiertas:",
                len(
                    estado.operaciones_abiertas
                )
            )

            ultima_impresion_estado = ahora

        ronda_estadisticas += 1

        # ==========================================
        # D7.6D — ESTADISTICAS FUERA DE VENTANA
        # ==========================================
        #
        # imprimir_estadisticas() genera una salida
        # extensa y puede consumir varios segundos,
        # especialmente usando tee.
        #
        # Nunca permitimos que esa tarea de reporte
        # robe tiempo a la ventana operativa 0-10.
        #
        segundo_estadisticas_d76d = (
            segundo_actual()
        )

        if (
            ronda_estadisticas
            >= MOSTRAR_ESTADISTICAS_CADA_RONDAS
            and 30
            <= segundo_estadisticas_d76d
            <= 35
        ):
            inicio_estadisticas_d76d = (
                time.perf_counter()
            )

            segundo_estadisticas_antes = (
                segundo_actual()
            )

            imprimir_estadisticas()

            demora_estadisticas_d76d = (
                time.perf_counter()
                - inicio_estadisticas_d76d
            )

            segundo_estadisticas_despues = (
                segundo_actual()
            )

            print(
                "D7.6D TIMING ESTADISTICAS |",
                "antes:",
                segundo_estadisticas_antes,
                "| despues:",
                segundo_estadisticas_despues,
                "| demora:",
                round(
                    demora_estadisticas_d76d,
                    3
                ),
            )

            ronda_estadisticas = 0
        if (
            balance_actual is not None
            and estado.balance_inicial is not None
            and ganancia_neta <= STOP_LOSS
        ):
            print(
                "Stop loss alcanzado. "
                "Bot detenido."
            )
            break

        if (
            balance_actual is not None
            and estado.balance_inicial is not None
            and ganancia_neta >= STOP_WIN
        ):
            print(
                "Stop win alcanzado. "
                "Bot detenido."
            )
            break

        segundo = segundo_actual()

        # ==========================================
        # VENTANA DE BÚSQUEDA DE ENTRADA
        # ==========================================
        if not (
            VENTANA_ENTRADA_INICIO
            <= segundo
            <= VENTANA_ENTRADA_FIN
        ):

            # ==========================================
            # D7.6A — PRECALENTAR CACHE DE ACTIVOS
            # ==========================================
            #
            # El scanner completo se ejecuta FUERA de
            # la ventana operativa. Así 0-10 queda para:
            # estrategia -> Cerebro -> ranking -> orden.
            #
            if (
                12 <= segundo <= 18
                and time.time()
                - ultima_precarga_activos
                >= 45
            ):
                edad_cache = (
                    time.time()
                    - float(
                        getattr(
                            estado,
                            "ultima_actualizacion_activos",
                            0,
                        )
                        or 0
                    )
                )

                if (
                    not getattr(
                        estado,
                        "activos_cache",
                        [],
                    )
                    or edad_cache >= 60
                ):

                    inicio_precarga_total_d76d = (
                        time.perf_counter()
                    )

                    segundo_precarga_total_antes = (
                        segundo_actual()
                    )

                    print(
                        "D7.6A PRECALENTANDO CACHE "
                        "FUERA DE VENTANA | edad:",
                        round(edad_cache, 2),
                    )

                    # ==========================================
                    # D7.6D — BOOTSTRAP / REFRESH INCREMENTAL
                    # ==========================================

                    inicio_obtener_activos_d76d = (
                        time.perf_counter()
                    )

                    segundo_obtener_activos_antes = (
                        segundo_actual()
                    )

                    # Tanto el BOOTSTRAP inicial como
                    # los refresh posteriores usan el
                    # scanner incremental.
                    #
                    # El progreso del universo se conserva
                    # entre llamadas y ningún TOP parcial
                    # se publica como cache operable.
                    activos_precarga = (
                        refrescar_activos_incremental()
                    )

                    demora_obtener_activos_d76d = (
                        time.perf_counter()
                        - inicio_obtener_activos_d76d
                    )

                    segundo_obtener_activos_despues = (
                        segundo_actual()
                    )

                    print(
                        "D7.6D TIMING OBTENER ACTIVOS |",
                        "antes:",
                        segundo_obtener_activos_antes,
                        "| despues:",
                        segundo_obtener_activos_despues,
                        "| demora:",
                        round(
                            demora_obtener_activos_d76d,
                            3,
                        ),
                    )

                    if activos_precarga:
                        precargar_velas_activos(
                            activos_precarga
                        )

                    demora_precarga_total_d76d = (
                        time.perf_counter()
                        - inicio_precarga_total_d76d
                    )

                    segundo_precarga_total_despues = (
                        segundo_actual()
                    )

                    print(
                        "D7.6D TIMING PRECARGA TOTAL |",
                        "antes:",
                        segundo_precarga_total_antes,
                        "| despues:",
                        segundo_precarga_total_despues,
                        "| demora:",
                        round(
                            demora_precarga_total_d76d,
                            3,
                        ),
                    )

                    ultima_precarga_activos = (
                        time.time()
                    )

                    time.sleep(0.25)
                    continue

            if (
                time.time()
                - ultima_impresion_resumen
                >= 60
            ):
                if (
                    estado.metricas_ronda.get(
                        "mercados_analizados",
                        0
                    ) > 0
                    or estado.metricas_ronda.get(
                        "senales_detectadas",
                        0
                    ) > 0
                    or estado.metricas_ronda.get(
                        "entradas_abiertas",
                        0
                    ) > 0
                ):
                    imprimir_resumen_ronda()

                ultima_impresion_resumen = (
                    time.time()
                )

                time.sleep(0.25)
                continue

            if (
                len(
                    estado.operaciones_abiertas
                )
                >= MAX_OPERACIONES_ABIERTAS
            ):
                revisar_operaciones_abiertas()

                if (
                    time.time()
                    - ultima_impresion_resumen
                    >= 60
                ):
                    if (
                        estado.metricas_ronda.get(
                            "mercados_analizados",
                            0
                        ) > 0
                        or estado.metricas_ronda.get(
                            "senales_detectadas",
                            0
                        ) > 0
                        or estado.metricas_ronda.get(
                            "entradas_abiertas",
                            0
                        ) > 0
                    ):
                        imprimir_resumen_ronda()

                    ultima_impresion_resumen = (
                        time.time()
                    )

            time.sleep(0.25)
            continue

        # ==========================================
        # OBTENER ACTIVOS
        # ==========================================
        #
        # D7.6A:
        # dentro de 0-10 nunca iniciamos un scanner
        # completo. La ronda solo trabaja con una cache
        # previamente preparada.
        # ==========================================

        edad_cache = (
            time.time()
            - float(
                getattr(
                    estado,
                    "ultima_actualizacion_activos",
                    0,
                )
                or 0
            )
        )

        if not getattr(
            estado,
            "activos_cache",
            [],
        ):
            print(
                "D7.6A VENTANA OMITIDA — "
                "CACHE NO PREPARADA | edad:",
                round(edad_cache, 2),
            )

            time.sleep(0.25)
            continue

        # ==========================================
        # D7.6C — UNA RONDA POR VELA
        # ==========================================
        try:
            ts_ronda = float(
                estado.Iq.get_server_timestamp()
            )

            if ts_ronda > 10_000_000_000:
                ts_ronda /= 1000.0

        except Exception:
            ts_ronda = time.time()

        clave_ronda_d76c = int(
            ts_ronda // CANDLE_TIME
        )

        if (
            ultima_ronda_live_d76c
            == clave_ronda_d76c
        ):
            time.sleep(0.25)
            continue

        ultima_ronda_live_d76c = (
            clave_ronda_d76c
        )

        print(
            "D7.6C RONDA UNICA | vela:",
            clave_ronda_d76c,
            "| segundo:",
            segundo,
        )

        reiniciar_metricas_ronda()

        # ==========================================
        # D7.6D — SOLO CACHE EN VENTANA CRITICA
        # ==========================================
        #
        # Dentro de 0-10 está prohibido iniciar
        # el scanner completo, independientemente
        # de la edad real de la cache.
        #
        activos = obtener_activos(
            solo_cache=True
        )

        estado.metricas_ronda[
            "mercados_analizados"
        ] = len(activos)

        # Limpiar snapshot para que el reporte
        # solo muestre los mercados reales
        # analizados en esta ronda.
        estado.snapshot_mercados = {}

        senales = []
        bloqueos_importantes = []

        resumen_mercado = {
            "TENDENCIA_ALCISTA": 0,
            "TENDENCIA_BAJISTA": 0,
            "RANGO": 0,
            "COMPRESION": 0,
            "EXPANSION": 0,
            "INDEFINIDO": 0,
            "LIMPIO": 0,
            "NORMAL": 0,
            "SUCIO": 0,
            "CAOTICO": 0
        }

        # ==========================================
        # ANALIZAR ACTIVOS
        # ==========================================
        inicio_analisis_d76c = time.perf_counter()

        # D7.6D:
        # ninguna operación puede salir de un universo
        # parcialmente analizado.
        estado.fallo_velas_ronda_d76d = False
        ronda_incompleta_d76d = False

        # ==================================================
        # D7.6D — BLOQUEABLES CALCULADOS UNA VEZ POR RONDA
        # ==================================================
        #
        # Antes motor_estrategias_profesional() recalculaba
        # esta misma lista para cada activo.
        #
        # La lista no puede cambiar durante esta ronda:
        # el proceso es secuencial y la reconciliación de
        # resultados ocurre fuera de este análisis crítico.
        #
        # No cambia criterios ni decisiones.
        activos_malos_ronda = activos_bloqueables()

        # D7.6D — telemetría temporal solamente.
        timings_activos_d76d = []

        for item in activos:

            # Reservamos aproximadamente 2 segundos para:
            # ranking -> validación temporal -> envío IQ.
            if segundo_actual() >= 9:
                ronda_incompleta_d76d = True

                print(
                    "D7.6D RONDA INTERRUMPIDA POR TIEMPO | "
                    "antes de activo:",
                    item,
                )

                break
            try:

                activo = item["activo"]
                tipo = item["tipo"]

                if any(
                    op["activo"] == activo
                    for op
                    in estado.operaciones_abiertas
                ):
                    continue

                # Evitar reutilizar telemetría de velas
                # perteneciente a una ronda anterior.
                getattr(
                    estado,
                    "telemetria_get_candles_d76d",
                    {},
                ).pop(
                    activo,
                    None,
                )

                inicio_activo_d76d = (
                    time.perf_counter()
                )

                try:
                    senal = analizar_activo(
                        activo,
                        activos_bloqueables_ronda=(
                            activos_malos_ronda
                        ),
                    )

                finally:
                    demora_activo_d76d = (
                        time.perf_counter()
                        - inicio_activo_d76d
                    )

                    demora_velas_d76d = (
                        getattr(
                            estado,
                            "telemetria_get_candles_d76d",
                            {},
                        ).get(
                            activo,
                            0.0,
                        )
                    )

                    subfases_d76d = (
                        getattr(
                            estado,
                            "telemetria_subfases_d76d",
                            {},
                        ).get(
                            activo,
                            {},
                        )
                    )

                    grafico_total_d76d = float(
                        subfases_d76d.get(
                            "grafico_total",
                            0.0,
                        )
                        or 0.0
                    )

                    grafico_local_d76d = max(
                        0.0,
                        grafico_total_d76d
                        - demora_velas_d76d,
                    )

                    mercado_d76d = float(
                        subfases_d76d.get(
                            "mercado",
                            0.0,
                        )
                        or 0.0
                    )

                    base_d76d = float(
                        subfases_d76d.get(
                            "base",
                            0.0,
                        )
                        or 0.0
                    )

                    estrategias_d76d = float(
                        subfases_d76d.get(
                            "estrategias",
                            0.0,
                        )
                        or 0.0
                    )

                    cerebro_d76d = float(
                        subfases_d76d.get(
                            "cerebro",
                            0.0,
                        )
                        or 0.0
                    )

                    ranking_d76d = float(
                        subfases_d76d.get(
                            "ranking",
                            0.0,
                        )
                        or 0.0
                    )

                    candidatas_cerebro_d76d = int(
                        subfases_d76d.get(
                            "candidatas_cerebro",
                            0,
                        )
                        or 0
                    )

                    contabilizado_d76d = (
                        demora_velas_d76d
                        + grafico_local_d76d
                        + mercado_d76d
                        + base_d76d
                        + estrategias_d76d
                        + cerebro_d76d
                        + ranking_d76d
                    )

                    otros_d76d = max(
                        0.0,
                        demora_activo_d76d
                        - contabilizado_d76d,
                    )

                    timings_activos_d76d.append({
                        "activo": activo,
                        "total": demora_activo_d76d,
                        "velas": demora_velas_d76d,
                        "grafico": grafico_local_d76d,
                        "mercado": mercado_d76d,
                        "base": base_d76d,
                        "estrategias": estrategias_d76d,
                        "cerebro": cerebro_d76d,
                        "ranking": ranking_d76d,
                        "otros": otros_d76d,
                        "n_cerebro": candidatas_cerebro_d76d,
                    })

                # D7.6D — abortar inmediatamente si falla
                # la actualización de velas de cualquier activo.
                if getattr(
                    estado,
                    "fallo_velas_ronda_d76d",
                    False,
                ):
                    ronda_incompleta_d76d = True

                    print(
                        "D7.6D RONDA INCOMPLETA — "
                        "FALLO VELAS | activo:",
                        activo,
                    )

                    break

                if senal is not None:

                    estado.metricas_ronda[
                        "senales_detectadas"
                    ] += 1

                    senal["tipo"] = tipo

                    senales.append(
                        senal
                    )


                    tipo_m = senal.get(
                        "tipo_mercado"
                    )

                    calidad_m = senal.get(
                        "calidad_mercado"
                    )

                    if tipo_m in resumen_mercado:
                        resumen_mercado[
                            tipo_m
                        ] += 1

                    if calidad_m in resumen_mercado:
                        resumen_mercado[
                            calidad_m
                        ] += 1

            except Exception as e:

                bloqueos_importantes.append(
                    "Error analizando "
                    + str(item)
                    + ": "
                    + str(e)
                )

                # D7.6D — cualquier excepción durante el
                # análisis invalida el universo completo.
                ronda_incompleta_d76d = True

                print(
                    "D7.6D RONDA INCOMPLETA — "
                    "ERROR ANALIZANDO | activo:",
                    item,
                    "| error:",
                    e,
                )

                break

        demora_analisis_d76c = (
            time.perf_counter()
            - inicio_analisis_d76c
        )

        print(
            "D7.6C TIEMPO ANALISIS TOP:",
            round(demora_analisis_d76c, 3),
            "segundos | activos:",
            len(activos),
        )

        # ==========================================
        # D7.6D — VALIDACION FINAL DE RONDA
        # ==========================================

        if segundo_actual() >= 9:
            ronda_incompleta_d76d = True

        if (
            ronda_incompleta_d76d
            or getattr(
                estado,
                "fallo_velas_ronda_d76d",
                False,
            )
        ):
            if timings_activos_d76d:
                print(
                    "D7.6D PERF DESCARTE |",
                    "procesados:",
                    len(timings_activos_d76d),
                    "/",
                    len(activos),
                    "| detalle:",
                    " ; ".join(
                        (
                            f"{x['activo']} "
                            f"tot={x['total']:.3f}s "
                            f"vel={x['velas']:.3f}s "
                            f"graf={x['grafico']:.3f}s "
                            f"merc={x['mercado']:.3f}s "
                            f"base={x['base']:.3f}s "
                            f"estr={x['estrategias']:.3f}s "
                            f"cer={x['cerebro']:.3f}s "
                            f"rank={x['ranking']:.3f}s "
                            f"otros={x['otros']:.3f}s "
                            f"ncer={x['n_cerebro']}"
                        )
                        for x in timings_activos_d76d
                    ),
                )
            print(
                "D7.6D RONDA DESCARTADA — "
                "NO SE ORDENA TOP PARCIAL | segundo:",
                segundo_actual(),
            )

            time.sleep(0.25)
            continue

        # ==========================================
        # MOSTRAR SEÑALES
        # ==========================================
        if senales:

            print(
                "\nSeñales preparadas:",
                len(senales)
            )

            senales = ordenar_candidatas_v3(
                senales
            )

            for s in senales[:5]:

                print(
                    s["activo"],
                    s["tipo"],
                    s["direccion"],
                    "| puntaje:",
                    s["puntaje"],
                    "| calidad:",
                    s.get(
                        "calidad",
                        "N/A"
                    ),
                    "| patrón:",
                    s["patron"],
                    "| RSI:",
                    s["rsi"],
                    "| mercado:",
                    s.get(
                        "tipo_mercado",
                        "N/A"
                    ),
                    "| calidad mercado:",
                    s.get(
                        "calidad_mercado",
                        "N/A"
                    )
                )

        abiertas_ahora = 0

        # ==========================================
        # PROCESAR SEÑALES
        # ==========================================
        for senal in senales:

            if (
                len(
                    estado.operaciones_abiertas
                )
                >= MAX_OPERACIONES_ABIERTAS
            ):
                break

            if any(
                op["activo"]
                == senal["activo"]
                for op
                in estado.operaciones_abiertas
            ):
                continue

            # ======================================
            # AUTORIZACIÓN DEL CEREBRO ÚNICO
            # ======================================
            decision_cerebro = str(
                senal.get(
                    "cerebro_unico_decision",
                    senal.get(
                        "decision_unificada_accion",
                        ""
                    )
                )
            ).upper().strip()

            # Defensa adicional.
            # Normalmente estrategia.py
            # ya elimina estas señales.
            if decision_cerebro == "NO_OPERAR":

                estado.metricas_ronda[
                    "cerebro_no_operar"
                ] += 1

                print(
                    "SEÑAL BLOQUEADA POR "
                    "CEREBRO ÚNICO:",
                    senal.get(
                        "activo",
                        ""
                    ),
                    senal.get(
                        "patron",
                        ""
                    )
                )

                continue

            # Una decisión desconocida nunca
            # debe llegar al broker.
            if decision_cerebro not in [
                "OPERAR",
                "OPERAR_CON_PROTOCOLO"
            ]:

                estado.metricas_ronda[
                    "cerebro_sin_autorizacion"
                ] += 1

                print(
                    "SEÑAL SIN AUTORIZACIÓN VÁLIDA:",
                    senal.get(
                        "activo",
                        ""
                    ),
                    "| decisión:",
                    decision_cerebro
                    or "VACÍA"
                )

                continue

            # ======================================
            # OPERAR CON PROTOCOLO
            # ======================================
            # Esta señal nunca puede abrirse
            # directamente.
            #
            # Debe pasar obligatoriamente
            # por pendientes.
            if (
                decision_cerebro
                == "OPERAR_CON_PROTOCOLO"
            ):

                estado.metricas_ronda[
                    "senales_aprobadas"
                ] += 1

                estado.metricas_ronda[
                    "autorizadas_protocolo"
                ] += 1

                motivo = (
                    motivo_pendiente_por_accion_precio(
                        senal
                    )
                )

                if (
                    not motivo
                    or motivo
                    == "ENTRADA_NORMAL"
                ):
                    motivo = (
                        "CEREBRO_UNICO_"
                        "REQUIERE_PROTOCOLO"
                    )

                senal[
                    "requiere_protocolo_cerebro"
                ] = True

                senal[
                    "protocolo_confirmado"
                ] = False

                guardar_senal_pendiente(
                    senal,
                    motivo
                )

                print(
                    "SEÑAL ENVIADA A PROTOCOLO:",
                    senal.get(
                        "activo",
                        ""
                    ),
                    "| motivo:",
                    motivo
                )

                time.sleep(0.02)
                continue

            # ======================================
            # OPERAR — EJECUCIÓN DIRECTA
            # ======================================
            # El Cerebro Único ya evaluó:
            #
            # - estrategia
            # - mercado
            # - Price Action
            # - confianza
            # - riesgo
            #
            # bot.py no vuelve a decidir ni
            # envía esta señal a protocolo.
            estado.metricas_ronda[
                "senales_aprobadas"
            ] += 1

            estado.metricas_ronda[
                "autorizadas_directa"
            ] += 1

            senal[
                "requiere_protocolo_cerebro"
            ] = False

            senal[
                "protocolo_confirmado"
            ] = False

            if abrir_operacion(
                senal
            ):

                estado.metricas_ronda[
                    "entradas_abiertas"
                ] += 1

                abiertas_ahora += 1

                operaciones_desde_resumen_mercado += 1

            else:

                estado.metricas_ronda[
                    "directas_no_ejecutadas"
                ] += 1

                print(
                    "OPERACIÓN DIRECTA "
                    "NO EJECUTADA:",
                    senal.get(
                        "activo",
                        ""
                    ),
                    "| decisión:",
                    decision_cerebro
                )

            time.sleep(0.02)

        if abiertas_ahora > 0:

            print(
                "Operaciones abiertas "
                "en esta ronda:",
                abiertas_ahora
            )

        # ==========================================
        # RESUMEN DE MERCADO CADA 5 OPERACIONES
        # ==========================================
        if (
            operaciones_desde_resumen_mercado
            >= 5
        ):

            print(
                "\n===== RESUMEN DE MERCADO "
                "CADA 5 OPERACIONES ====="
            )

            print(
                "Tendencias:",
                "ALCISTA",
                resumen_mercado[
                    "TENDENCIA_ALCISTA"
                ],
                "| BAJISTA",
                resumen_mercado[
                    "TENDENCIA_BAJISTA"
                ],
                "| RANGO",
                resumen_mercado[
                    "RANGO"
                ]
            )

            print(
                "Calidad:",
                "LIMPIO",
                resumen_mercado[
                    "LIMPIO"
                ],
                "| NORMAL",
                resumen_mercado[
                    "NORMAL"
                ],
                "| SUCIO",
                resumen_mercado[
                    "SUCIO"
                ],
                "| CAOTICO",
                resumen_mercado[
                    "CAOTICO"
                ]
            )

            operaciones_desde_resumen_mercado = 0

            if (
                time.time()
                - ultima_impresion_resumen
                >= 60
            ):

                if (
                    estado.metricas_ronda.get(
                        "mercados_analizados",
                        0
                    ) > 0
                    or estado.metricas_ronda.get(
                        "senales_detectadas",
                        0
                    ) > 0
                    or estado.metricas_ronda.get(
                        "entradas_abiertas",
                        0
                    ) > 0
                ):

                    imprimir_resumen_ronda()

                ultima_impresion_resumen = (
                    time.time()
                )

        time.sleep(0.25)


if __name__ == "__main__":
    main()
