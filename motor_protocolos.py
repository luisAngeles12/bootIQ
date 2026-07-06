# motor_protocolos.py
from motor_confirmacion import decidir_confirmacion
from motor_riesgo import evaluar_riesgo_protocolo

def _txt(v):
    return str(v or "").lower().strip()


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
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
    Refactor Fase 6:
    El protocolo ya no vuelve a decidir calidad general.
    Solo cancela bloqueos técnicos/críticos.
    """

    modo = _txt(senal.get("modo_entrada_setup"))
    calidad = _txt(senal.get("calidad_setup"))
    riesgo = _num(senal.get("riesgo_protocolo"), 50)
    accion_ia = _txt(senal.get("accion_confirmacion_ia"))
    fase4_decision = _txt(senal.get("fase4_decision"))

    if fase4_decision == "no_operar":
        return True, "CANCELADA_FASE4_NO_OPERAR"

    if accion_ia == "cancelar":
        if riesgo >= 85 or fase4_decision == "no_operar":
            return True, "CANCELADA_CONFIRMACION_IA"

    # Fase 6: no cancelar solo por confirmación IA.
    # Si Fase 4 permitió, el protocolo debe intentar confirmar técnicamente.
    if "no_operar" in modo or "cancelar" in modo:
        return True, "CANCELADA_SETUP_NO_OPERAR"

    if calidad in ["muy_baja", "baja"]:
        return True, "CANCELADA_CALIDAD_SETUP_BAJA"

    if riesgo >= 85:
        return True, "CANCELADA_RIESGO_PROTOCOLO_CRITICO"

    return False, ""

def _entrada_directa_permitida(senal):
    calidad = _txt(senal.get("calidad_setup"))
    modo = _txt(senal.get("modo_entrada_setup"))
    balance = _num(senal.get("balance_setup"))
    score = _num(senal.get("score_final"))
    nivel_consenso = _txt(senal.get("nivel_consenso"))
    subtipo = _txt(senal.get("subtipo_setup"))

    if "directa" not in modo:
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
    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))

    def confirmacion_fuerte(j):
        return _ruptura_micro(velas, j, direccion) and _impulso(velas[j], direccion)

    def confirmacion_media(j):
        return _ruptura_micro(velas, j, direccion) or (
            _rechazo(velas[j], direccion) and _impulso(velas[j], direccion)
        )

    if subtipo == "sweep_simple":
        for j in range(idx + 2, min(idx + 5, len(velas) - 1)):
            if confirmacion_fuerte(j):
                return j, "PROTOCOLO_SWEEP_SIMPLE_RUPTURA_IMPULSO_ESPERA_2"

        return None, "CANCELADA_SWEEP_SIMPLE"

    if subtipo == "sweep_ruptura_confirmable":
        for j in range(idx + 2, min(idx + 5, len(velas) - 1)):
            if confirmacion_fuerte(j):
                return j, "PROTOCOLO_SWEEP_RUPTURA_CONFIRMABLE_IMPULSO_ESPERA_2"

        for j in range(idx + 2, min(idx + 5, len(velas) - 1)):
            if confirmacion_media(j):
                return j, "PROTOCOLO_SWEEP_RUPTURA_CONFIRMABLE_MEDIA"

        return None, "CANCELADA_SWEEP_RUPTURA_NO_CONFIRMADA"

    if subtipo == "sweep_con_rechazo_agotamiento":
        for j in range(idx + 1, min(idx + 5, len(velas) - 1)):
            if _rechazo(velas[j], direccion) and _impulso(velas[j], direccion):
                return j, "PROTOCOLO_SWEEP_RECHAZO_AGOTAMIENTO_CONFIRMADO"

        for j in range(idx + 2, min(idx + 5, len(velas) - 1)):
            if confirmacion_fuerte(j):
                return j, "PROTOCOLO_SWEEP_AGOTAMIENTO_RUPTURA_IMPULSO"

        return None, "CANCELADA_SWEEP_AGOTAMIENTO_SIN_CONFIRMACION"

    for j in range(idx + 2, min(idx + 5, len(velas) - 1)):
        if confirmacion_fuerte(j):
            return j, "PROTOCOLO_SWEEP_RUPTURA_IMPULSO_ESPERA_2"

    for j in range(idx + 2, min(idx + 5, len(velas) - 1)):
        if confirmacion_media(j):
            return j, "PROTOCOLO_SWEEP_CONFIRMACION_MEDIA"

    return None, "CANCELADA_SWEEP_SIN_RECHAZO_VALIDO"
def _protocolo_choch(velas, idx, senal):
    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))

    # CHOCH con PA a favor: esperar mínimo 2 velas
    if subtipo == "choch_con_pa_a_favor":
        for j in range(idx + 1, min(idx + 5, len(velas) - 1)):
            if _ruptura_micro(velas, j, direccion) and _impulso(velas[j], direccion):
                return j, "PROTOCOLO_CHOCH_PA_FAVOR_RUPTURA_IMPULSO_ESPERA_2"

        for j in range(idx + 2, min(idx + 6, len(velas) - 1)):
            if _pullback_recuperado(velas, j, direccion) and _impulso(velas[j], direccion):
                return j, "PROTOCOLO_CHOCH_PA_FAVOR_PULLBACK_IMPULSO_ESPERA_2"

        return None, "CANCELADA_CHOCH_PA_FAVOR_SIN_CONFIRMACION"

    # CHOCH con tendencia débil: esperar confirmación real
    if subtipo == "choch_tendencia_debil":
        for j in range(idx + 1, min(idx + 6, len(velas) - 1)):
            if _ruptura_micro(velas, j, direccion) and _impulso(velas[j], direccion):
                return j, "PROTOCOLO_CHOCH_TENDENCIA_DEBIL_RUPTURA_IMPULSO_ESPERA_2"

        return None, "CANCELADA_CHOCH_TENDENCIA_DEBIL"

    # CHOCH genérico: no entrar en idx ni idx+1
    for j in range(idx + 2, min(idx + 5, len(velas) - 1)):
        if _ruptura_micro(velas, j, direccion) and _impulso(velas[j], direccion):
            return j, "PROTOCOLO_CHOCH_RUPTURA_IMPULSO_ESPERA_2"

    for j in range(idx + 2, min(idx + 6, len(velas) - 1)):
        if _pullback_recuperado(velas, j, direccion) and _impulso(velas[j], direccion):
            return j, "PROTOCOLO_CHOCH_PULLBACK_CON_IMPULSO_ESPERA_2"

    return None, "CANCELADA_CHOCH_SIN_RUPTURA_REAL"
def _protocolo_pullback(velas, idx, senal):
    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))
    tendencia = _txt(senal.get("tendencia") or senal.get("estado_tendencia"))
    calidad_mercado = _txt(senal.get("calidad_mercado"))
    accion_ia = _txt(senal.get("accion_confirmacion_ia"))
    nivel_ia = _txt(senal.get("nivel_confirmacion_ia"))

    if subtipo == "pullback_tendencia_agotada":
        return None, "CANCELADA_PULLBACK_TENDENCIA_AGOTADA"

    if "agotada" in tendencia:
        return None, "CANCELADA_PULLBACK_TENDENCIA_AGOTADA"

    if calidad_mercado == "sucio":
        return None, "CANCELADA_PULLBACK_MERCADO_SUCIO"

    # Si Fase 4 / confirmación IA ya viene fuerte, no exigir confirmación perfecta.
    if accion_ia == "entrar" or nivel_ia in ["premium", "alto"]:
        for j in range(idx + 1, min(idx + 5, len(velas) - 1)):
            recuperado = _pullback_recuperado(velas, j, direccion)
            rechazo = _rechazo(velas[j], direccion)
            impulso = _impulso(velas[j], direccion)

            if recuperado and (rechazo or impulso):
                return j, "PROTOCOLO_PULLBACK_IA_FUERTE_RECUPERACION"

    for j in range(idx + 1, min(idx + 6, len(velas) - 1)):
        recuperado = _pullback_recuperado(velas, j, direccion)
        rechazo = _rechazo(velas[j], direccion)
        impulso = _impulso(velas[j], direccion)

        if subtipo == "pullback_continuacion_limpia":
            if recuperado and rechazo and impulso:
                return j, "PROTOCOLO_PULLBACK_LIMPIO_RECHAZO_IMPULSO"

            if recuperado and impulso:
                return j, "PROTOCOLO_PULLBACK_LIMPIO_RECUPERACION_IMPULSO"

        if subtipo == "pullback_balance_positivo":
            if recuperado and rechazo:
                return j, "PROTOCOLO_PULLBACK_BALANCE_RECHAZO"

            if recuperado and impulso:
                return j, "PROTOCOLO_PULLBACK_BALANCE_RECUPERACION_IMPULSO"

        if subtipo in ["pullback_tendencia_insuficiente", "pullback_generico"]:
            if recuperado and rechazo and impulso:
                return j, "PROTOCOLO_PULLBACK_GENERICO_RECHAZO_IMPULSO"

            if recuperado and impulso and nivel_ia in ["premium", "alto", "medio"]:
                return j, "PROTOCOLO_PULLBACK_GENERICO_RECUPERACION_IMPULSO_IA"

        if recuperado and rechazo and impulso:
            return j, "PROTOCOLO_PULLBACK_RECHAZO_IMPULSO"

    return None, "CANCELADA_PULLBACK_SIN_CONFIRMACION_TECNICA"
def _protocolo_reaccion_zona(velas, idx, senal):
    direccion = _direccion(senal)
    subtipo = _txt(senal.get("subtipo_setup"))

    if subtipo == "zona_sin_ruptura":
        return None, "CANCELADA_ZONA_SIN_RUPTURA"

    if subtipo == "zona_rechazo_confirmado":
        for j in range(idx, min(idx + 4, len(velas) - 1)):
            if _rechazo(velas[j], direccion):
                return j, "PROTOCOLO_ZONA_RECHAZO_CONFIRMADO"

        return None, "CANCELADA_ZONA_RECHAZO_NO_VALIDADO"

    if subtipo == "zona_generica":
        for j in range(idx, min(idx + 4, len(velas) - 1)):
            if _rechazo(velas[j], direccion):
                return j, "PROTOCOLO_ZONA_GENERICA_RECHAZO"

        return None, "CANCELADA_ZONA_GENERICA_SIN_RECHAZO"

    for j in range(idx, min(idx + 4, len(velas) - 1)):
        if _rechazo(velas[j], direccion):
            return j, "PROTOCOLO_ZONA_RECHAZO"

    return None, "CANCELADA_ZONA_SIN_RECHAZO"


def _protocolo_continuacion(velas, idx, senal):
    direccion = _direccion(senal)

    if _entrada_directa_permitida(senal):
        return idx, "PROTOCOLO_CONTINUACION_DIRECTA_PREMIUM"

    for j in range(idx + 1, min(idx + 4, len(velas) - 1)):
        if _ruptura_micro(velas, j, direccion) and _impulso(velas[j], direccion):
            return j, "PROTOCOLO_CONTINUACION_RUPTURA_IMPULSO"

    return None, "CANCELADA_CONTINUACION_SIN_IMPULSO"


def _protocolo_generico(velas, idx, senal):
    direccion = _direccion(senal)

    if _entrada_directa_permitida(senal):
        return idx, "PROTOCOLO_GENERICO_DIRECTA_PREMIUM"

    for j in range(idx + 1, min(idx + 4, len(velas) - 1)):
        if _rechazo(velas[j], direccion) and _impulso(velas[j], direccion):
            return j, "PROTOCOLO_GENERICO_RECHAZO_IMPULSO"

    return None, "CANCELADA_GENERICO_SIN_CONFIRMACION"


def buscar_entrada_confirmada(velas, idx, senal):
    if idx >= len(velas) - 2:
        return None, "CANCELADA_SIN_VELAS_FUTURAS"

    diagnostico_riesgo = evaluar_riesgo_protocolo(senal)

    senal["riesgo_protocolo"] = diagnostico_riesgo.get("riesgo", 100)
    senal["nivel_riesgo_protocolo"] = diagnostico_riesgo.get("nivel", "ERROR")
    senal["razon_riesgo_protocolo"] = diagnostico_riesgo.get("razon", "")

    confirmacion_ia = decidir_confirmacion(senal)

    senal["indice_confirmacion_ia"] = confirmacion_ia.get("indice", 0)
    senal["nivel_confirmacion_ia"] = confirmacion_ia.get("nivel", "BAJO")
    senal["accion_confirmacion_ia"] = confirmacion_ia.get("accion", "CANCELAR")
    senal["razon_confirmacion_ia"] = confirmacion_ia.get("razon", "")

    cancelar, motivo = _riesgo_cancelacion(senal)
    if cancelar:
        return None, motivo

    protocolo_sugerido = _txt(senal.get("protocolo_sugerido"))

    if protocolo_sugerido == "protocolo_ruptura_resistencia":
        direccion = _direccion(senal)

        for j in range(idx + 1, min(idx + 4, len(velas) - 1)):
            if _ruptura_micro(velas, j, direccion) and _impulso(velas[j], direccion):
                return j, "PROTOCOLO_RUPTURA_RESISTENCIA_CONFIRMADA"

        return None, "CANCELADA_RUPTURA_RESISTENCIA_NO_CONFIRMADA"

    protocolo = _tipo_protocolo(senal)

    if protocolo == "SWEEP":
        return _protocolo_sweep(velas, idx, senal)

    if protocolo == "CHOCH":
        return _protocolo_choch(velas, idx, senal)

    if protocolo == "PULLBACK":
        return _protocolo_pullback(velas, idx, senal)

    if protocolo == "REACCION_ZONA":
        return _protocolo_reaccion_zona(velas, idx, senal)

    if protocolo == "CONTINUACION":
        return _protocolo_continuacion(velas, idx, senal)

    return _protocolo_generico(velas, idx, senal)