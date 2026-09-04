import time
import estado
from config import (
    CANDLE_TIME,
    VENTANA_ENTRADA_INICIO,
    VENTANA_ENTRADA_FIN,
    FUERZA_MAXIMA_VELA_NORMAL,
    SEGUNDO_MAXIMO_VELA_CORRIDA
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

def es_pullback_bajista_fuerte(senal):
    try:
        return (
            "pullback bajista" in str(senal.get("patron", "")).lower()
            and senal.get("puntaje", 0) >= 20
            and senal.get("prioridad", 0) >= 3
            and senal.get("tipo_mercado") == "TENDENCIA_BAJISTA"
            and senal.get("calidad_mercado") in ["LIMPIO", "NORMAL"]
            and str(senal.get("estado_tendencia", "")).startswith("BAJISTA")
        )
    except Exception:
        return False

def validar_vela_exacta_entrada(activo, direccion):
    try:
        candles = estado.Iq.get_candles(activo, CANDLE_TIME, 8, time.time())

        if not candles or len(candles) < 4:
            return False, "velas insuficientes"

        candles = sorted(candles, key=lambda x: x["from"])

        actual = candles[-1]
        anterior = candles[-2]

        o = float(actual["open"])
        c = float(actual["close"])
        h = float(actual["max"])
        l = float(actual["min"])
        ac = float(anterior["close"])

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return False, "rango inválido"

        fuerza = cuerpo / rango
        posicion = (c - l) / rango

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        vela_verde = c > o
        vela_roja = c < o

        if fuerza < 0.06:
            return False, "vela débil o indecisa"

        if direccion == "call":
            if vela_roja and not (mecha_inf >= cuerpo * 0.9 and posicion >= 0.30):
                return False, "CALL sin recuperación compradora"

            if posicion >= 0.98 and fuerza >= 0.72:
                return False, "CALL tarde cerca del máximo"

            if mecha_sup >= cuerpo * 4.0 and fuerza < 0.25:
                return False, "absorción vendedora fuerte"

            return True, "vela exacta CALL válida"

        if direccion == "put":
            if vela_verde and not (mecha_sup >= cuerpo * 0.9 and posicion <= 0.70):
                return False, "PUT sin rechazo vendedor"

            if posicion <= 0.02 and fuerza >= 0.72:
                return False, "PUT tarde cerca del mínimo"

            if mecha_inf >= cuerpo * 4.0 and fuerza < 0.25:
                return False, "absorción compradora fuerte"

            return True, "vela exacta PUT válida"

        return False, "dirección inválida"

    except Exception as e:
        print("Error validando vela exacta:", activo, e)
        return False, "error validando vela"
def validar_microestructura_entrada(
    direccion,
    opens,
    closes,
    highs,
    lows
):
    try:
        ultimas = 4

        velas = []

        for i in range(-ultimas, 0):
            o = opens[i]
            c = closes[i]
            h = highs[i]
            l = lows[i]

            rango = h - l

            if rango <= 0:
                continue

            cuerpo = abs(c - o)

            fuerza = cuerpo / rango

            velas.append({
                "alcista": c > o,
                "bajista": c < o,
                "fuerza": fuerza,
                "mecha_sup": h - max(o, c),
                "mecha_inf": min(o, c) - l,
                "cuerpo": cuerpo
            })

        if len(velas) < 3:
            return False, "microestructura insuficiente"

        alcistas = sum(1 for v in velas if v["alcista"])
        bajistas = sum(1 for v in velas if v["bajista"])

        fuerza_promedio = sum(v["fuerza"] for v in velas) / len(velas)

        ultima = velas[-1]

        # =========================
        # CALL
        # =========================
        if direccion == "call":

            # Ya no exigir perfección.
            if alcistas >= 2 and fuerza_promedio >= 0.22:

                # Bloquea solo absorción MUY fuerte.
                if (
                    ultima["mecha_sup"] >= ultima["cuerpo"] * 2.8
                    and ultima["fuerza"] < 0.28
                ):
                    return False, "absorción vendedora fuerte"

                return True, "microestructura alcista válida"

        # =========================
        # PUT
        # =========================
        if direccion == "put":

            if bajistas >= 2 and fuerza_promedio >= 0.22:

                if (
                    ultima["mecha_inf"] >= ultima["cuerpo"] * 2.8
                    and ultima["fuerza"] < 0.28
                ):
                    return False, "absorción compradora fuerte"

                return True, "microestructura bajista válida"

        return False, "microestructura débil"

    except Exception as e:
        print("Error validando microestructura:", e)
        return False, "error microestructura"


def decidir_entrada(activo, direccion, candles, precio_referencia):
    try:
        candles = sorted(candles, key=lambda x: x["from"])

        if len(candles) < 4:
            return "esperar", "velas insuficientes"

        vela_actual = candles[-1]
        vela_anterior = candles[-2]

        o = float(vela_actual["open"])
        c = float(vela_actual["close"])
        h = float(vela_actual["max"])
        l = float(vela_actual["min"])

        ac = float(vela_anterior["close"])
        ah = float(vela_anterior["max"])
        al = float(vela_anterior["min"])

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return "esperar", "rango inválido"

        fuerza = cuerpo / rango

        mecha_superior = h - max(o, c)
        mecha_inferior = min(o, c) - l

        posicion = (c - l) / rango
        cerca_high = posicion >= 0.88
        cerca_low = posicion <= 0.12

        vela_verde = c > o
        vela_roja = c < o

        segundo = segundo_actual()

        if precio_referencia is not None:
            movimiento = abs(c - precio_referencia)

            if movimiento > rango * 1.20:
                return "cancelar", "precio se alejó demasiado"

        if segundo > VENTANA_ENTRADA_FIN + 10:
           return "cancelar", "se pasó la ventana segura"

        # Evitar entrar en vela ya explotada.
        if fuerza > FUERZA_MAXIMA_VELA_NORMAL and segundo > SEGUNDO_MAXIMO_VELA_CORRIDA:
            return "cancelar", "vela demasiado corrida"
        # =========================
        # CALL
        # =========================
        if direccion == "call":
            rechazo_comprador = (
                mecha_inferior >= cuerpo * 1.2
                and posicion >= 0.42
                and fuerza >= 0.14
            )

            recuperacion = (
                c > ac
                and posicion >= 0.40
                and fuerza >= 0.14
                and not cerca_high
            )

            ruptura_controlada = (
                c > ah
                and fuerza <= 0.72
                and segundo <= 28
                and not cerca_high
            )

            continuacion_sana = (
                vela_verde
                and c > ac
                and 0.16 <= fuerza <= 0.72
                and posicion < 0.84
            )

            if cerca_high and fuerza >= 0.75:
                return "esperar", "CALL alto en vela, esperar retroceso"

            if rechazo_comprador:
                return "entrar", "CALL por rechazo comprador confirmado"

            if ruptura_controlada:
                return "entrar", "CALL por ruptura controlada"

            if continuacion_sana:
                return "entrar", "CALL por continuación sana"

            if recuperacion:
                return "entrar", "CALL por recuperación"

            return "esperar", "CALL sin confirmación suficiente"

        # =========================
        # PUT
        # =========================
        if direccion == "put":
            rechazo_vendedor = (
                mecha_superior >= cuerpo * 1.2
                and posicion <= 0.58
                and fuerza >= 0.14
            )

            recuperacion_bajista = (
                c < ac
                and posicion <= 0.60
                and fuerza >= 0.14
                and not cerca_low
            )

            ruptura_controlada = (
                c < al
                and fuerza <= 0.72
                and segundo <= 28
                and not cerca_low
            )

            continuacion_sana = (
                vela_roja
                and c < ac
                and 0.16 <= fuerza <= 0.72
                and posicion > 0.16
            )

            if cerca_low and fuerza >= 0.75:
                return "esperar", "PUT bajo en vela, esperar retroceso"

            if rechazo_vendedor:
                return "entrar", "PUT por rechazo vendedor confirmado"

            if ruptura_controlada:
                return "entrar", "PUT por ruptura controlada"

            if continuacion_sana:
                return "entrar", "PUT por continuación sana"

            if recuperacion_bajista:
                return "entrar", "PUT por recuperación bajista"

            return "esperar", "PUT sin confirmación suficiente"

        return "cancelar", "dirección inválida"

    except Exception as e:
        print("Error decidiendo entrada:", activo, e)
        return "cancelar", "error decidiendo entrada"

def esperar_mejor_entrada(senal):
    activo = senal["activo"]
    direccion = senal["direccion"]

    print("Buscando mejor punto de entrada:", activo, direccion)

    tiempo_inicio = time.time()
    precio_referencia = None
    TIEMPO_MAXIMO_ESPERA = 6

    while True:
        segundo = segundo_actual()

        if segundo < 4:
            time.sleep(0.07)
            continue

        if segundo > 38:
            print("Entrada cancelada:", activo, "se pasó la ventana segura")
            return False

        if time.time() - tiempo_inicio > TIEMPO_MAXIMO_ESPERA:
            print("Entrada cancelada:", activo, "no confirmó rápido")
            return False

        try:
            candles = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                8,
                time.time(),
                timeout=1.5,
            )

            if not candles or len(candles) < 4:
                time.sleep(0.07)
                continue

            candles = sorted(candles, key=lambda x: x["from"])
            precio_actual = float(candles[-1]["close"])

            if precio_referencia is None:
                precio_referencia = precio_actual

            decision, razon_decision = decidir_entrada(
                activo,
                direccion,
                candles,
                precio_referencia
            )

            if decision == "cancelar":
                print("Entrada cancelada:", activo, razon_decision)
                return False

            if decision == "esperar":
                time.sleep(0.07)
                continue

            if decision == "entrar":
                ok_vela, razon_vela = validar_vela_exacta_entrada(
                    activo,
                    direccion
                )

                if not ok_vela:
                    print("Entrada bloqueada:", activo, razon_vela)
                    return False

                ok_micro, razon_micro = validar_microestructura_entrada(
                    direccion,
                    [x["open"] for x in candles],
                    [x["close"] for x in candles],
                    [x["max"] for x in candles],
                    [x["min"] for x in candles]
                )

                if not ok_micro:
                    print("Microestructura bloqueada:", activo, razon_micro)
                    return False

                print(
                    "Entrada",
                    direccion.upper(),
                    "confirmada:",
                    activo,
                    "| segundo:", segundo,
                    "| decisión:", razon_decision,
                    "| vela:", razon_vela,
                    "| micro:", razon_micro
                )

                return True

        except Exception as e:
            print("Error buscando mejor entrada:", activo, e)
            return False

        time.sleep(0.07)

def guardar_senal_pendiente(senal, motivo_pendiente="ENTRADA_NORMAL"):
    import time
    import estado
    from config import CANDLE_TIME

    activo = senal["activo"]

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
    from entrada import (
        decidir_entrada,
        validar_vela_exacta_entrada,
        validar_microestructura_entrada,
        validar_punto_entrada_en_vela
    )

    if not estado.senales_pendientes:
        return 0

    abiertas = 0
    restantes = []
    vela_actual = int(time.time() // CANDLE_TIME)
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
            pullback_bajista_fuerte = es_pullback_bajista_fuerte(senal)

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
            # PASO 5.5C — SOLO VELAS CERRADAS PARA EL PROTOCOLO
            # ========================================================
            
            ahora_protocolo = time.time()
            
            candles = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                8,
                ahora_protocolo,
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
            
            senal[
                "auditoria_5_5c_solo_velas_cerradas"
            ] = True
            
            senal[
                "auditoria_5_5c_bucket_actual"
            ] = bucket_actual
            
            senal[
                "auditoria_5_5c_ultima_vela_cerrada_from"
            ] = int(
                float(
                    candles_protocolo[-1]["from"]
                )
            )
            
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

            # =========================
            # RESOLVER PENDIENTE POR ZONA
            # =========================
            if pendiente_por_ruptura:
                from zonas import resolver_zona_pendiente

                opens = [float(x["open"]) for x in candles]
                closes = [float(x["close"]) for x in candles]
                highs = [float(x["max"]) for x in candles]
                lows = [float(x["min"]) for x in candles]

                soporte = senal.get("soporte")
                resistencia = senal.get("resistencia")
                vol = senal.get("vol", 0)

                if soporte is None or resistencia is None:
                    print("SEÑAL PENDIENTE CANCELADA:", activo, "sin soporte/resistencia guardados")
                    continue

                resolucion = resolver_zona_pendiente(
                    direccion,
                    opens,
                    closes,
                    highs,
                    lows,
                    soporte,
                    resistencia,
                    vol
                )

                estado_resolucion = resolucion.get("estado")

                if estado_resolucion == "CANCELAR":
                    print("SEÑAL PENDIENTE CANCELADA:", activo, resolucion.get("razon", ""))
                    continue

                if estado_resolucion == "ESPERAR":
                    restantes.append(senal)
                    continue

                if estado_resolucion == "OPERAR_CONTRARIO":
                    # Una confirmación de entrada no puede invertir CALL/PUT.
                    # La nueva dirección tendría que volver a ser evaluada
                    # por el Cerebro Único como una señal distinta.
                    print(
                        "SEÑAL PENDIENTE CANCELADA POR DIRECCIÓN CONTRARIA:",
                        activo,
                        "|",
                        resolucion.get("razon", ""),
                    )
                    continue

                elif estado_resolucion == "OPERAR":
                    senal["ruptura_confirmada"] = True
                    senal["entrada_confirmada"] = True
                    senal["tipo_ruptura"] = resolucion.get("tipo", "SIN_DATOS")
                    senal["razon_ruptura"] = resolucion.get("razon", "")
                    senal["motivo_pendiente"] = "RESUELTA_RUPTURA"

                    ruptura_confirmada = True
                    tipo_ruptura = str(senal.get("tipo_ruptura", "SIN_DATOS")).lower()

                    print("SEÑAL PENDIENTE RESUELTA:", activo, resolucion.get("razon", ""))

            # =========================
            # VALIDAR PUNTO DE ENTRADA
            # =========================
            ok_punto, razon_punto = validar_punto_entrada_en_vela(
                direccion,
                candles
            )

            if not ok_punto:
                if senal.get("entrada_confirmada", False):
                    print(
                        "SEÑAL PENDIENTE FLEXIBLE permitió punto por zona confirmada:",
                        activo,
                        razon_punto
                    )

                elif pendiente_por_ruptura and (
                    "precio demasiado arriba" in razon_punto.lower()
                    or "precio demasiado abajo" in razon_punto.lower()
                ):
                    print(
                        "SEÑAL PENDIENTE FLEXIBLE permitió ruptura confirmada:",
                        activo,
                        razon_punto
                    )

                elif pullback_bajista_fuerte and (
                    "vela verde sin rechazo real" in razon_punto.lower()
                    or "precio demasiado abajo" in razon_punto.lower()
                ):
                    print(
                        "SEÑAL PENDIENTE FLEXIBLE permitió punto pullback bajista:",
                        activo,
                        razon_punto
                    )

                else:
                    print("SEÑAL PENDIENTE BLOQUEADA:", activo, razon_punto)
                    continue
            # =========================
            # CEREBRO DE ENTRADA
            # =========================
            # Se mantiene como diagnóstico. La autoridad operativa
            # permanece en las validaciones técnicas reales de
            # entrada.py.
            confirmacion = evaluar_confirmacion_entrada(
                senal,
                candles,
                segundo
            )

            senal["entrada_cerebro_accion"] = confirmacion.get(
                "accion",
                "",
            )
            senal["entrada_cerebro_indice"] = confirmacion.get(
                "indice",
                0,
            )
            senal["entrada_cerebro_nivel"] = confirmacion.get(
                "nivel",
                "",
            )
            senal["entrada_cerebro_motivos"] = " | ".join(
                confirmacion.get("motivos", [])
            )

            senal["entrada_cerebro_accion_diagnostico"] = (
                confirmacion.get(
                    "accion_diagnostico",
                    confirmacion.get("accion", ""),
                )
            )
            senal["entrada_cerebro_indice_diagnostico"] = (
                confirmacion.get(
                    "indice_diagnostico",
                    confirmacion.get("indice", 0),
                )
            )
            senal["entrada_cerebro_nivel_diagnostico"] = (
                confirmacion.get(
                    "nivel_diagnostico",
                    confirmacion.get("nivel", ""),
                )
            )
            senal["entrada_cerebro_intermedio_operativo"] = (
                ENTRADA_CEREBRO_INTERMEDIO_OPERATIVO
            )

            if ENTRADA_CEREBRO_INTERMEDIO_OPERATIVO:
                if confirmacion.get("accion") == "CANCELAR":
                    print(
                        "SEÑAL PENDIENTE CANCELADA POR CEREBRO ENTRADA:",
                        activo,
                        confirmacion.get("indice"),
                        "|",
                        senal["entrada_cerebro_motivos"]
                    )
                    continue

                if confirmacion.get("accion") == "ESPERAR":
                    print(
                        "SEÑAL PENDIENTE ESPERA POR CEREBRO ENTRADA:",
                        activo,
                        confirmacion.get("indice"),
                        "|",
                        senal["entrada_cerebro_motivos"]
                    )
                    restantes.append(senal)
                    continue

            # =========================
            # DECISIÓN DE ENTRADA
            # =========================
            decision, razon = decidir_entrada(
                activo,
                direccion,
                candles,
                None
            )

            if decision != "entrar":
        
                 razon_lower = razon.lower()
             
                 if (
                     "precio demasiado arriba" in razon_lower
                     or "precio demasiado abajo" in razon_lower
                     or "alto en vela" in razon_lower
                     or "bajo en vela" in razon_lower
                     or "esperar retroceso" in razon_lower
                     or "vela demasiado corrida" in razon_lower
                 ):
                     print(
                         "SEÑAL PENDIENTE ESPERA RETEST:",
                         activo,
                         razon
                     )
             
                     restantes.append(senal)
                     continue
             
                 print(
                     "SEÑAL PENDIENTE DESCARTADA:",
                     activo,
                     razon
                 )
             
                 continue

            # =========================
            # BLOQUEO POR ZONA CONTRARIA
            # =========================
            zona_contraria_peligrosa = False

            if direccion == "call" and "CALL_RESISTENCIA_CERCA_SIN_RUPTURA" in accion_precio:
                zona_contraria_peligrosa = True

            if direccion == "put" and "PUT_SOPORTE_CERCA_SIN_RUPTURA" in accion_precio:
                zona_contraria_peligrosa = True

            es_breakout_retest = (
                "breakout" in patron
                or "retest" in patron
                or "ruptura" in patron
                or "breakout" in tipo_ruptura
                or "retest" in tipo_ruptura
                or ruptura_confirmada
                or senal.get("entrada_confirmada", False)
            )

            if zona_contraria_peligrosa and not es_breakout_retest:
                confirmacion_fuerte = (
                    "rechazo" in razon.lower()
                    or "ruptura" in razon.lower()
                    or "recuperación" in razon.lower()
                    or "recuperacion" in razon.lower()
                )

                if not confirmacion_fuerte:
                    registrar_paridad_protocolo_live(
                        senal,
                        "BLOQUEAR",
                        "zona contraria cerca sin ruptura/retest real",
                    )
                    print(
                        "SEÑAL PENDIENTE BLOQUEADA:",
                        activo,
                        "zona contraria cerca sin ruptura/retest real"
                    )
                    continue

            if zona_contraria_peligrosa and "continuación sana" in razon.lower():
                if pendiente_por_ruptura and ruptura_confirmada:
                    print(
                        "SEÑAL PENDIENTE FLEXIBLE permitió continuación tras ruptura:",
                        activo
                    )
                else:
                    registrar_paridad_protocolo_live(
                        senal,
                        "BLOQUEAR",
                        "continuación sana no válida contra zona cercana",
                    )
                    print(
                        "SEÑAL PENDIENTE BLOQUEADA:",
                        activo,
                        "continuación sana no válida contra zona cercana"
                    )
                    continue

            # =========================
            # VALIDAR VELA EXACTA
            # =========================
            if senal.get("entrada_confirmada", False):
                razon_vela = "ruptura/zona ya confirmada"
            else:
                ok_vela, razon_vela = validar_vela_exacta_entrada(
                    activo,
                    direccion
                )

                if not ok_vela:
                    if pendiente_por_ruptura and ruptura_confirmada and (
                        "cerca del máximo" in razon_vela.lower()
                        or "cerca del mínimo" in razon_vela.lower()
                    ):
                        print("SEÑAL PENDIENTE ESPERA RETEST POR VELA TARDE:", activo, razon_vela)
                        restantes.append(senal)
                        continue

                    elif pullback_bajista_fuerte and "sin rechazo" in razon_vela.lower():
                        print(
                            "SEÑAL PENDIENTE FLEXIBLE permitió vela pullback bajista:",
                            activo,
                            razon_vela
                        )

                    else:
                        registrar_paridad_protocolo_live(
                            senal,
                            "BLOQUEAR",
                            razon_vela,
                        )
                        print("SEÑAL PENDIENTE BLOQUEADA:", activo, razon_vela)
                        continue

            # =========================
            # VALIDAR MICROESTRUCTURA
            # =========================
            razon_micro = "microestructura no requerida"
            if senal.get("entrada_confirmada", False):
                ok_micro, razon_micro = validar_microestructura_entrada(
                    direccion,
                    [x["open"] for x in candles],
                    [x["close"] for x in candles],
                    [x["max"] for x in candles],
                    [x["min"] for x in candles]
                )
            
                if not ok_micro:
                    registrar_paridad_protocolo_live(
                        senal,
                        "BLOQUEAR",
                        razon_micro,
                    )
                    print(
                        "SEÑAL PENDIENTE BLOQUEADA POR MICRO:",
                        activo,
                        razon_micro
                    )
                    continue
            print(
                "SEÑAL PENDIENTE CONFIRMADA:",
                activo,
                direccion,
                "|",
                razon,
                "| vela:",
                razon_vela,
                "| micro:",
                razon_micro
            )
            # ========================================================
            # C-C2C — SEGUNDA EVALUACIÓN DEL CEREBRO
            # ========================================================
            #
            # La señal ya superó las validaciones técnicas del flujo
            # de pendientes.
            #
            # Si llegó aquí porque el Cerebro exigió protocolo,
            # consultamos ahora la memoria histórica POST-PROTOCOLO.
            #
            # IMPORTANTE:
            # en esta fase todavía NO bloqueamos.
            # Solo registramos la evaluación para medirla en TRAIN.
            # ========================================================
            
            if senal.get("requiere_protocolo_cerebro", False):
                senal["protocolo_confirmado"] = True
            
                decision_post = (
                    evaluar_decision_post_protocolo(
                        senal
                    )
                )
            
                senal["decision_post_protocolo"] = (
                    decision_post.get(
                        "decision_post_protocolo",
                        "SIN_DATOS",
                    )
                )
            
                senal["autoriza_post_protocolo"] = (
                    decision_post.get(
                        "autoriza_post_protocolo",
                        True,
                    )
                )
            
                senal["probabilidad_post_protocolo"] = (
                    decision_post.get(
                        "probabilidad_post_protocolo",
                        0,
                    )
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
            
                senal["muestra_post_protocolo"] = (
                    decision_post.get(
                        "muestra_post_protocolo",
                        0,
                    )
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
                    "EVALUACION POST-PROTOCOLO:",
                    activo,
                    "| prob:",
                    senal.get(
                        "probabilidad_post_protocolo",
                        0,
                    ),
                    "| muestra:",
                    senal.get(
                        "muestra_post_protocolo",
                        0,
                    ),
                    "| confiabilidad:",
                    senal.get(
                        "confiabilidad_post_protocolo",
                        "SIN_DATOS",
                    ),
                )
            
            # Todavía no bloqueamos en C-C2.
            registrar_paridad_protocolo_live(
                senal,
                "ENTRAR",
                "flujo LIVE actual confirmó la entrada",
            )

            if abrir_operacion(senal):
                abiertas += 1
            
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
def validar_punto_entrada_en_vela(direccion, candles):
    try:
        candles = sorted(candles, key=lambda x: x["from"])

        if len(candles) < 4:
            return False, "velas insuficientes"

        actual = candles[-1]

        o = float(actual["open"])
        c = float(actual["close"])
        h = float(actual["max"])
        l = float(actual["min"])

        rango = h - l
        if rango <= 0:
            return False, "rango inválido"

        cuerpo = abs(c - o)
        fuerza = cuerpo / rango
        posicion = (c - l) / rango

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        vela_verde = c > o
        vela_roja = c < o

        if fuerza < 0.06:
            return False, "vela sin cuerpo suficiente"

        if direccion == "call":
            if posicion >= 0.90 and fuerza >= 0.62:
                return False, "CALL bloqueado: precio demasiado arriba"

            if vela_roja:
                if not (mecha_inf >= cuerpo * 1.15 and posicion >= 0.34):
                    return False, "CALL bloqueado: vela roja sin recuperación real"

            if mecha_sup >= cuerpo * 3.0 and fuerza < 0.32:
                return False, "CALL bloqueado: absorción vendedora"

            return True, "punto CALL válido"

        if direccion == "put":
            if posicion <= 0.10 and fuerza >= 0.62:
                return False, "PUT bloqueado: precio demasiado abajo"

            if vela_verde:
                if not (mecha_sup >= cuerpo * 1.15 and posicion <= 0.66):
                    return False, "PUT bloqueado: vela verde sin rechazo real"

            if mecha_inf >= cuerpo * 3.0 and fuerza < 0.32:
                return False, "PUT bloqueado: absorción compradora"

            return True, "punto PUT válido"

        return False, "dirección inválida"

    except Exception as e:
        print("Error validando punto de entrada:", e)
        return False, "error punto entrada"