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
from mercado import obtener_activos, precargar_velas_activos
from estrategia import analizar_activo
from entrada import (
    guardar_senal_pendiente,
    procesar_senales_pendientes,
    motivo_pendiente_por_accion_precio
)
from operaciones import revisar_operaciones_abiertas, abrir_operacion
from estadisticas import imprimir_estadisticas


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
    balance_actual = float(
        getattr(estado, "balance_inicial", 0) or 0
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
        # Solo después de validar conexión revisamos
        # operaciones abiertas y señales pendientes.
        revisar_operaciones_abiertas()
        procesar_senales_pendientes(
            abrir_operacion
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
                nuevo_balance = estado.Iq.get_balance()

                if nuevo_balance is not None:
                    balance_actual = float(
                        nuevo_balance
                    )

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

        ganancia_neta = (
            balance_actual
            - estado.balance_inicial
        )

        # ==========================================
        # REPORTE GENERAL DE MERCADOS CADA 5 MIN
        # ==========================================
        if (
            ahora
            - estado.ultimo_reporte_mercados
            >= 300
        ):
            if estado.snapshot_mercados:

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
                    balance_actual,
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

        if (
            ronda_estadisticas
            >= MOSTRAR_ESTADISTICAS_CADA_RONDAS
        ):
            imprimir_estadisticas()
            ronda_estadisticas = 0

        if ganancia_neta <= STOP_LOSS:
            print(
                "Stop loss alcanzado. "
                "Bot detenido."
            )
            break

        if ganancia_neta >= STOP_WIN:
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
                    print(
                        "D7.6A PRECALENTANDO CACHE "
                        "FUERA DE VENTANA | edad:",
                        round(edad_cache, 2),
                    )

                    # ==========================================
                    # D7.6C.1 — preservar edad real de la cache
                    # si el scanner falla y obtener_activos()
                    # necesita utilizar su fallback.
                    # ==========================================

                    timestamp_cache_previo = float(
                        getattr(
                            estado,
                            "ultima_actualizacion_activos",
                            0,
                        )
                        or 0
                    )

                    # Fuerza intento de scanner completo.
                    # La lista cacheada se conserva para fallback.
                    estado.ultima_actualizacion_activos = 0

                    activos_precarga = obtener_activos()

                    timestamp_cache_despues = float(
                        getattr(
                            estado,
                            "ultima_actualizacion_activos",
                            0,
                        )
                        or 0
                    )

                    # Si obtener_activos() devolvió activos pero
                    # no registró un timestamp nuevo, significa
                    # que utilizó el fallback de cache.
                    #
                    # Restauramos EL TIMESTAMP ORIGINAL.
                    # No usamos time.time(), porque eso haría
                    # parecer nueva una cache que realmente
                    # puede llevar 70, 100 o más segundos.
                    if (
                        activos_precarga
                        and timestamp_cache_despues <= 0
                        and timestamp_cache_previo > 0
                    ):
                        estado.ultima_actualizacion_activos = (
                            timestamp_cache_previo
                        )

                        print(
                            "D7.6C.1 SCANNER FALLBACK — "
                            "TIMESTAMP CACHE RESTAURADO | edad:",
                            round(
                                time.time()
                                - timestamp_cache_previo,
                                2,
                            ),
                        )

                    if activos_precarga:
                        precargar_velas_activos(
                            activos_precarga
                        )

                    ultima_precarga_activos = time.time()

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

        if (
            not getattr(
                estado,
                "activos_cache",
                [],
            )
            or edad_cache >= 120
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

        # Con cache <120 s, obtener_activos() usa
        # directamente su rama CACHE.
        activos = obtener_activos()

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

                senal = analizar_activo(
                    activo
                )

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
