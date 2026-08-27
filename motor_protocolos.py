# motor_protocolos.py
from motor_confirmacion import decidir_confirmacion
from motor_riesgo import evaluar_riesgo_protocolo

# ============================================================
# VETO GENERAL DEL SETUP — LEGACY OPCIONAL
# ============================================================
# False:
# - motor_protocolos NO cancela automáticamente porque
#   motor_setup haya marcado riesgo_estructural_critico_setup;
# - la señal debe fallar una confirmación técnica real para
#   ser descartada;
# - el dato se conserva como diagnóstico.
#
# True:
# - restaura temporalmente el comportamiento anterior.
PROTOCOLO_VETO_SETUP_LEGACY_ACTIVO = True

def _txt(v):
    return str(v or "").lower().strip()


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
        return default

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
def _direccion(senal):
    return _txt(senal.get("direccion"))


def _info_vela(v):
    open_ = v["open"]
    close = v["close"]
    high = v["max"]
    low = v["min"]

    rango = max(high - low, 0.00000001)
    cuerpo = abs(close - open_)
    mecha_sup = high - max(open_, close)
    mecha_inf = min(open_, close) - low

    return {
        "alcista": close > open_,
        "bajista": close < open_,
        "fuerza": cuerpo / rango,
        "cuerpo": cuerpo,
        "rango": rango,
        "mecha_sup": mecha_sup,
        "mecha_inf": mecha_inf,
        "rechazo_alcista": mecha_inf >= cuerpo * 1.3 and close > open_,
        "rechazo_bajista": mecha_sup >= cuerpo * 1.3 and close < open_,
        "impulso_alcista": close > open_ and cuerpo / rango >= 0.58,
        "impulso_bajista": close < open_ and cuerpo / rango >= 0.58,
    }


def _rechazo(v, direccion):
    info = _info_vela(v)

    if direccion == "call":
        return info["rechazo_alcista"]

    if direccion == "put":
        return info["rechazo_bajista"]

    return False


def _impulso(v, direccion):
    info = _info_vela(v)

    if direccion == "call":
        return info["impulso_alcista"]

    if direccion == "put":
        return info["impulso_bajista"]

    return False


def _ruptura_micro(velas, idx, direccion):
    if idx < 2:
        return False

    anteriores = velas[idx - 2:idx]
    max_prev = max(v["max"] for v in anteriores)
    min_prev = min(v["min"] for v in anteriores)
    vela = velas[idx]

    if direccion == "call":
        return vela["close"] > max_prev

    if direccion == "put":
        return vela["close"] < min_prev

    return False


def _pullback_recuperado(velas, idx, direccion):
    if idx < 3:
        return False

    vela = velas[idx]
    previa = velas[idx - 1]

    if direccion == "call":
        retroceso = vela["min"] <= previa["close"]
        recuperacion = vela["close"] > vela["open"]
        return retroceso and recuperacion

    if direccion == "put":
        retroceso = vela["max"] >= previa["close"]
        recuperacion = vela["close"] < vela["open"]
        return retroceso and recuperacion

    return False



def _ventana_sweep(senal, idx, velas):
    """
    Compatibilidad SWEEP.

    La autoridad temporal única pertenece a
    _ventana_confirmacion().
    """
    return _ventana_confirmacion(
        senal,
        idx,
        velas,
    )


def _ventana_confirmacion(senal, idx, velas):
    """
    Define la ventana máxima permitida para protocolos que deben
    respetar ESPERAR_2 / ESPERAR_3 de motor_confirmacion.

    ESPERAR_2: permite entrada en +1 o +2.
    ESPERAR_3: permite entrada en +1, +2 o +3.

    La última vela disponible nunca se usa como entrada porque el
    backtest necesita una vela posterior para calcular el resultado.
    """
    accion = _txt(senal.get("accion_confirmacion_ia"))
    ultimo_idx_entrada = len(velas) - 2

    if accion == "esperar_3":
        inicio = idx + 1
        objetivo = idx + 3
    elif accion == "esperar_2":
        inicio = idx + 1
        objetivo = idx + 2
    else:
        inicio = idx + 1
        objetivo = idx + 2

    inicio = min(inicio, ultimo_idx_entrada)
    objetivo = min(objetivo, ultimo_idx_entrada)
    fin = min(objetivo + 1, ultimo_idx_entrada + 1)

    if fin <= inicio:
        fin = min(inicio + 1, ultimo_idx_entrada + 1)

    return inicio, objetivo, fin


def _tipo_protocolo(senal):
    texto = " ".join([
        _txt(senal.get("subtipo_setup")),
        _txt(senal.get("tipo_setup")),
        _txt(senal.get("patron")),
        _txt(senal.get("base_estrategia")),
        _txt(senal.get("accion_precio")),
        _txt(senal.get("pa_tipo")),
        _txt(senal.get("razon")),
        _txt(senal.get("razones_setup")),
    ])

    if "sweep" in texto or "liquidity" in texto or "liquidez" in texto:
        return "SWEEP"

    if "choch" in texto or "cambio_estructura" in texto:
        return "CHOCH"

    if "pullback" in texto or "retroceso" in texto or "ema" in texto:
        return "PULLBACK"

    if "soporte" in texto or "resistencia" in texto or "zona" in texto:
        return "REACCION_ZONA"

    if "continuacion" in texto or "continuación" in texto:
        return "CONTINUACION"

    return "GENERICO"


def _riesgo_cancelacion(senal):
    """
    El protocolo no decide la calidad general de la operación.

    Solo cancela por:
    - bloqueo duro del cerebro;
    - calidad extremadamente baja;
    - riesgo de protocolo crítico.

    El veto general por riesgo estructural crítico del setup queda
    disponible solo en modo legacy mediante
    PROTOCOLO_VETO_SETUP_LEGACY_ACTIVO.
    """

    # Campo legacy: respaldo temporal.
    modo = _txt(senal.get("modo_entrada_setup"))

    # Evidencia neutral nueva del setup.
    riesgo_critico_setup = _bool(
        senal.get("riesgo_estructural_critico_setup"),
        default=("no_operar" in modo or "cancelar" in modo)
    )

    calidad = _txt(senal.get("calidad_setup"))
    riesgo = _num(senal.get("riesgo_protocolo"), 50)
    accion_ia = _txt(senal.get("accion_confirmacion_ia"))
    fase4_decision = _txt(senal.get("fase4_decision"))

    confianza_cerebro = _num(
        senal.get("cerebro_unico_confianza"),
        0
    )
    riesgo_cerebro = _txt(
        senal.get("cerebro_unico_riesgo")
    )

    bloqueo_duro_cerebro = (
        fase4_decision == "no_operar"
        and riesgo_cerebro == "extremo"
        and confianza_cerebro < 38
    )

    if bloqueo_duro_cerebro:
        return True, "CANCELADA_FASE4_NO_OPERAR"

    if accion_ia == "cancelar":
        if riesgo >= 90 and bloqueo_duro_cerebro:
            return True, "CANCELADA_CONFIRMACION_IA"

    # Ya no se interpreta NO_OPERAR directamente.
    # Se utiliza la evidencia neutral generada por motor_setup.
    if (
        PROTOCOLO_VETO_SETUP_LEGACY_ACTIVO
        and riesgo_critico_setup
    ):
        return True, "CANCELADA_SETUP_NO_OPERAR"

    if calidad in ["muy_baja", "baja"]:
        return True, "CANCELADA_CALIDAD_SETUP_BAJA"

    if riesgo >= 85:
        return True, "CANCELADA_RIESGO_PROTOCOLO_CRITICO"

    # Riesgo crítico del setup queda disponible como diagnóstico,
    # pero no veta automáticamente cuando el modo legacy está apagado.
    if (
        riesgo_critico_setup
        and not PROTOCOLO_VETO_SETUP_LEGACY_ACTIVO
    ):
        senal["veto_setup_legacy_omitido"] = True

    return False, ""
def _entrada_directa_permitida(senal):
    calidad = _txt(senal.get("calidad_setup"))

    # Campo legacy: respaldo temporal.
    modo = _txt(senal.get("modo_entrada_setup"))

    # Evidencias neutrales nuevas.
    requiere_ruptura = _bool(
        senal.get("requiere_ruptura_setup"),
        default=("esperar_ruptura" in modo)
    )

    requiere_confirmacion = _bool(
        senal.get("requiere_confirmacion_setup"),
        default=("esperar_confirmacion" in modo)
    )

    riesgo_critico = _bool(
        senal.get("riesgo_estructural_critico_setup"),
        default=("no_operar" in modo or "cancelar" in modo)
    )

    balance = _num(senal.get("balance_setup"))
    score = _num(senal.get("score_final"))
    nivel_consenso = _txt(senal.get("nivel_consenso"))
    subtipo = _txt(senal.get("subtipo_setup"))

    # Una entrada no puede ser directa si el setup exige
    # ruptura, confirmación o presenta riesgo crítico.
    if riesgo_critico:
        return False

    if requiere_ruptura:
        return False

    if requiere_confirmacion:
        return False

    # Compatibilidad temporal:
    # una señal antigua sin campos neutrales solo será directa
    # cuando el modo legacy también lo indique.
    tiene_campos_neutrales = (
        senal.get("requiere_ruptura_setup") is not None
        or senal.get("requiere_confirmacion_setup") is not None
        or senal.get("riesgo_estructural_critico_setup") is not None
    )

    if not tiene_campos_neutrales and "directa" not in modo:
        return False

    if subtipo in [
        "pullback_generico",
        "pullback_tendencia_insuficiente",
        "sweep_simple",
        "zona_sin_ruptura",
    ]:
        return False

    if calidad == "premium" and balance >= 1:
        return True

    if calidad in ["premium", "alta"] and score >= 180:
        return True

    if nivel_consenso == "premium" and balance >= 0:
        return True

    return False
def _protocolo_sweep(velas, idx, senal):
    """
    Protocolo SWEEP con timing coordinado con motor_confirmacion.

    Regla:
    - la recomendación ESPERAR_2 / ESPERAR_3 define la ventana;
    - una confirmación fuerte puede entrar antes del objetivo;
    - no se persiguen confirmaciones tardías fuera de la ventana;
    - la confirmación media solo se acepta en el objetivo o antes.
    """

    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))

    inicio, objetivo, fin = _ventana_sweep(
        senal,
        idx,
        velas,
    )

    def confirmacion_fuerte(j):
        return (
            _ruptura_micro(velas, j, direccion)
            and _impulso(velas[j], direccion)
        )

    def confirmacion_media(j):
        return (
            _ruptura_micro(velas, j, direccion)
            or (
                _rechazo(velas[j], direccion)
                and _impulso(velas[j], direccion)
            )
        )

    if subtipo == "sweep_simple":
        for j in range(inicio, fin):
            if confirmacion_fuerte(j):
                return (
                    j,
                    "PROTOCOLO_SWEEP_SIMPLE_"
                    "RUPTURA_IMPULSO_TIMING_IA",
                )

        return None, "CANCELADA_SWEEP_SIMPLE"

    if subtipo == "sweep_ruptura_confirmable":
        for j in range(inicio, fin):
            if confirmacion_fuerte(j):
                return (
                    j,
                    "PROTOCOLO_SWEEP_RUPTURA_CONFIRMABLE_"
                    "IMPULSO_TIMING_IA",
                )

        fin_media = min(objetivo + 1, fin)

        for j in range(inicio, fin_media):
            if confirmacion_media(j):
                return (
                    j,
                    "PROTOCOLO_SWEEP_RUPTURA_CONFIRMABLE_"
                    "MEDIA_TIMING_IA",
                )

        return None, "CANCELADA_SWEEP_RUPTURA_NO_CONFIRMADA"

    if subtipo == "sweep_con_rechazo_agotamiento":
        for j in range(inicio, fin):
            if (
                _rechazo(velas[j], direccion)
                and _impulso(velas[j], direccion)
            ):
                return (
                    j,
                    "PROTOCOLO_SWEEP_RECHAZO_AGOTAMIENTO_"
                    "CONFIRMADO_TIMING_IA",
                )

        for j in range(inicio, fin):
            if confirmacion_fuerte(j):
                return (
                    j,
                    "PROTOCOLO_SWEEP_AGOTAMIENTO_"
                    "RUPTURA_IMPULSO_TIMING_IA",
                )

        return None, "CANCELADA_SWEEP_AGOTAMIENTO_SIN_CONFIRMACION"

    for j in range(inicio, fin):
        if confirmacion_fuerte(j):
            return (
                j,
                "PROTOCOLO_SWEEP_RUPTURA_IMPULSO_TIMING_IA",
            )

    fin_media = min(objetivo + 1, fin)

    for j in range(inicio, fin_media):
        if confirmacion_media(j):
            return (
                j,
                "PROTOCOLO_SWEEP_CONFIRMACION_MEDIA_TIMING_IA",
            )

    return None, "CANCELADA_SWEEP_SIN_RECHAZO_VALIDO"


def _protocolo_choch(velas, idx, senal):
    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))

    inicio, _, fin = _ventana_confirmacion(
        senal,
        idx,
        velas,
    )

    # CHOCH con PA a favor puede confirmar desde la primera
    # vela posterior, pero nunca fuera de la ventana IA.
    if subtipo == "choch_con_pa_a_favor":
        for j in range(inicio, fin):
            if (
                _ruptura_micro(velas, j, direccion)
                and _impulso(velas[j], direccion)
            ):
                return (
                    j,
                    "PROTOCOLO_CHOCH_PA_FAVOR_RUPTURA_IMPULSO_ESPERA_2",
                )

        return None, "CANCELADA_CHOCH_PA_FAVOR_SIN_CONFIRMACION"

    # Conserva la condición técnica propia del subtipo,
    # pero elimina su ventana temporal independiente.
    if subtipo == "choch_tendencia_debil":
        for j in range(inicio, fin):
            if (
                _ruptura_micro(velas, j, direccion)
                and _impulso(velas[j], direccion)
            ):
                return (
                    j,
                    "PROTOCOLO_CHOCH_TENDENCIA_DEBIL_"
                    "RUPTURA_IMPULSO_ESPERA_2",
                )

        return None, "CANCELADA_CHOCH_TENDENCIA_DEBIL"

    # El CHOCH genérico históricamente exigía al menos +2.
    # Conservamos ese requisito técnico, pero respetando
    # el máximo autorizado por motor_confirmacion.
    inicio_choch = max(
        inicio,
        idx + 2,
    )

    for j in range(inicio_choch, fin):
        if (
            _ruptura_micro(velas, j, direccion)
            and _impulso(velas[j], direccion)
        ):
            return (
                j,
                "PROTOCOLO_CHOCH_RUPTURA_IMPULSO_ESPERA_2",
            )

    for j in range(inicio_choch, fin):
        if (
            _pullback_recuperado(velas, j, direccion)
            and _impulso(velas[j], direccion)
        ):
            return (
                j,
                "PROTOCOLO_CHOCH_PULLBACK_CON_IMPULSO_ESPERA_2",
            )

    return None, "CANCELADA_CHOCH_SIN_RUPTURA_REAL"
def _protocolo_pullback(velas, idx, senal):
    """
    Protocolo específico para pullbacks.

    Prioridad:
    1. Confirmación técnica estricta.
    2. Confirmación técnica moderada, únicamente cuando el Cerebro,
       la IA, el riesgo y el consenso están alineados.

    No decide la calidad general de la señal.
    Solo confirma el momento de entrada.
    """

    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))

    tendencia = _txt(
        senal.get("tendencia")
        or senal.get("estado_tendencia")
    )

    calidad_mercado = _txt(
        senal.get("calidad_mercado")
    )

    nivel_ia = _txt(
        senal.get("nivel_confirmacion_ia")
    )

    confianza_cerebro = _num(
        senal.get("cerebro_unico_confianza"),
        0,
    )

    riesgo_cerebro = _txt(
        senal.get("cerebro_unico_riesgo")
    )

    nivel_consenso = _txt(
        senal.get("nivel_consenso")
    )

    calidad_setup = _txt(
        senal.get("calidad_setup")
    )

    balance_setup = _num(
        senal.get("balance_setup"),
        0,
    )

    # ========================================================
    # CANCELACIONES ESTRUCTURALES
    # ========================================================

    if subtipo == "pullback_tendencia_agotada":
        return None, "CANCELADA_PULLBACK_TENDENCIA_AGOTADA"

    if "agotada" in tendencia:
        return None, "CANCELADA_PULLBACK_TENDENCIA_AGOTADA"

    if calidad_mercado == "sucio":
        return None, "CANCELADA_PULLBACK_MERCADO_SUCIO"

   # ========================================================
   # VENTANA DE CONFIRMACIÓN
   # ========================================================
   # La autoridad temporal pertenece a motor_confirmacion.
    inicio, _, final = _ventana_confirmacion(
       senal,
       idx,
       velas,
    )
   
    # ========================================================
    # NIVEL 1: CONFIRMACIÓN ESTRICTA
    # ========================================================

    for j in range(inicio, final):
        recuperado = _pullback_recuperado(
            velas,
            j,
            direccion,
        )

        rechazo = _rechazo(
            velas[j],
            direccion,
        )

        impulso = _impulso(
            velas[j],
            direccion,
        )

        if subtipo == "pullback_continuacion_limpia":
            if recuperado and rechazo and impulso:
                return (
                    j,
                    "PROTOCOLO_PULLBACK_LIMPIO_"
                    "RECHAZO_IMPULSO",
                )

            if recuperado and impulso:
                return (
                    j,
                    "PROTOCOLO_PULLBACK_LIMPIO_"
                    "RECUPERACION_IMPULSO",
                )

        elif subtipo == "pullback_balance_positivo":
            if recuperado and rechazo:
                return (
                    j,
                    "PROTOCOLO_PULLBACK_BALANCE_RECHAZO",
                )

            if recuperado and impulso:
                return (
                    j,
                    "PROTOCOLO_PULLBACK_BALANCE_"
                    "RECUPERACION_IMPULSO",
                )

        elif subtipo in [
            "pullback_tendencia_insuficiente",
            "pullback_generico",
        ]:
            if recuperado and rechazo and impulso:
                return (
                    j,
                    "PROTOCOLO_PULLBACK_GENERICO_"
                    "RECHAZO_IMPULSO",
                )

            if (
                recuperado
                and impulso
                and nivel_ia in ["premium", "alto", "medio"]
            ):
                return (
                    j,
                    "PROTOCOLO_PULLBACK_GENERICO_"
                    "RECUPERACION_IMPULSO_IA",
                )

        elif recuperado and rechazo and impulso:
            return (
                j,
                "PROTOCOLO_PULLBACK_RECHAZO_IMPULSO",
            )

    return (
        None,
        "CANCELADA_PULLBACK_SIN_CONFIRMACION_TECNICA",
    )
def _protocolo_reaccion_zona(velas, idx, senal):
    """
    Confirma una reacción de zona.

    Todos los subtipos respetan la misma ventana temporal
    definida por motor_confirmacion.
    """
    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))

    if direccion not in ["call", "put"]:
        return None, "CANCELADA_ZONA_DIRECCION_INVALIDA"

    if subtipo == "zona_sin_ruptura":
        return None, "CANCELADA_ZONA_SIN_RUPTURA"

    inicio, _, fin = _ventana_confirmacion(
        senal,
        idx,
        velas,
    )

    if subtipo == "zona_rechazo_confirmado":
        for j in range(inicio, fin):
            if _impulso(velas[j], direccion):
                return (
                    j,
                    "PROTOCOLO_ZONA_RECHAZO_CONFIRMADO_"
                    "IMPULSO_TIMING_IA",
                )

        return (
            None,
            "CANCELADA_ZONA_RECHAZO_CONFIRMADO_"
            "SIN_CONTINUIDAD",
        )

    if subtipo == "zona_generica":
        for j in range(inicio, fin):
            if _rechazo(velas[j], direccion):
                return (
                    j,
                    "PROTOCOLO_ZONA_GENERICA_RECHAZO",
                )

        return (
            None,
            "CANCELADA_ZONA_GENERICA_SIN_RECHAZO",
        )

    for j in range(inicio, fin):
        if _rechazo(velas[j], direccion):
            return j, "PROTOCOLO_ZONA_RECHAZO"

    return None, "CANCELADA_ZONA_SIN_RECHAZO"
def _protocolo_ruptura_resistencia(velas, idx, senal):
    """
    Confirma una ruptura real respetando el timing recomendado por
    motor_confirmacion.

    ESPERAR_2: solo se aceptan entradas hasta vela +2.
    ESPERAR_3: solo se aceptan entradas hasta vela +3.
    """
    direccion = _direccion(senal)

    if direccion not in ["call", "put"]:
        return None, "CANCELADA_RUPTURA_DIRECCION_INVALIDA"

    inicio, objetivo, fin = _ventana_confirmacion(
        senal,
        idx,
        velas,
    )

    # Nivel 1: ruptura acompañada de impulso.
    for j in range(inicio, fin):
        if (
            _ruptura_micro(velas, j, direccion)
            and _impulso(velas[j], direccion)
        ):
            return (
                j,
                "PROTOCOLO_RUPTURA_RESISTENCIA_CONFIRMADA_IMPULSO",
            )

    # Nivel 2: ruptura seguida de conservación del nivel, siempre
    # dentro de la ventana temporal permitida.
    for j in range(inicio, fin):
        if not _ruptura_micro(velas, j, direccion):
            continue

        idx_confirmacion = j + 1

        if idx_confirmacion > objetivo:
            continue

        if idx_confirmacion >= len(velas) - 1:
            continue

        vela_ruptura = velas[j]
        vela_confirmacion = velas[idx_confirmacion]

        if direccion == "call":
            conserva_nivel = (
                vela_confirmacion["close"]
                >= vela_ruptura["close"]
            )
            confirma_direccion = (
                vela_confirmacion["close"]
                > vela_confirmacion["open"]
            )
        else:
            conserva_nivel = (
                vela_confirmacion["close"]
                <= vela_ruptura["close"]
            )
            confirma_direccion = (
                vela_confirmacion["close"]
                < vela_confirmacion["open"]
            )

        if conserva_nivel and confirma_direccion:
            return (
                idx_confirmacion,
                "PROTOCOLO_RUPTURA_RESISTENCIA_CONFIRMADA_CONTINUIDAD",
            )

    return (
        None,
        "CANCELADA_RUPTURA_RESISTENCIA_NO_CONFIRMADA",
    )

def _protocolo_continuacion(velas, idx, senal):
    direccion = _direccion(senal)

    if _entrada_directa_permitida(senal):
        return idx, "PROTOCOLO_CONTINUACION_DIRECTA_PREMIUM"

    inicio, _, fin = _ventana_confirmacion(
        senal,
        idx,
        velas,
    )

    for j in range(inicio, fin):
        if (
            _ruptura_micro(velas, j, direccion)
            and _impulso(velas[j], direccion)
        ):
            return (
                j,
                "PROTOCOLO_CONTINUACION_RUPTURA_IMPULSO",
            )

    return None, "CANCELADA_CONTINUACION_SIN_IMPULSO"

def _protocolo_generico(velas, idx, senal):
    direccion = _direccion(senal)

    if _entrada_directa_permitida(senal):
        return idx, "PROTOCOLO_GENERICO_DIRECTA_PREMIUM"

    inicio, _, fin = _ventana_confirmacion(
        senal,
        idx,
        velas,
    )

    for j in range(inicio, fin):
        if (
            _rechazo(velas[j], direccion)
            and _impulso(velas[j], direccion)
        ):
            return (
                j,
                "PROTOCOLO_GENERICO_RECHAZO_IMPULSO",
            )

    return None, "CANCELADA_GENERICO_SIN_CONFIRMACION"
def _registrar_auditoria_protocolo(
    senal,
    idx_senal,
    idx_entrada,
    motivo,
    protocolo,
):
    """
    Registra cómo motor_protocolos llegó a su resultado.

    No modifica ninguna decisión.
    Solo añade diagnóstico para backtest.
    """

    if idx_entrada is None:
        espera = None
        operada = False
    else:
        espera = idx_entrada - idx_senal
        operada = True

    senal["auditoria_protocolo_tipo"] = protocolo

    senal["auditoria_protocolo_subtipo"] = _txt(
        senal.get("subtipo_setup")
    )

    senal["auditoria_protocolo_familia"] = _txt(
        senal.get("familia_setup")
    )

    senal["auditoria_protocolo_operada"] = operada

    senal["auditoria_protocolo_idx_senal"] = idx_senal

    senal["auditoria_protocolo_idx_entrada"] = (
        idx_entrada
        if idx_entrada is not None
        else -1
    )

    senal["auditoria_protocolo_espera_velas"] = (
        espera
        if espera is not None
        else -1
    )

    senal["auditoria_protocolo_motivo"] = motivo

    senal["auditoria_protocolo_riesgo"] = senal.get(
        "riesgo_protocolo",
        0,
    )

    senal["auditoria_protocolo_nivel_riesgo"] = senal.get(
        "nivel_riesgo_protocolo",
        "",
    )

    senal["auditoria_protocolo_indice_confirmacion"] = senal.get(
        "indice_confirmacion_ia",
        0,
    )

    senal["auditoria_protocolo_nivel_confirmacion"] = senal.get(
        "nivel_confirmacion_ia",
        "",
    )

    senal["auditoria_protocolo_accion_confirmacion"] = senal.get(
        "accion_confirmacion_ia",
        "",
    )

    senal["auditoria_protocolo_tipo_mercado"] = senal.get(
        "tipo_mercado",
        "",
    )

    senal["auditoria_protocolo_tendencia"] = senal.get(
        "estado_tendencia",
        "",
    )

    senal["auditoria_protocolo_pa_tipo"] = senal.get(
        "pa_tipo",
        "",
    )

    senal["auditoria_protocolo_probabilidad"] = senal.get(
        "probabilidad_estimada",
        0,
    )

    return idx_entrada, motivo
def _max_espera_protocolo_live(senal):
    """
    Máximo de velas reales permitido en LIVE.

    La autoridad temporal es la misma que usa
    motor_confirmacion / _ventana_confirmacion.

    ESPERAR_2 -> máximo +2
    ESPERAR_3 -> máximo +3
    """

    accion = _txt(
        senal.get("accion_confirmacion_ia")
    )

    if accion == "esperar_3":
        return 3

    return 2
def evaluar_protocolo_live_sombra(
    velas,
    senal,
    candle_time,
):
    """
    Evalúa en SOMBRA qué habría hecho motor_protocolos.py
    usando únicamente las velas disponibles hasta ahora.

    NO abre operaciones.
    NO cambia la decisión del Cerebro.
    NO modifica los protocolos existentes.

    Reutiliza buscar_entrada_confirmada(), la misma autoridad
    utilizada por el backtest.

    Retorna:
        CONFIRMADA
        ESPERAR
        CONFIRMACION_PASADA
        SENAL_NO_ENCONTRADA
        SIN_DATOS
    """

    if not isinstance(senal, dict):
        return {
            "estado": "SIN_DATOS",
            "idx_entrada": None,
            "motivo": "senal_invalida",
            "espera_velas": -1,
        }

    if not isinstance(velas, list) or len(velas) < 4:
        return {
            "estado": "SIN_DATOS",
            "idx_entrada": None,
            "motivo": "velas_insuficientes",
            "espera_velas": -1,
        }

    try:
        candle_time = int(candle_time)
    except (TypeError, ValueError):
        return {
            "estado": "SIN_DATOS",
            "idx_entrada": None,
            "motivo": "candle_time_invalido",
            "espera_velas": -1,
        }

    if candle_time <= 0:
        return {
            "estado": "SIN_DATOS",
            "idx_entrada": None,
            "motivo": "candle_time_invalido",
            "espera_velas": -1,
        }

    velas_ordenadas = sorted(
        velas,
        key=lambda v: v["from"],
    )

    vela_detectada = senal.get(
        "vela_detectada"
    )

    if vela_detectada is None:
        return {
            "estado": "SIN_DATOS",
            "idx_entrada": None,
            "motivo": "senal_sin_vela_detectada",
            "espera_velas": -1,
        }

    try:
        vela_detectada = int(
            vela_detectada
        )
    except (TypeError, ValueError):
        return {
            "estado": "SIN_DATOS",
            "idx_entrada": None,
            "motivo": "vela_detectada_invalida",
            "espera_velas": -1,
        }

    # ========================================================
    # LOCALIZAR LA VELA DONDE NACIÓ LA SEÑAL
    # ========================================================

    idx_senal = None

    for i, vela in enumerate(
        velas_ordenadas
    ):
        try:
            bucket = int(
                float(vela["from"])
                // candle_time
            )
        except Exception:
            continue

        if bucket == vela_detectada:
            idx_senal = i
            break

    if idx_senal is None:
        return {
            "estado": "SENAL_NO_ENCONTRADA",
            "idx_entrada": None,
            "motivo": (
                "la ventana de velas LIVE no contiene "
                "la vela donde nació la señal"
            ),
            "espera_velas": -1,
        }

    ultimo_idx_real = (
        len(velas_ordenadas) - 1
    )

    # ========================================================
    # VELAS CENTINELA LIVE
    # ========================================================
    #
    # buscar_entrada_confirmada() fue diseñado para backtest
    # y necesita margen de velas posteriores para evaluar
    # correctamente la señal.
    #
    # En LIVE esas velas futuras todavía no existen.
    #
    # Añadimos DOS velas neutrales:
    # - permiten evaluar la última vela REAL disponible;
    # - evitan CANCELADA_SIN_VELAS_FUTURAS artificial;
    # - no pueden confirmar una entrada por sí mismas;
    # - no introducen información futura real.
    # ========================================================

    ultima = velas_ordenadas[-1]

    close_ultima = float(
        ultima["close"]
    )

    centinela_1 = {
        "from": (
            float(ultima["from"])
            + candle_time
        ),
        "open": close_ultima,
        "close": close_ultima,
        "max": close_ultima,
        "min": close_ultima,
    }

    centinela_2 = {
        "from": (
            float(ultima["from"])
            + (candle_time * 2)
        ),
        "open": close_ultima,
        "close": close_ultima,
        "max": close_ultima,
        "min": close_ultima,
    }

    velas_motor = (
        list(velas_ordenadas)
        + [
            centinela_1,
            centinela_2,
        ]
    )

    # Copia porque motor_protocolos añade campos
    # de auditoría a la señal.
    senal_motor = dict(senal)

    idx_entrada, motivo = (
        buscar_entrada_confirmada(
            velas_motor,
            idx_senal,
            senal_motor,
        )
    )

    # ========================================================
    # NO ENCONTRÓ CONFIRMACIÓN TODAVÍA
    # ========================================================

    if idx_entrada is None:
        espera_actual = (
            ultimo_idx_real
            - idx_senal
        )

        max_espera = (
            _max_espera_protocolo_live(
                senal_motor
            )
        )

        # La ventana técnica del protocolo ya terminó
        # y nunca apareció una confirmación válida.
        if espera_actual >= max_espera:
            return {
                "estado": "CANCELADA",
                "idx_entrada": None,
                "motivo": motivo,
                "espera_velas": espera_actual,
                "max_espera_velas": max_espera,
                "protocolo": senal_motor.get(
                    "auditoria_protocolo_tipo",
                    "",
                ),
            }

        # Todavía quedan velas dentro de la ventana
        # donde el mismo protocolo podría confirmar.
        return {
            "estado": "ESPERAR",
            "idx_entrada": None,
            "motivo": motivo,
            "espera_velas": espera_actual,
            "max_espera_velas": max_espera,
            "protocolo": senal_motor.get(
                "auditoria_protocolo_tipo",
                "",
            ),
        }
    espera = (
        idx_entrada
        - idx_senal
    )

    # ========================================================
    # CONFIRMACIÓN EN LA VELA ACTUAL
    # ========================================================

    if idx_entrada == ultimo_idx_real:
        return {
            "estado": "CONFIRMADA",
            "idx_entrada": idx_entrada,
            "motivo": motivo,
            "espera_velas": espera,
            "protocolo": senal_motor.get(
                "auditoria_protocolo_tipo",
                "",
            ),
        }

    # ========================================================
    # LA CONFIRMACIÓN OCURRIÓ ANTES
    # ========================================================
    #
    # Muy importante:
    # LIVE NO debe entrar tarde simplemente porque al volver
    # a mirar el histórico descubre una confirmación vieja.
    # ========================================================

    if idx_entrada < ultimo_idx_real:
        return {
            "estado": "CONFIRMACION_PASADA",
            "idx_entrada": idx_entrada,
            "motivo": motivo,
            "espera_velas": espera,
            "protocolo": senal_motor.get(
                "auditoria_protocolo_tipo",
                "",
            ),
        }

    return {
        "estado": "ESPERAR",
        "idx_entrada": None,
        "motivo": motivo,
        "espera_velas": (
            ultimo_idx_real
            - idx_senal
        ),
        "protocolo": senal_motor.get(
            "auditoria_protocolo_tipo",
            "",
        ),
    }
def buscar_entrada_confirmada(velas, idx, senal):
    """
    Orquestador de protocolos.

    FASE C4:
    - mantiene los vetos generales para todos los protocolos;
    - PROTOCOLO_RUPTURA_RESISTENCIA no es cancelado por
      el veto previo de setup/riesgo;
    - riesgo y confirmación siguen calculándose y registrándose;
    - la entrada solo ocurre si el protocolo técnico confirma
      una ruptura real.
    """

    if idx >= len(velas) - 2:
        return _registrar_auditoria_protocolo(
            senal,
            idx,
            None,
            "CANCELADA_SIN_VELAS_FUTURAS",
            "SIN_PROTOCOLO",
        )

    # ========================================================
    # DIAGNÓSTICOS AUXILIARES
    # ========================================================

    diagnostico_riesgo = evaluar_riesgo_protocolo(
        senal
    )

    senal["riesgo_protocolo"] = diagnostico_riesgo.get(
        "riesgo",
        100,
    )

    senal["nivel_riesgo_protocolo"] = diagnostico_riesgo.get(
        "nivel",
        "ERROR",
    )

    senal["razon_riesgo_protocolo"] = diagnostico_riesgo.get(
        "razon",
        "",
    )

    confirmacion_ia = decidir_confirmacion(
        senal
    )

    senal["indice_confirmacion_ia"] = confirmacion_ia.get(
        "indice",
        0,
    )

    senal["nivel_confirmacion_ia"] = confirmacion_ia.get(
        "nivel",
        "BAJO",
    )

    senal["accion_confirmacion_ia"] = confirmacion_ia.get(
        "accion",
        "CANCELAR",
    )

    senal["razon_confirmacion_ia"] = confirmacion_ia.get(
        "razon",
        "",
    )

    # ========================================================
    # PROTOCOLO SUGERIDO
    # ========================================================

    protocolo_sugerido = _txt(
        senal.get("protocolo_sugerido")
    )

    # ========================================================
    # C4 — RUPTURA RESISTENCIA
    # ========================================================
    #
    # C3 mostró que este protocolo sí conserva ventaja
    # cuando las señales vetadas llegan a su confirmación
    # técnica:
    #
    # TRAIN      ~59.65%
    # VALIDACION ~60.71%
    #
    # Por eso setup/riesgo permanecen como evidencia,
    # pero no bloquean antes de comprobar la ruptura real.
    # ========================================================

    if (
        protocolo_sugerido
        == "protocolo_ruptura_resistencia"
    ):
        senal["c4_bypass_veto_ruptura_resistencia"] = True

        idx_entrada, motivo = (
            _protocolo_ruptura_resistencia(
                velas,
                idx,
                senal,
            )
        )

        return _registrar_auditoria_protocolo(
            senal,
            idx,
            idx_entrada,
            motivo,
            "RUPTURA_RESISTENCIA",
        )

    # ========================================================
    # CANCELACIONES PREVIAS
    # ========================================================
    #
    # Todos los demás protocolos conservan exactamente
    # el comportamiento anterior.
    # ========================================================

    cancelar, motivo = _riesgo_cancelacion(
        senal
    )

    if cancelar:
        return _registrar_auditoria_protocolo(
            senal,
            idx,
            None,
            motivo,
            "VETO_PREVIO",
        )

    # ========================================================
    # PROTOCOLOS RESTANTES
    # ========================================================

    protocolo = _tipo_protocolo(
        senal
    )

    if protocolo == "SWEEP":
        idx_entrada, motivo = _protocolo_sweep(
            velas,
            idx,
            senal,
        )

    elif protocolo == "CHOCH":
        idx_entrada, motivo = _protocolo_choch(
            velas,
            idx,
            senal,
        )

    elif protocolo == "PULLBACK":
        idx_entrada, motivo = _protocolo_pullback(
            velas,
            idx,
            senal,
        )

    elif protocolo == "REACCION_ZONA":
        idx_entrada, motivo = (
            _protocolo_reaccion_zona(
                velas,
                idx,
                senal,
            )
        )

    elif protocolo == "CONTINUACION":
        idx_entrada, motivo = (
            _protocolo_continuacion(
                velas,
                idx,
                senal,
            )
        )

    else:
        idx_entrada, motivo = _protocolo_generico(
            velas,
            idx,
            senal,
        )

    return _registrar_auditoria_protocolo(
        senal,
        idx,
        idx_entrada,
        motivo,
        protocolo,
    )