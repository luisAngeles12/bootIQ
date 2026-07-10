# motor_setup.py

def _txt(v):
    return str(v or "").upper().strip()


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
        return default


def _contiene(texto, *palabras):
    texto = _txt(texto)
    return any(p.upper() in texto for p in palabras)


def _leer_lista(valor):
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(x).upper().strip() for x in valor if str(x).strip()]
    return [x.strip().upper() for x in str(valor).split("|") if x.strip()]


def _limitar(valor, minimo=0, maximo=100):
    return max(minimo, min(maximo, valor))


def _nivel_estado_desde_confianza(confianza):
    if confianza >= 78:
        return "ALTO", "MADURO"
    if confianza >= 65:
        return "MEDIO_ALTO", "CONFIRMABLE"
    if confianza >= 52:
        return "MEDIO", "PENDIENTE_CONFIRMACION"
    if confianza >= 42:
        return "MEDIO_BAJO", "INMADURO"
    return "BAJO", "PELIGROSO"


def _agregar(razones, categoria, valor, motivo):
    signo = "+" if valor >= 0 else ""
    razones.append(f"{categoria} {signo}{valor}: {motivo}")


def identificar_setup(senal):
    tipo_setup = _txt(senal.get("tipo_setup", "INDEFINIDO"))
    patron = _txt(senal.get("patron", ""))
    direccion = _txt(senal.get("direccion", ""))
    accion_precio = _txt(senal.get("accion_precio", ""))
    pa_tipo = _txt(senal.get("pa_tipo", ""))
    pa_direccion = _txt(senal.get("pa_direccion", ""))
    mercado = _txt(senal.get("tipo_mercado", ""))
    tendencia = _txt(senal.get("estado_tendencia", ""))

    fortalezas = _leer_lista(senal.get("fortalezas_base", ""))
    riesgos = _leer_lista(senal.get("riesgos_base", ""))

    texto_total = " ".join([
        tipo_setup,
        patron,
        accion_precio,
        pa_tipo,
        mercado,
        tendencia,
        " ".join(fortalezas),
        " ".join(riesgos),
    ])

    familia_setup = "INDEFINIDA"
    subtipo_setup = "INDEFINIDO"
    protocolo_sugerido = "PROTOCOLO_GENERICO"

    if _contiene(texto_total, "SWEEP", "LIQUIDITY", "LIQUIDEZ"):
        familia_setup = "REVERSIÓN"
        protocolo_sugerido = "PROTOCOLO_SWEEP"

        if _contiene(pa_tipo, "AGOTAMIENTO", "RECHAZO"):
            subtipo_setup = "SWEEP_CON_RECHAZO_AGOTAMIENTO"
        elif _contiene(texto_total, "RUPTURA"):
            subtipo_setup = "SWEEP_RUPTURA_CONFIRMABLE"
        else:
            subtipo_setup = "SWEEP_SIMPLE"

    elif _contiene(texto_total, "CHOCH", "CAMBIO_ESTRUCTURA"):
        familia_setup = "REVERSIÓN_ESTRUCTURAL"
        protocolo_sugerido = "PROTOCOLO_CHOCH"

        if pa_direccion == direccion:
            subtipo_setup = "CHOCH_CON_PA_A_FAVOR"
        elif _contiene(tendencia, "DEBIL", "DÉBIL"):
            subtipo_setup = "CHOCH_TENDENCIA_DEBIL"
        else:
            subtipo_setup = "CHOCH_SIMPLE"

    elif _contiene(texto_total, "PULLBACK", "EMA", "RETROCESO"):
        familia_setup = "CONTINUACIÓN"
        protocolo_sugerido = "PROTOCOLO_PULLBACK"

        if "PULLBACK_TENDENCIA_INSUFICIENTE" in riesgos:
            subtipo_setup = "PULLBACK_TENDENCIA_INSUFICIENTE"
        elif _contiene(tendencia, "AGOTADA"):
            subtipo_setup = "PULLBACK_TENDENCIA_AGOTADA"
        elif "PULLBACK_CON_PA_Y_TENDENCIA" in fortalezas:
            subtipo_setup = "PULLBACK_CONTINUACION_LIMPIA"
        else:
            subtipo_setup = "PULLBACK_GENERICO"

    elif _contiene(texto_total, "SOPORTE", "RESISTENCIA", "ZONA", "RECHAZO"):
        familia_setup = "REACCIÓN_ZONA"
        protocolo_sugerido = "PROTOCOLO_REACCION_ZONA"

        if _contiene(pa_tipo, "RECHAZO") and pa_direccion == direccion:
            subtipo_setup = "ZONA_RECHAZO_CONFIRMADO"
        elif _contiene(accion_precio, "SIN_RUPTURA"):
            subtipo_setup = "ZONA_SIN_RUPTURA"
        else:
            subtipo_setup = "ZONA_GENERICA"

    elif _contiene(texto_total, "CONTINUACION", "CONTINUACIÓN", "TENDENCIA"):
        familia_setup = "CONTINUACIÓN"
        protocolo_sugerido = "PROTOCOLO_CONTINUACION"

        if _contiene(tendencia, "FUERTE"):
            subtipo_setup = "CONTINUACION_TENDENCIA_FUERTE"
        else:
            subtipo_setup = "CONTINUACION_SIMPLE"

    return {
        "familia_setup": familia_setup,
        "subtipo_setup": subtipo_setup,
        "protocolo_sugerido": protocolo_sugerido,
    }


def calcular_confianza_setup_por_capas(senal, identidad_setup):
    direccion = _txt(senal.get("direccion", ""))
    accion_precio = _txt(senal.get("accion_precio", ""))
    pa_tipo = _txt(senal.get("pa_tipo", ""))
    pa_direccion = _txt(senal.get("pa_direccion", ""))
    calidad_mercado = _txt(senal.get("calidad_mercado", ""))
    tipo_mercado = _txt(senal.get("tipo_mercado", ""))
    tendencia = _txt(senal.get("estado_tendencia", ""))
    base_estrategia = _txt(senal.get("base_estrategia", ""))
    nivel_consenso = _txt(senal.get("nivel_consenso", ""))
    score_final = _num(senal.get("score_final"))

    decision_aprendizaje = _txt(senal.get("decision_aprendizaje", ""))
    ajuste_aprendizaje = _num(
        senal.get(
            "ajuste_confianza_aprendizaje",
            senal.get("ajuste_confianza", 0)
        )
    )

    riesgos = _leer_lista(senal.get("riesgos_base", ""))
    fortalezas = _leer_lista(senal.get("fortalezas_base", ""))

    familia = identidad_setup["familia_setup"]
    subtipo = identidad_setup["subtipo_setup"]

    razones = []

    # ==========================
    # 1. IDENTIDAD DEL SETUP
    # Peso final: 30%
    # ==========================
    score_identidad = 50

    if familia == "REVERSIÓN":
        score_identidad = 58
        _agregar(razones, "IDENTIDAD", 8, "setup de reversión")

    if familia == "REVERSIÓN_ESTRUCTURAL":
        score_identidad = 56
        _agregar(razones, "IDENTIDAD", 6, "setup estructural")

    if familia == "CONTINUACIÓN":
        score_identidad = 52
        _agregar(razones, "IDENTIDAD", 2, "setup de continuación")

    if familia == "REACCIÓN_ZONA":
        score_identidad = 54
        _agregar(razones, "IDENTIDAD", 4, "setup de zona")

    if subtipo in [
        "SWEEP_CON_RECHAZO_AGOTAMIENTO",
        "ZONA_RECHAZO_CONFIRMADO",
        "PULLBACK_CONTINUACION_LIMPIA",
        "CONTINUACION_TENDENCIA_FUERTE",
    ]:
        score_identidad += 12
        _agregar(razones, "IDENTIDAD", 12, "subtipo fuerte confirmado")

    elif subtipo in [
        "SWEEP_RUPTURA_CONFIRMABLE",
        "PULLBACK_GENERICO",
        "CHOCH_SIMPLE",
    ]:
        score_identidad += 4
        _agregar(razones, "IDENTIDAD", 4, "subtipo operable pero confirmable")

    elif subtipo in [
        "SWEEP_SIMPLE",
        "ZONA_SIN_RUPTURA",
        "CHOCH_CON_PA_A_FAVOR",
    ]:
        score_identidad -= 2
        _agregar(razones, "IDENTIDAD", -2, "subtipo históricamente mixto")

    elif subtipo in [
        "PULLBACK_TENDENCIA_INSUFICIENTE",
        "PULLBACK_TENDENCIA_AGOTADA",
        "CONTINUACION_SIMPLE",
    ]:
        score_identidad -= 8
        _agregar(razones, "IDENTIDAD", -8, "subtipo débil")

    # ==========================
    # 2. PRICE ACTION
    # Peso final: 30%
    # ==========================
    score_pa = 50

    if pa_direccion == direccion:
        score_pa += 12
        _agregar(razones, "PA", 12, "PA alineado con dirección")

    elif pa_direccion and pa_direccion not in ["NEUTRA", "SIN_DATO"] and pa_direccion != direccion:
        score_pa -= 18
        _agregar(razones, "PA", -18, "PA contrario a la señal")

    if _contiene(pa_tipo, "RECHAZO", "AGOTAMIENTO"):
        score_pa += 12
        _agregar(razones, "PA", 12, "rechazo/agote confirmado")

    elif _contiene(pa_tipo, "IMPULSO"):
        if pa_direccion == direccion:
            score_pa += 8
            _agregar(razones, "PA", 8, "impulso a favor")
        else:
            score_pa += 2
            _agregar(razones, "PA", 2, "impulso no dominante")

    elif pa_tipo == "SIN_CONTEXTO_CLARO":
        score_pa -= 8
        _agregar(razones, "PA", -8, "sin contexto claro")

    if "PA_A_FAVOR_CALL_ALTA" in fortalezas:
        score_pa += 14
        _agregar(razones, "PA", 14, "PA CALL alta histórica")

    if "REACCION_CONFIRMADA" in fortalezas:
        score_pa += 8
        _agregar(razones, "PA", 8, "reacción confirmada")

    if "PA_A_FAVOR_PUT_DEBIL" in riesgos:
        score_pa -= 12
        _agregar(razones, "PA", -12, "PA PUT débil histórico")

    if "PA_A_FAVOR_CALL_DEBIL" in riesgos:
        score_pa -= 8
        _agregar(razones, "PA", -8, "PA CALL débil histórico")

    # ==========================
    # 3. MERCADO
    # Peso final: 20%
    # ==========================
    score_mercado = 50

    if calidad_mercado == "NORMAL":
        score_mercado += 6
        _agregar(razones, "MERCADO", 6, "mercado normal operable")

    elif calidad_mercado == "LIMPIO":
        score_mercado += 2
        _agregar(razones, "MERCADO", 2, "mercado limpio pero no siempre superior")

    elif calidad_mercado == "SUCIO":
        score_mercado -= 12
        _agregar(razones, "MERCADO", -12, "mercado sucio")

    if _contiene(tendencia, "AGOTADA"):
        score_mercado -= 10
        _agregar(razones, "MERCADO", -10, "tendencia agotada")

    elif _contiene(tendencia, "FUERTE"):
        score_mercado += 3
        _agregar(razones, "MERCADO", 3, "tendencia fuerte")

    elif _contiene(tendencia, "NORMAL"):
        score_mercado += 5
        _agregar(razones, "MERCADO", 5, "tendencia normal")

    if "MERCADO_NO_VALIDADO" in riesgos:
        score_mercado -= 6
        _agregar(razones, "MERCADO", -6, "mercado no validado")

    if "FUERZA_TENDENCIA_BAJA" in riesgos:
        score_mercado -= 5
        _agregar(razones, "MERCADO", -5, "fuerza tendencia baja")

    # ==========================
    # 4. APRENDIZAJE HISTÓRICO
    # Peso final: 10%
    # ==========================
    score_aprendizaje = 50

    if decision_aprendizaje == "FAVORABLE":
        ajuste = min(18, max(8, ajuste_aprendizaje))
        score_aprendizaje += ajuste
        _agregar(razones, "HISTÓRICO", ajuste, "aprendizaje favorable")

    elif decision_aprendizaje == "DEBIL":
        ajuste = max(-18, min(-8, ajuste_aprendizaje))
        score_aprendizaje += ajuste
        _agregar(razones, "HISTÓRICO", ajuste, "aprendizaje débil")

    else:
        _agregar(razones, "HISTÓRICO", 0, "sin aprendizaje suficiente")

    # ==========================
    # 5. CONSENSO
    # Peso final: 5%
    # ==========================
    score_consenso = 50

    if nivel_consenso == "PREMIUM":
        score_consenso += 10
        _agregar(razones, "CONSENSO", 10, "consenso premium")

    elif nivel_consenso == "ALTO":
        score_consenso += 8
        _agregar(razones, "CONSENSO", 8, "consenso alto")

    elif nivel_consenso == "BUENO":
        score_consenso -= 8
        _agregar(razones, "CONSENSO", -8, "consenso bueno históricamente débil")

    elif nivel_consenso == "MEDIO":
        score_consenso -= 2
        _agregar(razones, "CONSENSO", -2, "consenso medio")

    elif nivel_consenso in ["BAJO", "MUY_BAJO"]:
        score_consenso -= 4
        _agregar(razones, "CONSENSO", -4, "consenso bajo")

    # ==========================
    # 6. SCORE FINAL / BASE
    # Peso final: 5%
    # ==========================
    score_metricas = 50

    if base_estrategia == "FUERTE":
        score_metricas += 8
        _agregar(razones, "MÉTRICAS", 8, "base estrategia fuerte")

    elif base_estrategia == "DEBIL":
        score_metricas -= 4
        _agregar(razones, "MÉTRICAS", -4, "base estrategia débil")

    if score_final >= 200:
        score_metricas += 4
        _agregar(razones, "MÉTRICAS", 4, "score final muy alto")

    elif score_final >= 170:
        score_metricas += 2
        _agregar(razones, "MÉTRICAS", 2, "score final aceptable")

    elif score_final and score_final < 120:
        score_metricas -= 6
        _agregar(razones, "MÉTRICAS", -6, "score final bajo")

    # ==========================
    # PENALIZACIONES ESTRUCTURALES
    # No destruyen todo, solo ajustan.
    # ==========================
    penalizacion_extra = 0

    if "REACCION_SIN_CONFIRMACION_FUERTE" in riesgos:
        penalizacion_extra -= 8
        _agregar(razones, "RIESGO", -8, "reacción sin confirmación fuerte")

    if "CHOCH_CON_TENDENCIA_DEBIL" in riesgos:
        penalizacion_extra -= 3
        _agregar(razones, "RIESGO", -3, "CHOCH tendencia débil moderado")

    if "CONTINUACION_TENDENCIA_INSUFICIENTE" in riesgos:
        penalizacion_extra -= 5
        _agregar(razones, "RIESGO", -5, "continuación con tendencia insuficiente")

    if "CALL_RESISTENCIA_CERCA_SIN_RUPTURA" in accion_precio and direccion == "CALL":
        penalizacion_extra -= 4
        _agregar(razones, "RIESGO", -4, "CALL contra resistencia sin ruptura")

    if "PUT_SOPORTE_CERCA_SIN_RUPTURA" in accion_precio and direccion == "PUT":
        penalizacion_extra -= 2
        _agregar(razones, "RIESGO", -2, "PUT contra soporte sin ruptura")

    confianza = (
        score_identidad * 0.30 +
        score_pa * 0.30 +
        score_mercado * 0.20 +
        score_aprendizaje * 0.10 +
        score_consenso * 0.05 +
        score_metricas * 0.05
    )

    confianza += penalizacion_extra

    confianza = round(_limitar(confianza), 2)

    razones.append(
        "RESUMEN_CAPAS: "
        f"identidad={round(score_identidad, 2)}, "
        f"pa={round(score_pa, 2)}, "
        f"mercado={round(score_mercado, 2)}, "
        f"historico={round(score_aprendizaje, 2)}, "
        f"consenso={round(score_consenso, 2)}, "
        f"metricas={round(score_metricas, 2)}, "
        f"extra={round(penalizacion_extra, 2)}"
    )

    return confianza, razones


def clasificar_setup(senal):
    identidad_setup = identificar_setup(senal)

    familia_setup = identidad_setup["familia_setup"]
    subtipo_setup = identidad_setup["subtipo_setup"]
    protocolo_sugerido = identidad_setup["protocolo_sugerido"]

    confianza_setup, razones = calcular_confianza_setup_por_capas(
        senal,
        identidad_setup
    )

    direccion = _txt(senal.get("direccion", ""))
    accion_precio = _txt(senal.get("accion_precio", ""))

    if "CALL_RESISTENCIA_CERCA_SIN_RUPTURA" in accion_precio and direccion == "CALL":
        protocolo_sugerido = "PROTOCOLO_RUPTURA_RESISTENCIA"

    nivel_setup, estado_setup = _nivel_estado_desde_confianza(confianza_setup)

    return {
        "familia_setup": familia_setup,
        "subtipo_setup": subtipo_setup,
        "protocolo_sugerido": protocolo_sugerido,
        "nivel_setup": nivel_setup,
        "estado_setup": estado_setup,
        "confianza_setup": confianza_setup,
        "razones_clasificador_setup": " | ".join(razones),
    }


def aplicar_setup_decision(decision_bootiq):
    try:
        identidad = decision_bootiq.get("identidad", {})
        estrategia = decision_bootiq.get("estrategia", {})
        mercado = decision_bootiq.get("mercado", {})
        price_action = decision_bootiq.get("price_action", {})
        riesgos = decision_bootiq.get("riesgos", {})
        fortalezas = decision_bootiq.get("fortalezas", {})
        consenso = decision_bootiq.get("consenso", {})
        historial = decision_bootiq.get("historial", {})

        senal_temp = {
            "tipo_setup": decision_bootiq.get("setup", {}).get("tipo_setup", "INDEFINIDO"),
            "patron": identidad.get("patron", ""),
            "direccion": identidad.get("direccion", ""),
            "accion_precio": price_action.get("accion_precio", ""),
            "pa_tipo": price_action.get("pa_tipo", ""),
            "pa_direccion": price_action.get("pa_direccion", ""),
            "tipo_mercado": mercado.get("tipo_mercado", ""),
            "calidad_mercado": mercado.get("calidad_mercado", ""),
            "estado_tendencia": mercado.get("estado_tendencia", ""),
            "base_estrategia": estrategia.get("base_estrategia", ""),
            "nivel_consenso": consenso.get("nivel_consenso", ""),
            "score_final": estrategia.get("score_final", 0),
            "balance_setup": fortalezas.get("balance_setup", 0),
            "fortalezas_base": fortalezas.get("fortalezas_base", ""),
            "riesgos_base": riesgos.get("riesgos_base", ""),
            "decision_aprendizaje": historial.get("decision_aprendizaje", ""),
            "ajuste_confianza_aprendizaje": historial.get("ajuste_confianza_aprendizaje", 0),
            "ajuste_confianza": historial.get("ajuste_confianza", 0),
        }

        datos_setup = clasificar_setup(senal_temp)

        if "setup" not in decision_bootiq:
            decision_bootiq["setup"] = {}

        decision_bootiq["setup"].update(datos_setup)

        return decision_bootiq

    except Exception as e:
        if "setup" not in decision_bootiq:
            decision_bootiq["setup"] = {}

        decision_bootiq["setup"].update({
            "familia_setup": "ERROR",
            "subtipo_setup": "ERROR",
            "protocolo_sugerido": "PROTOCOLO_GENERICO",
            "nivel_setup": "ERROR",
            "estado_setup": "ERROR",
            "confianza_setup": 0,
            "razones_clasificador_setup": "error aplicando setup a DecisionBootIQ: " + str(e),
        })

        return decision_bootiq


def enriquecer_senal_con_setup(senal):
    datos_setup = clasificar_setup(senal)
    senal.update(datos_setup)
    return senal

def clasificar_setup_estrategico(senal, ctx):
    """
    Clasifica la oportunidad sin bloquearla.
    Sirve para que BootIQ aprenda qué tipo de setup está viendo:
    reversión, continuación, ruptura, rechazo, sweep, CHOCH o riesgo de zona.
    """

    patron = str(senal.get("patron", "")).lower()
    direccion = str(senal.get("direccion", "")).lower()

    tipo_mercado = ctx.get("tipo_mercado", "INDEFINIDO")
    calidad_mercado = ctx.get("calidad_mercado", "NORMAL")
    estado_tendencia = ctx.get("estado_tendencia", "INDEFINIDA")
    direccion_tendencia = ctx.get("direccion_tendencia", "INDEFINIDA")
    fuerza_tendencia = ctx.get("fuerza_tendencia", 0)

    cerca_soporte = ctx.get("cerca_soporte", False)
    cerca_resistencia = ctx.get("cerca_resistencia", False)

    rechazo = ctx.get("rechazo", 0)
    liquidity_sweep = ctx.get("liquidity_sweep", 0)
    ruptura_confirmada = ctx.get("ruptura_confirmada", False)

    pa_tipo = ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO")
    pa_direccion = ctx.get("pa_direccion", "NEUTRA")
    pa_fuerza = ctx.get("pa_fuerza", 0)

    puntaje = senal.get("puntaje", 0)

    direccion_setup = "ALCISTA" if direccion == "call" else "BAJISTA"
    a_favor_tendencia = direccion_setup == direccion_tendencia

    tipo_setup = "INDEFINIDO"
    calidad_setup = "MEDIA"
    modo_entrada = "DIRECTA"
    puntaje_extra = 0
    riesgo_extra = 0
    razones = []

    # =========================
    # UBICACIÓN EN ZONA
    # =========================
    if direccion == "call" and cerca_soporte:
        razones.append("CALL ubicado cerca de soporte")
        puntaje_extra += 2

    if direccion == "put" and cerca_resistencia:
        razones.append("PUT ubicado cerca de resistencia")
        puntaje_extra += 2

    if direccion == "call" and cerca_resistencia:
        razones.append("CALL cerca de resistencia: requiere ruptura o impulso")
        riesgo_extra += 2
        modo_entrada = "ESPERAR_RUPTURA"

    if direccion == "put" and cerca_soporte:
        razones.append("PUT cerca de soporte: requiere ruptura o impulso")
        riesgo_extra += 2
        modo_entrada = "ESPERAR_RUPTURA"

    # =========================
    # RECHAZO
    # =========================
    if direccion == "call" and rechazo == 1:
        tipo_setup = "RECHAZO_ALCISTA"
        puntaje_extra += 3
        razones.append("rechazo comprador detectado")

    if direccion == "put" and rechazo == -1:
        tipo_setup = "RECHAZO_BAJISTA"
        puntaje_extra += 3
        razones.append("rechazo vendedor detectado")

    # =========================
    # LIQUIDITY SWEEP
    # =========================
    if "liquidity sweep" in patron:
        if direccion == "call":
            tipo_setup = "SWEEP_ALCISTA"
        else:
            tipo_setup = "SWEEP_BAJISTA"

        puntaje_extra += 2
        razones.append("setup basado en barrida de liquidez")

        if (
            direccion == "call"
            and cerca_soporte
            and (rechazo == 1 or pa_direccion == "CALL")
        ):
            tipo_setup = "REVERSION_ALCISTA"
            calidad_setup = "BUENA"
            modo_entrada = "DIRECTA"
            puntaje_extra += 4
            razones.append("sweep alcista con soporte/rechazo: reversión válida")

        elif (
            direccion == "put"
            and cerca_resistencia
            and (rechazo == -1 or pa_direccion == "PUT")
        ):
            tipo_setup = "REVERSION_BAJISTA"
            calidad_setup = "BUENA"
            puntaje_extra += 4
            razones.append("sweep bajista con resistencia/rechazo: reversión válida")

        elif not a_favor_tendencia:
            riesgo_extra += 2
            razones.append("sweep contra tendencia sin confirmación completa")

    # =========================
    # CHOCH
    # =========================
    if "choch" in patron:
        if direccion == "call":
            tipo_setup = "CHOCH_ALCISTA"
        else:
            tipo_setup = "CHOCH_BAJISTA"

        razones.append("setup de cambio de estructura")

        if pa_direccion in ["CALL", "PUT"] and pa_direccion == direccion.upper():
            puntaje_extra += 3
            calidad_setup = "BUENA"
            razones.append("CHOCH con price action profesional a favor")

        if ruptura_confirmada:
            puntaje_extra += 3
            calidad_setup = "BUENA"
            modo_entrada = "DIRECTA"
            razones.append("CHOCH con ruptura confirmada")

        if not a_favor_tendencia and fuerza_tendencia >= 60:
            riesgo_extra += 3
            razones.append("CHOCH contra tendencia fuerte")

    # =========================
    # PULLBACK / CONTINUACIÓN
    # =========================
    if "pullback" in patron or "continuacion" in patron or "continuación" in patron:
        tipo_setup = "CONTINUACION"

        if a_favor_tendencia:
            puntaje_extra += 3
            razones.append("continuación a favor de tendencia")

        if fuerza_tendencia >= 60:
            puntaje_extra += 3
            calidad_setup = "BUENA"
            razones.append("tendencia con fuerza suficiente")

        if not a_favor_tendencia:
            riesgo_extra += 4
            calidad_setup = "DEBIL"
            razones.append("pullback/continuación contra tendencia")

    # =========================
    # BREAKOUT / RETEST
    # =========================
    if "breakout" in patron or "retest" in patron:
        tipo_setup = "RUPTURA_RETEST"

        if ruptura_confirmada:
            puntaje_extra += 4
            calidad_setup = "BUENA"
            modo_entrada = "DIRECTA"
            razones.append("ruptura/retest confirmado")

        else:
            modo_entrada = "ESPERAR_CONFIRMACION"
            riesgo_extra += 2
            razones.append("ruptura/retest sin confirmación completa")

    # =========================
    # PRICE ACTION PROFESIONAL
    # =========================
    if pa_tipo in [
        "RECHAZO_COMPRADOR_CONFIRMADO",
        "RECHAZO_VENDEDOR_CONFIRMADO",
        "AGOTAMIENTO_BAJISTA_CONFIRMADO",
        "AGOTAMIENTO_ALCISTA_CONFIRMADO"
    ]:
        puntaje_extra += 4
        calidad_setup = "BUENA"
        razones.append("price action profesional confirma rechazo/agottamiento")

    if pa_tipo in [
        "IMPULSO_ALCISTA_FUERTE",
        "IMPULSO_BAJISTA_FUERTE"
    ]:
        puntaje_extra += 2
        razones.append("price action muestra impulso fuerte")

    if pa_tipo == "SIN_CONTEXTO_CLARO":
        riesgo_extra += 2
        razones.append("price action sin contexto claro")

    # =========================
    # CALIDAD DEL MERCADO
    # =========================
    if calidad_mercado == "LIMPIO":
        puntaje_extra += 2
        razones.append("mercado limpio")

    if calidad_mercado == "NORMAL":
        razones.append("mercado normal operable")

    if calidad_mercado in ["SUCIO", "CAOTICO"]:
        riesgo_extra += 4
        calidad_setup = "DEBIL"
        razones.append("mercado sucio/caótico")

    # =========================
    # CLASIFICACIÓN FINAL
    # =========================
    balance = puntaje + puntaje_extra - riesgo_extra

    if balance >= 26 and riesgo_extra <= 2:
        calidad_setup = "PREMIUM"
    elif balance >= 21 and riesgo_extra <= 4:
        calidad_setup = "BUENA"
    elif balance >= 16:
        calidad_setup = "MEDIA"
    else:
        calidad_setup = "DEBIL"

    if riesgo_extra >= 6 and calidad_setup != "PREMIUM":
        modo_entrada = "NO_OPERAR"

    return {
        "tipo_setup": tipo_setup,
        "calidad_setup": calidad_setup,
        "modo_entrada": modo_entrada,
        "puntaje_extra_setup": puntaje_extra,
        "riesgo_extra_setup": riesgo_extra,
        "balance_setup": balance,
        "a_favor_tendencia": a_favor_tendencia,
        "razones_setup": razones,
    }    
