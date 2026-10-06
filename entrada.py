import time
import csv
from pathlib import Path
import estado
from config import (
    CANDLE_TIME,
    VENTANA_ENTRADA_INICIO,
    VENTANA_ENTRADA_FIN,
    FUERZA_MAXIMA_VELA_NORMAL,
    SEGUNDO_MAXIMO_VELA_CORRIDA,
    PARIDAD_LIVE_CSV
)
from motor_protocolos import (
    evaluar_protocolo_live_sombra,
)
from utils import segundo_actual
from confirmacion_entrada import evaluar_confirmacion_entrada
from motor_decision import evaluar_decision_post_protocolo
# ============================================================
# CEREBRO INTERMEDIO DE ENTRADA — MODO DIAGNÓSTICO
# ============================================================
# False:
# - evaluar_confirmacion_entrada() sigue calculándose completo;
# - conserva índice, nivel, motivos y acción diagnóstica;
# - NO puede cancelar ni dejar esperando una señal por sí solo;
# - las validaciones reales de entrada.py mantienen autoridad.
#
# True:
# - restaura temporalmente el comportamiento anterior.

ENTRADA_CEREBRO_INTERMEDIO_OPERATIVO = False


def registrar_paridad_protocolo_live(
    senal,
    resultado_live,
    razon_live="",
):
    """
    Compara la decisión técnica final del flujo LIVE actual
    contra motor_protocolos.py ejecutado en sombra.

    No cambia ninguna decisión.
    Solo registra COINCIDE / CONFLICTO / SIN_COMPARAR.
    """

    estado_sombra = str(
        senal.get(
            "protocolo_live_sombra_estado",
            "SIN_DATOS",
        )
        or "SIN_DATOS"
    ).upper().strip()

    resultado_live = str(
        resultado_live
        or "SIN_DATOS"
    ).upper().strip()

    razon_live = str(
        razon_live
        or ""
    ).strip()

    if estado_sombra in [
        "SIN_DATOS",
        "SENAL_NO_ENCONTRADA",
        "ERROR",
    ]:
        estado_paridad = "SIN_COMPARAR"

    else:
        sombra_entraria = (
            estado_sombra == "CONFIRMADA"
        )

        live_entraria = (
            resultado_live == "ENTRAR"
        )

        if sombra_entraria == live_entraria:
            estado_paridad = "COINCIDE"
        else:
            estado_paridad = "CONFLICTO"

    senal["paridad_live_estado"] = estado_paridad
    senal["paridad_live_resultado_actual"] = resultado_live
    senal["paridad_live_razon_actual"] = razon_live
    senal["paridad_live_estado_sombra"] = estado_sombra
    senal["paridad_live_motivo_sombra"] = senal.get(
        "protocolo_live_sombra_motivo",
        "",
    )

    # ========================================================
    # AUDITORÍA LIVE PERSISTENTE
    # Registra todas las ramas: SIN_DATOS, ESPERAR,
    # CANCELADA, CONFIRMACION_PASADA y CONFIRMADA.
    # Solo telemetría. No altera ninguna decisión.
    # ========================================================
    campos_paridad = [
        "timestamp",
        "activo",
        "direccion",
        "patron",
        "vela_senal_from",
        "protocolo_live_tipo",
        "protocolo_live_espera",
        "paridad_live_estado",
        "paridad_live_resultado_actual",
        "paridad_live_razon_actual",
        "paridad_live_estado_sombra",
        "paridad_live_motivo_sombra",
        "protocolo_live_vela_entrada_from",
    ]

    fila_paridad = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "activo": senal.get("activo", ""),
        "direccion": senal.get("direccion", ""),
        "patron": senal.get("patron", ""),
        "vela_senal_from": senal.get("vela_senal_from", ""),
        "protocolo_live_tipo": senal.get(
            "protocolo_live_sombra_tipo",
            "",
        ),
        "protocolo_live_espera": senal.get(
            "protocolo_live_sombra_espera",
            "",
        ),
        "paridad_live_estado": estado_paridad,
        "paridad_live_resultado_actual": resultado_live,
        "paridad_live_razon_actual": razon_live,
        "paridad_live_estado_sombra": estado_sombra,
        "paridad_live_motivo_sombra": senal.get(
            "protocolo_live_sombra_motivo",
            "",
        ),
        "protocolo_live_vela_entrada_from": senal.get(
            "protocolo_live_vela_entrada_from",
            "",
        ),
    }

    try:
        existe = Path(PARIDAD_LIVE_CSV).exists()
        with open(
            PARIDAD_LIVE_CSV,
            "a",
            newline="",
            encoding="utf-8-sig",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=campos_paridad,
            )
            if not existe or Path(PARIDAD_LIVE_CSV).stat().st_size == 0:
                writer.writeheader()
            writer.writerow(fila_paridad)
    except Exception as e:
        print(
            "ERROR AUDITORIA PARIDAD LIVE:",
            e,
        )

    print(
        "PARIDAD BACKTEST-LIVE:",
        senal.get("activo", ""),
        "|",
        estado_paridad,
        "| sombra:",
        estado_sombra,
        "| live:",
        resultado_live,
        "| motivo sombra:",
        senal.get(
            "protocolo_live_sombra_motivo",
            "",
        ),
        "| motivo live:",
        razon_live,
    )

    return estado_paridad

def _bool(v, default=False):
    if isinstance(v, bool):
        return v

    if v is None:
        return default

    texto = str(v).lower().strip()

    if texto in ["true", "1", "si", "sí", "yes"]:
        return True

    if texto in ["false", "0", "no", "none", "null", ""]:
        return False

    return default






def guardar_senal_pendiente(senal, motivo_pendiente="ENTRADA_NORMAL"):
    import time
    import estado
    from config import CANDLE_TIME

    activo = senal["activo"]

    # ========================================================
    # PENDIENTES EXCLUSIVAS DEL CEREBRO
    # ========================================================
    # entrada.py no crea una segunda ruta de decisión.
    # Solo puede almacenar una señal que motor_decision.py
    # ya clasificó explícitamente como OPERAR_CON_PROTOCOLO.
    requiere_protocolo = _bool(
        senal.get(
            "requiere_protocolo_cerebro",
            False,
        )
    )

    decision_cerebro = str(
        senal.get(
            "cerebro_unico_decision",
            "",
        )
        or ""
    ).upper().strip()

    if (
        not requiere_protocolo
        or decision_cerebro != "OPERAR_CON_PROTOCOLO"
    ):
        print(
            "PENDIENTE RECHAZADA POR CONTRATO:",
            activo,
            "| decision:",
            decision_cerebro or "VACIA",
            "| requiere_protocolo:",
            requiere_protocolo,
        )
        return False

    for s in estado.senales_pendientes:
        if s["activo"] == activo and s.get("motivo_pendiente") == motivo_pendiente:
            return False

    senal_pendiente = senal.copy()
    
    senal_pendiente["hora_detectada"] = time.time()
    
    # ============================================================
    # PASO 5.5A — ANCLAR LA PENDIENTE A LA VELA REAL DE SEÑAL
    # ============================================================
    
    vela_senal_from = senal_pendiente.get(
        "vela_senal_from"
    )
    
    try:
        vela_senal_from = int(
            float(vela_senal_from)
        )
    except (TypeError, ValueError):
        vela_senal_from = 0
    
    if vela_senal_from > 0:
        senal_pendiente["vela_detectada"] = int(
            vela_senal_from // CANDLE_TIME
        )
    
        senal_pendiente[
            "vela_detectada_fuente"
        ] = "VELA_SENAL_EXACTA"
    
    else:
        # Compatibilidad defensiva.
        # No debería utilizarse en señales nuevas después de 5.5A.
        senal_pendiente["vela_detectada"] = int(
            time.time() // CANDLE_TIME
        )
    
        senal_pendiente[
            "vela_detectada_fuente"
        ] = "FALLBACK_TIME"
    
    senal_pendiente[
        "motivo_pendiente"
    ] = motivo_pendiente

    estado.senales_pendientes.append(senal_pendiente)

    print(
        "SEÑAL PENDIENTE GUARDADA:",
        activo,
        senal["direccion"],
        senal["patron"],
        "| motivo:",
        motivo_pendiente,
        "| vela_from:",
        senal_pendiente.get(
            "vela_senal_from",
            0
        ),
        "| bucket:",
        senal_pendiente.get(
            "vela_detectada",
            -1
        ),
        "| fuente:",
        senal_pendiente.get(
            "vela_detectada_fuente",
            "SIN_DATOS"
        ),
    )

    return True

def motivo_pendiente_por_accion_precio(senal):
    """
    Decide si una señal debe entrar directo o quedar pendiente
    esperando confirmación de ruptura/rechazo.

    En esta fase:
    - NO cambiamos el comportamiento operativo.
    - auditamos el veto por riesgo estructural crítico.
    - conservamos PA, setup y contexto para análisis posterior.
    """

    direccion = str(
        senal.get("direccion", "")
    ).lower()

    accion_precio = str(
        senal.get("accion_precio", "")
    ).upper()

    tipo_setup = str(
        senal.get("tipo_setup", "")
    ).upper()

    calidad_setup = str(
        senal.get("calidad_setup", "")
    ).upper()

    # Campo legacy: respaldo temporal.
    modo_setup_legacy = str(
        senal.get("modo_entrada_setup", "")
    ).upper()

    # Evidencia neutral oficial del setup.
    riesgo_critico_setup = _bool(
        senal.get(
            "riesgo_estructural_critico_setup"
        ),
        default=(
            modo_setup_legacy == "NO_OPERAR"
            or "CANCELAR" in modo_setup_legacy
        ),
    )

    requiere_ruptura_setup = _bool(
        senal.get("requiere_ruptura_setup"),
        default=(
            "ESPERAR_RUPTURA"
            in modo_setup_legacy
        ),
    )

    requiere_confirmacion_setup = _bool(
        senal.get(
            "requiere_confirmacion_setup"
        ),
        default=(
            "ESPERAR_CONFIRMACION"
            in modo_setup_legacy
        ),
    )

    pa_tipo = str(
        senal.get("pa_tipo", "")
    ).upper()

    pa_direccion = str(
        senal.get("pa_direccion", "")
    ).upper()

    patron = str(
        senal.get("patron", "")
    ).lower()

    # ========================================================
    # AUDITORÍA DEL VETO DE SETUP
    # ========================================================
    senal[
        "entrada_auditoria_riesgo_critico_setup"
    ] = riesgo_critico_setup

    senal[
        "entrada_auditoria_modo_setup_legacy"
    ] = modo_setup_legacy

    senal[
        "entrada_auditoria_calidad_setup"
    ] = calidad_setup

    senal[
        "entrada_auditoria_tipo_setup"
    ] = tipo_setup

    senal[
        "entrada_auditoria_accion_precio"
    ] = accion_precio

    senal[
        "entrada_auditoria_pa_tipo"
    ] = pa_tipo

    senal[
        "entrada_auditoria_pa_direccion"
    ] = pa_direccion

    senal[
        "entrada_auditoria_requiere_ruptura"
    ] = requiere_ruptura_setup

    senal[
        "entrada_auditoria_requiere_confirmacion"
    ] = requiere_confirmacion_setup

    # ========================================================
    # RIESGO ESTRUCTURAL CRÍTICO
    # ========================================================
    # IMPORTANTE:
    # todavía conserva exactamente el comportamiento anterior.
    # Solo añadimos trazabilidad.
    if riesgo_critico_setup:
        senal[
            "entrada_auditoria_veto_setup_aplicado"
        ] = True

        senal[
            "entrada_auditoria_motivo_veto"
        ] = "RIESGO_ESTRUCTURAL_CRITICO_SETUP"

        return "CANCELAR_PROTOCOLO_RIESGO_CRITICO"

    senal[
        "entrada_auditoria_veto_setup_aplicado"
    ] = False

    senal[
        "entrada_auditoria_motivo_veto"
    ] = ""

    # ========================================================
    # RUPTURAS POR ZONA
    # ========================================================
    if (
        direccion == "call"
        and accion_precio in [
            "CALL_RESISTENCIA_CERCA_SIN_RUPTURA",
            "CALL_ZONA_NEUTRA",
        ]
    ):
        return "ESPERANDO_RUPTURA_RESISTENCIA"

    if (
        direccion == "put"
        and accion_precio in [
            "PUT_SOPORTE_CERCA_SIN_RUPTURA",
            "PUT_ZONA_NEUTRA",
        ]
    ):
        return "ESPERANDO_RUPTURA_SOPORTE"

    # ========================================================
    # SWEEP / REVERSIÓN
    # ========================================================
    if tipo_setup in [
        "SWEEP_ALCISTA",
        "SWEEP_BAJISTA",
        "REVERSION_ALCISTA",
        "REVERSION_BAJISTA",
    ]:

        # PA fuerte a favor CALL.
        if (
            direccion == "call"
            and pa_direccion == "CALL"
            and pa_tipo in [
                "RECHAZO_COMPRADOR_CONFIRMADO",
                "AGOTAMIENTO_BAJISTA_CONFIRMADO",
                "IMPULSO_ALCISTA_FUERTE",
            ]
        ):
            return None

        # PA fuerte a favor PUT.
        if (
            direccion == "put"
            and pa_direccion == "PUT"
            and pa_tipo in [
                "RECHAZO_VENDEDOR_CONFIRMADO",
                "AGOTAMIENTO_ALCISTA_CONFIRMADO",
                "IMPULSO_BAJISTA_FUERTE",
            ]
        ):
            return None

        return "ESPERANDO_CONFIRMACION_RECHAZO"

    # ========================================================
    # RECHAZOS EN SOPORTE / RESISTENCIA
    # ========================================================
    if (
        "reaccion" in patron
        or tipo_setup in [
            "RECHAZO_ALCISTA",
            "RECHAZO_BAJISTA",
        ]
    ):
        if calidad_setup in [
            "PREMIUM",
            "BUENA",
        ]:
            return None

        return "ESPERANDO_CONFIRMACION_RECHAZO"

    # ========================================================
    # SETUPS MEDIOS
    # ========================================================
    if calidad_setup == "MEDIA":
        return "ESPERANDO_CONFIRMACION_RECHAZO"

    return None
def procesar_senales_pendientes(abrir_operacion):
    import time
    import estado
    from config import (
        CANDLE_TIME,
        MAX_OPERACIONES_ABIERTAS,
        VENTANA_ENTRADA_INICIO,
        VENTANA_ENTRADA_FIN
    )
    from utils import segundo_actual
    if not estado.senales_pendientes:
        return 0

    abiertas = 0
    restantes = []

    try:
        timestamp_iq = float(
            estado.Iq.get_server_timestamp()
        )
        if timestamp_iq > 10_000_000_000:
            timestamp_iq /= 1000.0
        if timestamp_iq <= 0:
            raise ValueError("timestamp IQ inválido")
    except Exception:
        timestamp_iq = time.time()

    vela_actual = int(
        timestamp_iq // CANDLE_TIME
    )
    segundo = segundo_actual()

    for senal in estado.senales_pendientes:
        try:
            activo = senal["activo"]
            direccion = senal["direccion"]
            patron = str(senal.get("patron", "")).lower()
            accion_precio = str(senal.get("accion_precio", "")).upper()
            tipo_ruptura = str(senal.get("tipo_ruptura", "SIN_DATOS")).lower()
            ruptura_confirmada = senal.get("ruptura_confirmada", False)
            motivo_pendiente = senal.get("motivo_pendiente", "ENTRADA_NORMAL")
            requiere_protocolo_cerebro = _bool(
                senal.get(
                    "requiere_protocolo_cerebro",
                    False,
                )
            )

            decision_cerebro = str(
                senal.get(
                    "cerebro_unico_decision",
                    "",
                )
                or ""
            ).upper().strip()

            # ========================================================
            # PENDIENTES EXCLUSIVAS DEL CEREBRO
            # ========================================================
            # Desde la arquitectura V3 una pendiente solo puede
            # existir si el Cerebro autorizó OPERAR_CON_PROTOCOLO.
            #
            # Cualquier pendiente antigua/legacy queda fuera de
            # la ruta LIVE y no puede llegar a las validaciones
            # históricas que todavía existen más abajo.
            if (
                not requiere_protocolo_cerebro
                or decision_cerebro != "OPERAR_CON_PROTOCOLO"
            ):
                print(
                    "SEÑAL PENDIENTE LEGACY DESCARTADA:",
                    activo,
                    "| decision:",
                    decision_cerebro or "VACIA",
                )
                continue

            # ========================================================
            # PASO 5.4A — VETO LEGACY SIN AUTORIDAD SOBRE EL CEREBRO
            # ========================================================
            if (
                motivo_pendiente
                == "CANCELAR_PROTOCOLO_RIESGO_CRITICO"
                and not requiere_protocolo_cerebro
            ):
                senal[
                    "entrada_auditoria_veto_setup_bypass_cerebro"
                ] = False

                print(
                    "SEÑAL PENDIENTE CANCELADA POR "
                    "RIESGO CRÍTICO DE SETUP:",
                    activo,
                )
                continue

            if (
                motivo_pendiente
                == "CANCELAR_PROTOCOLO_RIESGO_CRITICO"
                and requiere_protocolo_cerebro
            ):
                senal[
                    "entrada_auditoria_veto_setup_bypass_cerebro"
                ] = True

                print(
                    "VETO LEGACY DE RIESGO OMITIDO "
                    "POR AUTORIDAD DEL CEREBRO:",
                    activo,
                    "| señal continúa a motor_protocolos.py",
                )

            pendiente_por_ruptura = motivo_pendiente in [
                "ESPERANDO_RUPTURA_RESISTENCIA",
                "ESPERANDO_RUPTURA_SOPORTE"
            ]

            if len(estado.operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
                restantes.append(senal)
                continue

            if any(op["activo"] == activo for op in estado.operaciones_abiertas):
                continue

            if vela_actual <= senal["vela_detectada"]:
                restantes.append(senal)
                continue

            # ========================================================
            # EXPIRACIÓN LEGACY
            # ========================================================
            #
            # Las señales controladas por motor_protocolos.py
            # NO pueden expirar por una ventana inventada aquí.
            #
            # Su ventana temporal pertenece al protocolo.
            # ========================================================

            if not requiere_protocolo_cerebro:
                max_velas_pendiente = (
                    3
                    if pendiente_por_ruptura
                    else 2
                )

                if (
                    vela_actual
                    - senal["vela_detectada"]
                    > max_velas_pendiente
                ):
                    print(
                        "SEÑAL PENDIENTE EXPIRADA:",
                        activo
                    )
                    continue

            if segundo < VENTANA_ENTRADA_INICIO:
                restantes.append(senal)
                continue

            if segundo > VENTANA_ENTRADA_FIN:
                if requiere_protocolo_cerebro:
                    # No destruir la señal.
                    # Esperamos la próxima ventana de evaluación.
                    restantes.append(senal)
                    continue

                print(
                    "SEÑAL PENDIENTE CANCELADA POR TIEMPO:",
                    activo
                )
                continue

            # ========================================================
            # UNA EVALUACIÓN PRODUCTIVA POR VELA CERRADA
            # ========================================================
            # motor_protocolos.py trabaja exclusivamente con velas
            # cerradas. Mientras seguimos dentro del mismo bucket,
            # el conjunto de velas cerradas no puede cambiar.
            #
            # Evitamos repetir get_candles() y todo el protocolo
            # varias veces sobre exactamente la misma información.
            # Si una consulta previa falló, este campo no se actualiza
            # y el siguiente loop conserva la posibilidad de reintento.
            ultimo_bucket_evaluado = senal.get(
                "protocolo_live_ultimo_bucket_evaluado"
            )

            if ultimo_bucket_evaluado == vela_actual:
                restantes.append(senal)
                continue

            # ========================================================
            # PASO 5.5C — SOLO VELAS CERRADAS PARA EL PROTOCOLO
            # ========================================================
            
            try:
                ahora_protocolo = float(
                    estado.Iq.get_server_timestamp()
                )
                if ahora_protocolo > 10_000_000_000:
                    ahora_protocolo /= 1000.0
                if ahora_protocolo <= 0:
                    raise ValueError(
                        "timestamp IQ inválido"
                    )
            except Exception:
                ahora_protocolo = time.time()
            
            candles = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                8,
                ahora_protocolo,
                timeout=3.0,
                drain_timeout=1.0,
            )
            
            if not candles or len(candles) < 4:
                restantes.append(senal)
                continue
            
            candles = sorted(
                candles,
                key=lambda x: x["from"]
            )
            
            # --------------------------------------------------------
            # IMPORTANTE:
            #
            # IQ puede devolver como última vela la vela que está
            # formándose en este mismo instante.
            #
            # BACKTEST trabaja con velas históricas ya cerradas.
            #
            # Por paridad, motor_protocolos.py solo puede recibir
            # velas cuyo periodo ya terminó.
            # --------------------------------------------------------
            
            bucket_actual = int(
                ahora_protocolo // CANDLE_TIME
            )
            
            candles_protocolo = []
            
            for vela in candles:
                try:
                    bucket_vela = int(
                        float(vela["from"])
                        // CANDLE_TIME
                    )
                except Exception:
                    continue
            
                if bucket_vela < bucket_actual:
                    candles_protocolo.append(
                        vela
                    )
            
            if len(candles_protocolo) < 4:
                restantes.append(senal)
                continue

            ultima_cerrada_from = int(
                float(
                    candles_protocolo[-1]["from"]
                )
            )

            ultima_cerrada_esperada = (
                (bucket_actual - 1)
                * CANDLE_TIME
            )

            # No congelar este bucket si IQ respondió con un
            # bloque atrasado. La señal sigue pendiente y puede
            # reintentarse dentro del mismo minuto hasta recibir
            # la última vela realmente cerrada.
            if (
                ultima_cerrada_from
                != ultima_cerrada_esperada
            ):
                print(
                    "PROTOCOLO LIVE — VELAS ATRASADAS:",
                    activo,
                    "| ultima:",
                    ultima_cerrada_from,
                    "| esperada:",
                    ultima_cerrada_esperada,
                )
                restantes.append(senal)
                continue
            
            senal[
                "auditoria_5_5c_solo_velas_cerradas"
            ] = True
            
            senal[
                "auditoria_5_5c_bucket_actual"
            ] = bucket_actual
            
            senal[
                "auditoria_5_5c_ultima_vela_cerrada_from"
            ] = ultima_cerrada_from
            
            # ========================================================
            # PASO 5 — PARIDAD BACKTEST ↔ LIVE (SOLO SOMBRA)
            # ========================================================
            # NO abre operaciones, NO cancela señales y NO sustituye
            # todavía la lógica LIVE existente. Solo registra qué
            # habría decidido motor_protocolos.py con las velas
            # disponibles en este instante.
            # ========================================================
            try:
                print(
                    "PARIDAD VELAS 5.5C:",
                    activo,
                    "| vela actual bucket:",
                    bucket_actual,
                    "| ultima cerrada from:",
                    senal.get(
                        "auditoria_5_5c_ultima_vela_cerrada_from"
                    ),
                    "| velas IQ:",
                    len(candles),
                    "| velas cerradas:",
                    len(candles_protocolo),
                )
                protocolo_live = evaluar_protocolo_live_sombra(
                    candles_protocolo,
                    senal,
                    CANDLE_TIME,
                )

                # Solo marcar el bucket como evaluado después de que
                # obtuvimos velas suficientes y motor_protocolos
                # respondió correctamente. Los fallos de API o de
                # evaluación permanecen reintentables.
                senal[
                    "protocolo_live_ultimo_bucket_evaluado"
                ] = bucket_actual

                senal["protocolo_live_sombra_estado"] = (
                    protocolo_live.get("estado", "SIN_DATOS")
                )
                senal["protocolo_live_sombra_motivo"] = (
                    protocolo_live.get("motivo", "")
                )
                senal["protocolo_live_sombra_espera"] = (
                    protocolo_live.get("espera_velas", -1)
                )
                senal["protocolo_live_sombra_tipo"] = (
                    protocolo_live.get("protocolo", "")
                )

                # D8-E6.1 — conservar la acción de confirmación
                # que motor_protocolos calculó sobre su copia interna.
                # Solo trazabilidad; no participa en una nueva decisión.
                if protocolo_live.get(
                    "accion_confirmacion_ia",
                    "",
                ):
                    senal["accion_confirmacion_ia"] = (
                        protocolo_live.get(
                            "accion_confirmacion_ia",
                            "",
                        )
                    )

                senal["protocolo_live_sombra_idx_entrada"] = (
                    protocolo_live.get("idx_entrada", None)
                )
                # ============================================================
                # PASO 5.5B — VELA EXACTA DE CONFIRMACIÓN DEL PROTOCOLO
                # ============================================================
                
                idx_entrada_live = senal.get(
                    "protocolo_live_sombra_idx_entrada"
                )
                
                senal["protocolo_live_vela_entrada_from"] = None
                senal["protocolo_live_vela_entrada_open"] = None
                senal["protocolo_live_vela_entrada_close"] = None
                senal["protocolo_live_vela_entrada_high"] = None
                senal["protocolo_live_vela_entrada_low"] = None
                senal["protocolo_live_espera_timestamp"] = -1
                
                if (
                    isinstance(idx_entrada_live, int)
                    and 0 <= idx_entrada_live < len(
                        candles_protocolo
                    )
                ):
                    vela_entrada_live = (
                        candles_protocolo[
                            idx_entrada_live
                        ]
                    )
                
                    try:
                        vela_entrada_from = int(
                            float(
                                vela_entrada_live["from"]
                            )
                        )
                
                        senal[
                            "protocolo_live_vela_entrada_from"
                        ] = vela_entrada_from
                
                        senal[
                            "protocolo_live_vela_entrada_open"
                        ] = float(
                            vela_entrada_live["open"]
                        )
                
                        senal[
                            "protocolo_live_vela_entrada_close"
                        ] = float(
                            vela_entrada_live["close"]
                        )
                
                        senal[
                            "protocolo_live_vela_entrada_high"
                        ] = float(
                            vela_entrada_live["max"]
                        )
                
                        senal[
                            "protocolo_live_vela_entrada_low"
                        ] = float(
                            vela_entrada_live["min"]
                        )
                
                        vela_senal_from = int(
                            float(
                                senal.get(
                                    "vela_senal_from",
                                    0,
                                )
                                or 0
                            )
                        )
                
                        if vela_senal_from > 0:
                            senal[
                                "protocolo_live_espera_timestamp"
                            ] = int(
                                (
                                    vela_entrada_from
                                    - vela_senal_from
                                )
                                // CANDLE_TIME
                            )
                
                    except Exception as e:
                        print(
                            "ERROR AUDITORIA 5.5B:",
                            activo,
                            e,
                        )
                print(
                    "PROTOCOLO LIVE SOMBRA:",
                    activo,
                    "| estado:",
                    senal["protocolo_live_sombra_estado"],
                    "| protocolo:",
                    senal["protocolo_live_sombra_tipo"],
                    "| espera motor:",
                    senal["protocolo_live_sombra_espera"],
                    "| idx entrada:",
                    senal["protocolo_live_sombra_idx_entrada"],
                    "| vela señal from:",
                    senal.get(
                        "vela_senal_from",
                        0,
                    ),
                    "| vela entrada from:",
                    senal.get(
                        "protocolo_live_vela_entrada_from"
                    ),
                    "| espera timestamp:",
                    senal.get(
                        "protocolo_live_espera_timestamp",
                        -1,
                    ),
                    "| motivo:",
                    senal["protocolo_live_sombra_motivo"],
                )

            except Exception as e:
                # La auditoría sombra nunca puede romper el flujo LIVE.
                senal["protocolo_live_sombra_estado"] = "ERROR"
                senal["protocolo_live_sombra_motivo"] = str(e)
                senal["protocolo_live_sombra_espera"] = -1
                senal["protocolo_live_sombra_tipo"] = ""
                senal["protocolo_live_sombra_idx_entrada"] = None
                senal["protocolo_live_vela_entrada_from"] = None
                senal["protocolo_live_vela_entrada_open"] = None
                senal["protocolo_live_vela_entrada_close"] = None
                senal["protocolo_live_vela_entrada_high"] = None
                senal["protocolo_live_vela_entrada_low"] = None
                senal["protocolo_live_espera_timestamp"] = -1
                print(
                    "ERROR PROTOCOLO LIVE SOMBRA:",
                    activo,
                    e,
                )

            # ========================================================
            # PASO 5.4B — AUTORIDAD OPERATIVA DEL PROTOCOLO
            # ========================================================
            # Solo aplica a señales que el Cerebro clasificó como
            # OPERAR_CON_PROTOCOLO.
            #
            # motor_protocolos.py decide.
            # entrada.py ejecuta.
            # ========================================================
            if requiere_protocolo_cerebro:
                estado_protocolo = str(
                    senal.get(
                        "protocolo_live_sombra_estado",
                        "SIN_DATOS",
                    )
                    or "SIN_DATOS"
                ).upper().strip()

                motivo_protocolo = str(
                    senal.get(
                        "protocolo_live_sombra_motivo",
                        "",
                    )
                    or ""
                )

                if estado_protocolo in [
                    "SIN_DATOS",
                    "SENAL_NO_ENCONTRADA",
                    "ERROR",
                ]:
                    registrar_paridad_protocolo_live(
                        senal,
                        "SIN_DATOS",
                        motivo_protocolo,
                    )
                    restantes.append(senal)
                    continue

                if estado_protocolo == "ESPERAR":
                    registrar_paridad_protocolo_live(
                        senal,
                        "ESPERAR",
                        motivo_protocolo,
                    )
                    restantes.append(senal)
                    continue

                if estado_protocolo == "CANCELADA":
                    registrar_paridad_protocolo_live(
                        senal,
                        "NO_OPERAR",
                        motivo_protocolo,
                    )
                    print(
                        "SEÑAL CANCELADA POR PROTOCOLO:",
                        activo,
                        "|",
                        motivo_protocolo,
                    )
                    continue

                if estado_protocolo == "CONFIRMACION_PASADA":
                    registrar_paridad_protocolo_live(
                        senal,
                        "NO_OPERAR",
                        motivo_protocolo,
                    )
                    print(
                        "SEÑAL DESCARTADA — CONFIRMACIÓN YA PASÓ:",
                        activo,
                        "|",
                        motivo_protocolo,
                    )
                    continue

                if estado_protocolo == "CONFIRMADA":
                    senal["protocolo_confirmado"] = True
                    senal["entrada_confirmada"] = True
                    senal[
                        "motivo_confirmacion_protocolo_live"
                    ] = motivo_protocolo
                    senal[
                        "tipo_protocolo_live"
                    ] = senal.get(
                        "protocolo_live_sombra_tipo",
                        "",
                    )

                    # C-C2 LIVE:
                    # recuperar exactamente la auditoría generada
                    # por motor_protocolos antes de consultar
                    # aprendizaje post-protocolo.
                    auditoria_protocolo = protocolo_live.get(
                        "auditoria_protocolo",
                        {},
                    )

                    if isinstance(
                        auditoria_protocolo,
                        dict,
                    ):
                        for clave, valor in (
                            auditoria_protocolo.items()
                        ):
                            if str(clave).startswith(
                                "auditoria_protocolo_"
                            ):
                                senal[clave] = valor

                    decision_post = evaluar_decision_post_protocolo(
                        senal
                    )

                    senal["decision_post_protocolo"] = decision_post.get(
                        "decision_post_protocolo",
                        "SIN_DATOS",
                    )
                    senal["autoriza_post_protocolo"] = decision_post.get(
                        "autoriza_post_protocolo",
                        True,
                    )
                    senal["probabilidad_post_protocolo"] = decision_post.get(
                        "probabilidad_post_protocolo",
                        0,
                    )
                    senal[
                        "intervalo_post_protocolo_inferior"
                    ] = decision_post.get(
                        "intervalo_post_protocolo_inferior",
                        0,
                    )
                    senal[
                        "intervalo_post_protocolo_superior"
                    ] = decision_post.get(
                        "intervalo_post_protocolo_superior",
                        0,
                    )
                    senal["muestra_post_protocolo"] = decision_post.get(
                        "muestra_post_protocolo",
                        0,
                    )
                    senal[
                        "confiabilidad_post_protocolo"
                    ] = decision_post.get(
                        "confiabilidad_post_protocolo",
                        "SIN_DATOS",
                    )
                    senal[
                        "fuente_post_protocolo_principal"
                    ] = decision_post.get(
                        "fuente_post_protocolo_principal"
                    )
                    senal[
                        "fuente_post_protocolo_respaldo"
                    ] = decision_post.get(
                        "fuente_post_protocolo_respaldo"
                    )

                    print(
                        "PROTOCOLO AUTORIZÓ ENTRADA:",
                        activo,
                        "| protocolo:",
                        senal.get(
                            "protocolo_live_sombra_tipo",
                            "",
                        ),
                        "| espera:",
                        senal.get(
                            "protocolo_live_sombra_espera",
                            -1,
                        ),
                        "| motivo:",
                        motivo_protocolo,
                    )

                    registrar_paridad_protocolo_live(
                        senal,
                        "ENTRAR",
                        motivo_protocolo,
                    )

                    if abrir_operacion(senal):
                        abiertas += 1

                    continue

                print(
                    "ESTADO DE PROTOCOLO DESCONOCIDO:",
                    activo,
                    estado_protocolo,
                )
                restantes.append(senal)
                continue

            # ========================================================
            # LIMPIEZA ARQUITECTURA V3 — RUTA LEGACY ELIMINADA
            # ========================================================
            # Todas las señales que llegan a este punto fueron
            # autorizadas como OPERAR_CON_PROTOCOLO.
            #
            # motor_protocolos.py ya resolvió:
            #   CONFIRMADA / ESPERAR / CANCELADA /
            #   CONFIRMACION_PASADA.
            #
            # No existe una segunda evaluación de entrada debajo
            # de esta capa.
            continue

        except Exception as e:
            print(
                "Error procesando señal pendiente:",
                senal.get("activo", ""),
                e,
            )
        
            # ========================================================
            # F5.5 — NO PERDER PENDIENTES POR ERROR TRANSITORIO API
            # ========================================================
            #
            # Una caída entre el check_connect() de bot.py y una
            # consulta get_candles() no puede destruir una señal
            # todavía pendiente.
            #
            # La reconexión pertenece a bot.py. Aquí solamente
            # preservamos la señal para la próxima iteración.
            # ========================================================
        
            if senal not in restantes:
                restantes.append(senal)

    estado.senales_pendientes = restantes

    return abiertas
