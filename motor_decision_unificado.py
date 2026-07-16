# motor_decision_unificado.py
"""
LEGACY BOOTIQ V1/V2.

Este módulo ya no participa en la decisión de producción
ni en el backtest oficial.

Cerebro activo:
    decision_bootiq.py
        -> motor_decision.evaluar_decision_cerebro_unico()

No volver a importar este módulo en:
    bot.py
    estrategia.py
    entrada.py
    operaciones.py
    backtest_bot_real.py
"""

def _num(v, default=0):
    try:
        return float(v if v is not None else default)
    except Exception:
        return default


def _txt(v):
    return str(v or "").upper().strip()


def _agregar(score, valor, razones, motivo):
    score += valor
    signo = "+" if valor >= 0 else ""
    razones.append(f"{signo}{valor}: {motivo}")
    return score


def _clasificar(score, bloqueos):
    score = max(0, min(100, round(score, 2)))

    if bloqueos and score < 65:
        accion = "NO_OPERAR"
    elif score >= 68:
        accion = "OPERAR"
    elif score >= 55:
        accion = "ESPERAR"
    else:
        accion = "NO_OPERAR"

    if score >= 75:
        confianza = "ALTA"
    elif score >= 62:
        confianza = "MEDIA"
    elif score >= 50:
        confianza = "BAJA"
    else:
        confianza = "MUY_BAJA"

    return accion, confianza, score


def evaluar_decision_bootiq(decision_bootiq):
    """
    Árbitro central BootIQ V2.

    Este motor NO vuelve a analizar mercado, PA, setup ni protocolo.
    Solo combina evidencias ya calculadas por otros módulos:

    - estrategia
    - setup
    - consenso
    - riesgo
    - confirmación
    - fase4

    Objetivo:
    una sola decisión final basada en evidencias organizadas.
    """

    identidad = decision_bootiq.get("identidad", {})
    estrategia = decision_bootiq.get("estrategia", {})
    setup = decision_bootiq.get("setup", {})
    consenso = decision_bootiq.get("consenso", {})
    protocolo = decision_bootiq.get("protocolo", {})
    riesgos = decision_bootiq.get("riesgos", {})
    fase4 = decision_bootiq.get("fase4", {})
    evidencias = decision_bootiq.get("evidencias", {})
    pa_evidencias = evidencias.get("price_action", [])
    mercado_evidencias = evidencias.get("mercado", [])
    patron = _txt(identidad.get("patron", ""))

    score = 50
    razones = []
    advertencias = []
    bloqueos = []

    # =========================
    # 1. EVIDENCIA DE ESTRATEGIA
    # =========================
    puntaje = _num(estrategia.get("puntaje", 0))
    prioridad = _num(estrategia.get("prioridad", 0))
    score_final = _num(estrategia.get("score_final", 0))

    if puntaje >= 18:
        score = _agregar(score, 8, razones, "puntaje estrategia alto")
    elif puntaje >= 14:
        score = _agregar(score, 4, razones, "puntaje estrategia aceptable")
    elif puntaje > 0:
        score = _agregar(score, -4, advertencias, "puntaje estrategia bajo")

    if prioridad >= 3:
        score = _agregar(score, 5, razones, "prioridad alta")
    elif prioridad == 2:
        score = _agregar(score, 2, razones, "prioridad media")
    elif prioridad > 0:
        score = _agregar(score, -4, advertencias, "prioridad baja")

    if score_final >= 180:
        score = _agregar(score, 4, razones, "score final fuerte")
    elif score_final and score_final < 120:
        score = _agregar(score, -4, advertencias, "score final bajo")

    # =========================
    # 2. EVIDENCIA DE SETUP
    # =========================
    confianza_setup = _num(setup.get("confianza_setup", 0))
    estado_setup = _txt(setup.get("estado_setup", ""))
    nivel_setup = _txt(setup.get("nivel_setup", ""))

    if confianza_setup >= 75:
        score = _agregar(score, 10, razones, "setup muy confiable")
    elif confianza_setup >= 65:
        score = _agregar(score, 6, razones, "setup confiable")
    elif confianza_setup >= 52:
        score = _agregar(score, 2, razones, "setup medio")
    elif confianza_setup > 0:
        score = _agregar(score, -6, advertencias, "setup débil")

    if estado_setup == "PELIGROSO":
        score = _agregar(score, -8, advertencias, "setup peligroso")
    elif estado_setup == "MADURO":
        score = _agregar(score, 5, razones, "setup maduro")
    elif estado_setup == "CONFIRMABLE":
        score = _agregar(score, 3, razones, "setup confirmable")

    if nivel_setup == "BAJO":
        score = _agregar(score, -5, advertencias, "nivel setup bajo")

    # =========================
    # 3. EVIDENCIA DE CONSENSO
    # =========================
    valor_consenso = _num(consenso.get("consenso", 0))
    nivel_consenso = _txt(consenso.get("nivel_consenso", ""))

    if nivel_consenso == "PREMIUM":
        score = _agregar(score, 8, razones, "consenso premium")
    elif nivel_consenso == "ALTO":
        score = _agregar(score, 5, razones, "consenso alto")
    elif nivel_consenso == "BUENO":
        score = _agregar(score, 2, razones, "consenso bueno")
    elif nivel_consenso == "BAJO":
        score = _agregar(score, -4, advertencias, "consenso bajo")
    elif nivel_consenso == "MUY_BAJO":
        score = _agregar(score, -7, advertencias, "consenso muy bajo")
    elif valor_consenso:
        if valor_consenso >= 75:
            score = _agregar(score, 4, razones, "consenso numérico favorable")
        elif valor_consenso < 45:
            score = _agregar(score, -5, advertencias, "consenso numérico bajo")

    # =========================
    # 4. EVIDENCIA DE RIESGO
    # =========================
    riesgo_protocolo = _num(
        riesgos.get(
            "riesgo_protocolo",
            protocolo.get("riesgo_protocolo", 0)
        )
    )

    nivel_riesgo = _txt(
        riesgos.get(
            "nivel_riesgo_protocolo",
            protocolo.get("nivel_riesgo_protocolo", "")
        )
    )

    if nivel_riesgo == "MUY_BAJO":
        score = _agregar(score, 6, razones, "riesgo muy bajo")
    elif nivel_riesgo == "BAJO":
        score = _agregar(score, 3, razones, "riesgo bajo")
    elif nivel_riesgo == "MEDIO":
        score = _agregar(score, -2, advertencias, "riesgo medio")
    elif nivel_riesgo == "ALTO":
        score = _agregar(score, -8, advertencias, "riesgo alto")

    if riesgo_protocolo >= 85:
        bloqueos.append("riesgo protocolo crítico")
        score = _agregar(score, -15, advertencias, "riesgo protocolo crítico")
    elif riesgo_protocolo >= 70:
        score = _agregar(score, -8, advertencias, "riesgo protocolo elevado")
    elif 0 < riesgo_protocolo <= 25:
        score = _agregar(score, 4, razones, "riesgo protocolo favorable")

    # =========================
    # 5. EVIDENCIA DE CONFIRMACIÓN
    # =========================
    accion_confirmacion = _txt(protocolo.get("accion_confirmacion_ia", ""))
    nivel_confirmacion = _txt(protocolo.get("nivel_confirmacion_ia", ""))
    indice_confirmacion = _num(protocolo.get("indice_confirmacion_ia", 0))

    if accion_confirmacion == "ENTRAR":
        score = _agregar(score, 6, razones, "confirmación sugiere entrar")
    elif accion_confirmacion == "ESPERAR_2":
        score = _agregar(score, 2, razones, "confirmación sugiere esperar 2")
    elif accion_confirmacion == "ESPERAR_3":
        score = _agregar(score, -2, advertencias, "confirmación débil")
    elif accion_confirmacion == "CANCELAR":
        score = _agregar(score, -6, advertencias, "confirmación sugiere cancelar")

    if nivel_confirmacion == "PREMIUM":
        score = _agregar(score, 5, razones, "confirmación premium")
    elif nivel_confirmacion == "ALTO":
        score = _agregar(score, 3, razones, "confirmación alta")
    elif nivel_confirmacion == "BAJO":
        score = _agregar(score, -3, advertencias, "confirmación baja")

    if indice_confirmacion >= 75:
        score = _agregar(score, 3, razones, "índice confirmación alto")
    elif indice_confirmacion and indice_confirmacion < 42:
        score = _agregar(score, -3, advertencias, "índice confirmación bajo")

    # =========================
    # 6. EVIDENCIA FASE 4 / HISTORIAL
    # =========================
    fase4_bloquea = bool(fase4.get("fase4_debe_bloquear", False))
    fase4_confianza = _num(fase4.get("fase4_confianza", 50))
    fase4_decision = _txt(fase4.get("fase4_decision", ""))

    if fase4_decision == "NO_OPERAR" or fase4_bloquea:
        score = _agregar(score, -6, advertencias, "fase4 sugiere no operar")

    if fase4_confianza >= 70:
        score = _agregar(score, 5, razones, "fase4 confianza alta")
    elif fase4_confianza >= 60:
        score = _agregar(score, 2, razones, "fase4 confianza aceptable")
    elif fase4_confianza <= 40:
        score = _agregar(score, -4, advertencias, "fase4 confianza baja")

    # =========================
    # 7. AJUSTES HISTÓRICOS SUAVES POR FAMILIA
    # =========================
    if "CHOCH" in patron:
        score = _agregar(score, -5, advertencias, "CHOCH históricamente débil")

    if "PULLBACK ALCISTA" in patron:
        score = _agregar(score, 5, razones, "pullback alcista favorable")

    if "CONTINUACIÓN ALCISTA" in patron or "CONTINUACION ALCISTA" in patron:
        score = _agregar(score, 4, razones, "continuación alcista favorable")
    # =========================
    # 8. EVIDENCIAS PRICE ACTION
    # =========================
    for ev in pa_evidencias:
        if not isinstance(ev, dict):
            continue
    
        tipo_ev = _txt(ev.get("tipo", ""))
        direccion_ev = _txt(ev.get("direccion", ""))
        peso_ev = _num(ev.get("peso", 0))
        fuerza_ev = _num(ev.get("fuerza", 0))
        direccion_senal = _txt(identidad.get("direccion", ""))
    
        if direccion_ev and direccion_senal and direccion_ev == direccion_senal.upper():
            ajuste = min(8, max(1, peso_ev / 8))
    
            if fuerza_ev >= 0.45:
                score = _agregar(
                    score,
                    ajuste,
                    razones,
                    "evidencia PA a favor: " + tipo_ev
                )
    
        elif direccion_ev in ["CALL", "PUT"] and direccion_senal and direccion_ev != direccion_senal.upper():
            ajuste = min(8, max(2, peso_ev / 7))
    
            score = _agregar(
                score,
                -ajuste,
                advertencias,
                "evidencia PA en contra: " + tipo_ev
            )
    
        if tipo_ev == "CONTRADICCION_PA":
            score = _agregar(
                score,
                -6,
                advertencias,
                "contradicción price action"
            )
    # =========================
    # 9. EVIDENCIAS MERCADO SELECTIVAS
    # =========================
    tipos_mercado = []

    for ev in mercado_evidencias:
        if isinstance(ev, dict):
            tipos_mercado.append(_txt(ev.get("tipo", "")))

    set_mercado = set(tipos_mercado)
    direccion_senal = _txt(identidad.get("direccion", ""))

    # Evidencias buenas detectadas en backtest:
    # - TENDENCIA_ALCISTA + MERCADO_NORMAL
    # - TENDENCIA_ALCISTA + MERCADO_NORMAL + TENDENCIA_LIMPIA
    # - TENDENCIA_ALCISTA + MERCADO_NORMAL + TENDENCIA_FUERTE + TENDENCIA_LIMPIA
    # - TENDENCIA_BAJISTA + MERCADO_NORMAL + TENDENCIA_FUERTE + TENDENCIA_LIMPIA

    if (
        direccion_senal == "CALL"
        and "TENDENCIA_ALCISTA" in set_mercado
        and "MERCADO_NORMAL" in set_mercado
    ):
        score = _agregar(
            score,
            4,
            razones,
            "mercado selectivo favorable CALL: tendencia alcista normal"
        )

    if (
        direccion_senal == "CALL"
        and "TENDENCIA_ALCISTA" in set_mercado
        and "TENDENCIA_LIMPIA" in set_mercado
    ):
        score = _agregar(
            score,
            3,
            razones,
            "mercado selectivo favorable CALL: tendencia limpia"
        )

    if (
        direccion_senal == "PUT"
        and "TENDENCIA_BAJISTA" in set_mercado
        and "MERCADO_NORMAL" in set_mercado
        and "TENDENCIA_FUERTE" in set_mercado
        and "TENDENCIA_LIMPIA" in set_mercado
    ):
        score = _agregar(
            score,
            5,
            razones,
            "mercado selectivo favorable PUT: bajista fuerte limpia"
        )

    # Evidencias malas detectadas en backtest:
    # - TENDENCIA_BAJISTA + MERCADO_NORMAL
    # - TENDENCIA_BAJISTA + MERCADO_NORMAL + TENDENCIA_FUERTE
    # - MERCADO_NORMAL + TENDENCIA_DEBIL

    if (
        direccion_senal == "PUT"
        and "TENDENCIA_BAJISTA" in set_mercado
        and "MERCADO_NORMAL" in set_mercado
        and "TENDENCIA_LIMPIA" not in set_mercado
    ):
        score = _agregar(
            score,
            -4,
            advertencias,
            "mercado selectivo débil PUT: bajista normal sin limpieza"
        )

    if "TENDENCIA_DEBIL" in set_mercado:
        score = _agregar(
            score,
            -4,
            advertencias,
            "mercado selectivo penaliza tendencia débil"
        )

    if "TENDENCIA_AGOTADA" in set_mercado:
        score = _agregar(
            score,
            -3,
            advertencias,
            "mercado selectivo penaliza tendencia agotada"
        )
    # =========================
    # DECISIÓN FINAL
    # =========================
    accion, confianza, score = _clasificar(score, bloqueos)

    return {
        "accion": accion,
        "score": score,
        "confianza": confianza,
        "razones": razones,
        "advertencias": advertencias,
        "bloqueos": bloqueos,
    }


def evaluar_decision_unificada(senal, ctx):
    """
    Compatibilidad temporal BootIQ V1.

    Convierte senal + ctx a una estructura mínima tipo DecisionBootIQ
    y usa el árbitro central nuevo.

    Esta función se mantiene para no romper imports antiguos.
    """

    decision_bootiq = {
        "identidad": {
            "activo": senal.get("activo", ""),
            "tipo": senal.get("tipo", ""),
            "direccion": senal.get("direccion", ""),
            "patron": senal.get("patron", ""),
        },
        "estrategia": {
            "puntaje": senal.get("puntaje", 0),
            "prioridad": senal.get("prioridad", 0),
            "score_final": senal.get("score_final", 0),
            "calidad": senal.get("calidad", ""),
        },
        "mercado": {
            "tipo_mercado": senal.get("tipo_mercado", ctx.get("tipo_mercado", "")),
            "calidad_mercado": senal.get("calidad_mercado", ctx.get("calidad_mercado", "")),
            "score_mercado": senal.get("score_mercado", ctx.get("score_mercado", 0)),
            "estado_tendencia": senal.get("estado_tendencia", ctx.get("estado_tendencia", "")),
            "fuerza_tendencia": senal.get("fuerza_tendencia", ctx.get("fuerza_tendencia", 0)),
            "direccion_tendencia": senal.get("direccion_tendencia", ctx.get("direccion_tendencia", "")),
        },
        "price_action": {
            "accion_precio": senal.get("accion_precio", ctx.get("accion_precio", "")),
            "pa_tipo": senal.get("pa_tipo", ctx.get("pa_tipo", "")),
            "pa_direccion": senal.get("pa_direccion", ctx.get("pa_direccion", "")),
            "pa_fuerza": senal.get("pa_fuerza", ctx.get("pa_fuerza", 0)),
        },
        "setup": {
            "confianza_setup": senal.get("confianza_setup", 0),
            "estado_setup": senal.get("estado_setup", ""),
            "nivel_setup": senal.get("nivel_setup", ""),
            "calidad_setup": senal.get("calidad_setup", ""),
            "modo_entrada_setup": senal.get("modo_entrada_setup", ""),
        },
        "consenso": {
            "consenso": senal.get("consenso", 0),
            "nivel_consenso": senal.get("nivel_consenso", ""),
        },
        "protocolo": {
            "riesgo_protocolo": senal.get("riesgo_protocolo", 0),
            "nivel_riesgo_protocolo": senal.get("nivel_riesgo_protocolo", ""),
            "indice_confirmacion_ia": senal.get("indice_confirmacion_ia", 0),
            "nivel_confirmacion_ia": senal.get("nivel_confirmacion_ia", ""),
            "accion_confirmacion_ia": senal.get("accion_confirmacion_ia", ""),
        },
        "riesgos": {
            "riesgo_protocolo": senal.get("riesgo_protocolo", 0),
            "nivel_riesgo_protocolo": senal.get("nivel_riesgo_protocolo", ""),
        },
        "fase4": {
            "fase4_confianza": senal.get("fase4_confianza", 50),
            "fase4_decision": senal.get("fase4_decision", ""),
            "fase4_debe_bloquear": senal.get("fase4_debe_bloquear", False),
        },
    }

    return evaluar_decision_bootiq(decision_bootiq)