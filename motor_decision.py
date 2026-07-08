from motor_inferencia import inferir_confianza
from detector_riesgo_compuesto import evaluar_riesgo_compuesto
from motor_aprendizaje_historico import evaluar_aprendizaje_historico
from motor_ponderacion import calcular_ponderacion_estadistica

UMBRAL_OPERAR_DIRECTO = 65.0
UMBRAL_OPERAR_NORMAL = 50.0
UMBRAL_PROTOCOLO_ESTRICTO = 38.0

PESO_MINIMO_DECISION = 0.55
PESO_MAXIMO_DECISION = 1.30


def limitar_peso(peso):
    return max(PESO_MINIMO_DECISION, min(PESO_MAXIMO_DECISION, peso))


def _txt(v):
    return str(v or "").lower().strip()


def aplicar_reglas_generales(evidencia):
    peso = 1.0
    motivos = []

    patron = _txt(evidencia.get("patron"))
    direccion = _txt(evidencia.get("direccion"))
    tipo_mercado = _txt(evidencia.get("tipo_mercado"))
    pa_tipo = _txt(evidencia.get("pa_tipo"))
    pa_direccion = _txt(evidencia.get("pa_direccion"))
    accion_precio = _txt(evidencia.get("accion_precio"))
    nivel_consenso = _txt(evidencia.get("nivel_consenso"))
    base_estrategia = _txt(evidencia.get("base_estrategia"))
    fortalezas_base = _txt(evidencia.get("fortalezas_base"))
    riesgos_base = _txt(evidencia.get("riesgos_base"))
    tipo_setup = _txt(evidencia.get("tipo_setup"))

    if nivel_consenso in ["muy_bajo", "bajo"]:
        peso *= 0.96
        motivos.append("Ajuste suave: consenso bajo.")

    if base_estrategia == "media":
        peso *= 0.97
        motivos.append("Ajuste suave: base media.")

    if base_estrategia == "debil":
        peso *= 0.95
        motivos.append("Ajuste suave: base débil.")

    if "sin_contexto_claro" in riesgos_base or pa_tipo == "sin_contexto_claro":
        peso *= 0.96
        motivos.append("Ajuste suave: PA sin contexto claro.")

    if "contra_tendencia" in riesgos_base:
        peso *= 0.95
        motivos.append("Ajuste suave: contra tendencia.")

    if "pullback" in patron or "pullback" in tipo_setup:
        peso *= 0.96
        motivos.append("Ajuste suave: pullback requiere confirmación.")

    if "resistencia_cerca_sin_ruptura" in accion_precio:
        peso *= 0.92
        motivos.append("Ajuste fuerte: CALL/resistencia sin ruptura.")

    if "soporte_cerca_sin_ruptura" in accion_precio:
        peso *= 0.98
        motivos.append("Ajuste leve: soporte sin ruptura.")

    if tipo_mercado == "rango":
        peso *= 1.06
        motivos.append("Bono: mercado en rango.")

    if "choch" in patron or "choch" in tipo_setup:
        peso *= 1.06
        motivos.append("Bono: CHOCH.")

    if "sweep" in patron or "sweep" in tipo_setup:
        peso *= 1.03
        motivos.append("Bono leve: sweep.")

    if pa_direccion == direccion:
        peso *= 1.05
        motivos.append("Bono: PA alineado.")

    if "impulso" in pa_tipo and pa_direccion == direccion:
        peso *= 1.04
        motivos.append("Bono: impulso a favor.")

    if "rechazo" in pa_tipo and pa_direccion == direccion:
        peso *= 1.06
        motivos.append("Bono: rechazo confirmado.")

    if "tendencia_a_favor" in fortalezas_base:
        peso *= 1.04
        motivos.append("Bono: tendencia a favor.")

    return limitar_peso(round(peso, 3)), motivos


def regla_bloqueo_duro_contextual(evidencia):
    protocolo_sugerido = _txt(evidencia.get("protocolo_sugerido"))
    estado_setup = _txt(evidencia.get("estado_setup"))
    nivel_setup = _txt(evidencia.get("nivel_setup"))
    confianza_setup = float(evidencia.get("confianza_setup", 50) or 50)
    accion_precio = _txt(evidencia.get("accion_precio"))
    direccion = _txt(evidencia.get("direccion"))
    riesgos_base = _txt(evidencia.get("riesgos_base"))
    fortalezas_base = _txt(evidencia.get("fortalezas_base"))
    pa_tipo = _txt(evidencia.get("pa_tipo"))
    nivel_consenso = _txt(evidencia.get("nivel_consenso"))

    if (
        "pa_a_favor_call_debil" in riesgos_base
        and nivel_consenso in ["muy_bajo", "bajo"]
        and confianza_setup < 50
    ):
        return True, "Bloqueo duro: CALL débil + consenso bajo + setup débil."

    if (
        "choch_con_tendencia_debil" in riesgos_base
        and nivel_consenso in ["muy_bajo", "bajo"]
        and confianza_setup < 50
    ):
        return True, "Bloqueo duro: CHOCH con tendencia débil + consenso bajo."

    if (
        "impulso_alcista_fuerte_debil_historico" in riesgos_base
        and nivel_consenso in ["muy_bajo", "bajo"]
        and confianza_setup < 50
    ):
        return True, "Bloqueo duro: impulso alcista débil histórico + consenso bajo."

    if (
        protocolo_sugerido == "protocolo_ruptura_resistencia"
        and estado_setup == "pendiente_confirmacion"
        and nivel_setup in ["medio_bajo", "bajo"]
        and confianza_setup < 50
        and nivel_consenso in ["muy_bajo", "bajo"]
    ):
        return True, "Bloqueo duro: ruptura de resistencia pendiente + setup débil + consenso bajo."

    if (
        direccion == "call"
        and "call_resistencia_cerca_sin_ruptura" in accion_precio
        and nivel_consenso in ["muy_bajo", "bajo"]
        and confianza_setup < 52
    ):
        return True, "Bloqueo duro: CALL contra resistencia sin ruptura + consenso bajo."

    if (
        "call_resistencia_sin_ruptura" in riesgos_base
        and "pa_a_favor_call" not in fortalezas_base
        and pa_tipo not in ["impulso_alcista_fuerte", "rechazo_comprador_confirmado"]
        and nivel_consenso in ["muy_bajo", "bajo"]
    ):
        return True, "Bloqueo duro: resistencia sin ruptura sin PA alcista ni consenso."

    return False, ""
def sugerir_modo_ejecucion(confianza, riesgo_nivel, evidencia):
    tipo_setup = _txt(evidencia.get("tipo_setup"))
    patron = _txt(evidencia.get("patron"))
    accion_precio = _txt(evidencia.get("accion_precio"))

    texto = " ".join([tipo_setup, patron, accion_precio])
    
    if riesgo_nivel == "EXTREMO":
        return "NO_OPERAR"

    if "resistencia_cerca_sin_ruptura" in texto:
        return "NO_OPERAR_SI_NO_ROMPE"

    if "pullback" in texto:
        if confianza >= UMBRAL_OPERAR_NORMAL:
            return "ESPERAR_RECHAZO_IMPULSO"
        return "ESPERAR_2_VELAS_RECHAZO"

    if "choch" in texto:
        return "ESPERAR_RUPTURA_IMPULSO"

    if "sweep" in texto or "liquidity" in texto:
        return "ESPERAR_RECHAZO"

    if "soporte" in texto or "resistencia" in texto or "zona" in texto:
        return "ESPERAR_RECHAZO_O_RUPTURA"

    if confianza >= UMBRAL_OPERAR_DIRECTO and riesgo_nivel in ["BAJO", "MEDIO"]:
        return "DIRECTA_PERMITIDA"

    if confianza >= UMBRAL_OPERAR_NORMAL:
        return "ENTRADA_CONFIRMADA"

    return "PROTOCOLO_ESTRICTO"


def evaluar_decision(evidencia):
    resultado_inferencia = inferir_confianza(evidencia)

    confianza_base = resultado_inferencia.get("confianza", 50.0)
    decision_inferencia = resultado_inferencia.get("decision", "NEUTRA")
    peso_inferencia = resultado_inferencia.get("peso_final", 1.0)

    peso_reglas, motivos_reglas = aplicar_reglas_generales(evidencia)
    riesgo_compuesto = evaluar_riesgo_compuesto(evidencia)
    aprendizaje = evaluar_aprendizaje_historico(evidencia)

    peso_final = limitar_peso(round(peso_inferencia * peso_reglas, 3))
    
    # Antes usaba 50 fijo y destruía la confianza real de inferencia.
    # Ahora respeta la confianza calculada por motor_inferencia.
    confianza = round(max(0, min(100, confianza_base * peso_final)), 2)
    
    confianza += aprendizaje.get("ajuste_confianza_aprendizaje", 0)
    confianza = round(max(0, min(100, confianza)), 2)

    riesgo_nivel = riesgo_compuesto.get("riesgo_nivel", "BAJO")
    riesgo_puntos = riesgo_compuesto.get("riesgo_puntos", 0)
    pa_evidencias = evidencia.get("pa_evidencias", [])
    ajuste_evidencias = 0
    motivos_evidencias = []
    direccion = _txt(evidencia.get("direccion", ""))
    pa_evidencias = evidencia.get("pa_evidencias", [])
    mercado_evidencias = evidencia.get("mercado_evidencias", [])
    
    ajuste_evidencias = 0
    motivos_evidencias = []
    motivos = []
    motivos.extend(resultado_inferencia.get("motivos", []))
    motivos.extend(motivos_reglas)
    motivos.extend(riesgo_compuesto.get("motivos_riesgo", []))
    motivos.append(aprendizaje.get("motivo_aprendizaje", ""))
    for ev in pa_evidencias:
        tipo = _txt(ev.get("tipo", ""))
        direccion_ev = _txt(ev.get("direccion", ""))
        peso = float(ev.get("peso", 0) or 0)
        fuerza = float(ev.get("fuerza", 0) or 0)
        direccion = _txt(evidencia.get("direccion", ""))
    
        if direccion_ev == direccion.upper() and fuerza >= 0.45:
            ajuste_evidencias += min(6, max(1, peso / 8))
            motivos_evidencias.append("PA a favor: " + tipo)
    
        elif direccion_ev in ["call", "put"] and direccion_ev != direccion:
            ajuste_evidencias -= min(6, max(1, abs(peso) / 8))
            motivos_evidencias.append("PA en contra: " + tipo)
    
        if tipo == "contradiccion_pa":
            ajuste_evidencias -= 5
            motivos_evidencias.append("PA contradictorio")

    bloqueo_duro, motivo_bloqueo = regla_bloqueo_duro_contextual(evidencia)

    modo_ejecucion_sugerido = sugerir_modo_ejecucion(
        confianza=confianza,
        riesgo_nivel=riesgo_nivel,
        evidencia=evidencia
    )

    operar = True
    decision = "OPERAR_CON_PROTOCOLO"

    if bloqueo_duro:
        operar = False
        decision = "NO_OPERAR"
        motivos.append(motivo_bloqueo)
        confianza = round(max(0, min(100, confianza + ajuste_evidencias)), 2)
        motivos.extend(motivos_evidencias)
    elif riesgo_nivel == "EXTREMO":
        operar = False
        decision = "NO_OPERAR"
        motivos.append("Bloqueada por riesgo extremo.")

    elif confianza >= UMBRAL_OPERAR_DIRECTO:
        decision = "OPERAR_DIRECTO_O_CONFIRMADO"
        motivos.append("Aprobada: confianza alta.")

    elif confianza >= UMBRAL_OPERAR_NORMAL:
        decision = "OPERAR_CON_CONFIRMACION"
        motivos.append("Aprobada: requiere confirmación del protocolo.")

    elif confianza >= UMBRAL_PROTOCOLO_ESTRICTO:
        decision = "OPERAR_CON_PROTOCOLO_ESTRICTO"
        motivos.append("Permitida solo con protocolo estricto.")

    else:
        operar = True
        decision = "SOLO_SI_PROTOCOLO_CONFIRMA"
        motivos.append("Confianza baja: no entrada directa; solo permitir si el protocolo confirma fuerte.")

    return {
        "operar": operar,
        "decision": decision,
        "confianza": confianza,
        "confianza_base": confianza_base,
        "decision_inferencia": decision_inferencia,
        "peso_inferencia": peso_inferencia,
        "peso_reglas": peso_reglas,
        "peso_final": peso_final,
        "motivos": motivos,
        "detalle_inferencia": resultado_inferencia,
        "riesgo_compuesto": riesgo_compuesto,
        "riesgo_nivel": riesgo_nivel,
        "riesgo_puntos": riesgo_puntos,
        "modo_ejecucion_sugerido": modo_ejecucion_sugerido,
        "bloquear_por_riesgo_y_confianza": bloqueo_duro or riesgo_nivel == "EXTREMO",
        "aprendizaje_historico": aprendizaje,
        "decision_aprendizaje": aprendizaje.get("decision_aprendizaje", ""),
        "ajuste_confianza_aprendizaje": aprendizaje.get("ajuste_confianza_aprendizaje", 0),
    }
def evaluar_decision_cerebro_unico(evidencia):
    """
    Cerebro único BootIQ.

    Integra especialistas.
    No bloquea desde módulos externos.
    Decide una sola vez al final.
    """

    resultado_inferencia = inferir_confianza(evidencia)
    riesgo_compuesto = evaluar_riesgo_compuesto(evidencia)
    aprendizaje = evaluar_aprendizaje_historico(evidencia)

    confianza_base = resultado_inferencia.get("confianza", 50.0)
    ajuste_aprendizaje = aprendizaje.get("ajuste_confianza_aprendizaje", 0)

    confianza = confianza_base + ajuste_aprendizaje
    confianza = round(max(0, min(100, confianza)), 2)

    riesgo_nivel = riesgo_compuesto.get("riesgo_nivel", "BAJO")
    riesgo_puntos = riesgo_compuesto.get("riesgo_puntos", 0)

    direccion = _txt(evidencia.get("direccion", ""))
    patron = _txt(evidencia.get("patron", ""))
    tipo_setup = _txt(evidencia.get("tipo_setup", ""))
    subtipo_setup = _txt(evidencia.get("subtipo_setup", ""))
    protocolo = _txt(evidencia.get("protocolo_sugerido", ""))
    accion_precio = _txt(evidencia.get("accion_precio", ""))
    riesgos_base = _txt(evidencia.get("riesgos_base", ""))
    fortalezas_base = _txt(evidencia.get("fortalezas_base", ""))

    pa_evidencias = evidencia.get("pa_evidencias", [])
    mercado_evidencias = evidencia.get("mercado_evidencias", [])

    ajuste_evidencias = 0
    motivos = []

    motivos.extend(resultado_inferencia.get("motivos", []))
    motivos.extend(riesgo_compuesto.get("motivos_riesgo", []))

    motivo_aprendizaje = aprendizaje.get("motivo_aprendizaje", "")
    if motivo_aprendizaje:
        motivos.append(motivo_aprendizaje)

    # =========================
    # LECTURA PRICE ACTION
    # =========================
    for ev in pa_evidencias:
        tipo = _txt(ev.get("tipo", ""))
        direccion_ev = _txt(ev.get("direccion", ""))
        peso = float(ev.get("peso", 0) or 0)
        fuerza = float(ev.get("fuerza", 0) or 0)
        confirmada = bool(ev.get("confirmada", False))

        if tipo == "contradiccion_pa":
            ajuste_evidencias -= 6
            motivos.append("PA: contradicción interna detectada.")
            continue

        if direccion_ev in ["call", "put"]:
            if direccion_ev == direccion:
                ajuste = min(5, max(1, peso / 10))
                if confirmada:
                    ajuste += 1

                if fuerza < 0.45:
                    ajuste *= 0.5
                    motivos.append("PA a favor débil: " + tipo)
                else:
                    motivos.append("PA a favor: " + tipo)

                ajuste_evidencias += ajuste
            else:
                ajuste = min(6, max(2, abs(peso) / 9))
                ajuste_evidencias -= ajuste
                motivos.append("PA en contra: " + tipo)

    # =========================
    # LECTURA MERCADO
    # =========================
    tipos_mercado = set()

    for ev in mercado_evidencias:
        if isinstance(ev, dict):
            tipos_mercado.add(_txt(ev.get("tipo", "")))

    if direccion == "call" and "tendencia_alcista" in tipos_mercado and "mercado_normal" in tipos_mercado:
        ajuste_evidencias += 3
        motivos.append("Mercado: CALL alineado con tendencia alcista normal.")

    if direccion == "call" and "tendencia_alcista" in tipos_mercado and "tendencia_limpia" in tipos_mercado:
        ajuste_evidencias += 2
        motivos.append("Mercado: CALL con tendencia limpia.")

    if (
        direccion == "put"
        and "tendencia_bajista" in tipos_mercado
        and "mercado_normal" in tipos_mercado
        and "tendencia_fuerte" in tipos_mercado
        and "tendencia_limpia" in tipos_mercado
    ):
        ajuste_evidencias += 4
        motivos.append("Mercado: PUT bajista fuerte y limpio.")

    if (
        direccion == "put"
        and "tendencia_bajista" in tipos_mercado
        and "mercado_normal" in tipos_mercado
        and "tendencia_limpia" not in tipos_mercado
    ):
        ajuste_evidencias -= 4
        motivos.append("Mercado: PUT bajista normal sin limpieza.")

    if "tendencia_debil" in tipos_mercado:
        ajuste_evidencias -= 3
        motivos.append("Mercado: tendencia débil.")

    if "tendencia_agotada" in tipos_mercado:
        ajuste_evidencias -= 3
        motivos.append("Mercado: tendencia agotada.")

    if "mercado_sucio" in tipos_mercado:
        ajuste_evidencias -= 4
        motivos.append("Mercado: sucio o caótico.")

    # =========================
    # LECTURA ESTRATÉGICA
    # =========================

    if "choch" in patron or "choch" in tipo_setup or "choch" in subtipo_setup:
        if "choch_con_pa_a_favor" in subtipo_setup:
            ajuste_evidencias += 2
            motivos.append("Estrategia: CHOCH con PA a favor.")

        if "choch_con_tendencia_debil" in riesgos_base:
            ajuste_evidencias -= 5
            motivos.append("Estrategia: CHOCH con tendencia débil.")

        if "choch_sin_pa_valido" in riesgos_base:
            ajuste_evidencias -= 4
            motivos.append("Estrategia: CHOCH sin PA válido.")

    if "pullback" in patron or "pullback" in tipo_setup or "pullback" in subtipo_setup:
        if "pullback_tendencia_insuficiente" in riesgos_base:
            ajuste_evidencias -= 4
            motivos.append("Estrategia: pullback con tendencia insuficiente.")

        if "pullback_con_pa_y_tendencia" in fortalezas_base:
            ajuste_evidencias += 3
            motivos.append("Estrategia: pullback con PA y tendencia.")

        if "pullback_balance_positivo" in subtipo_setup:
            ajuste_evidencias += 2
            motivos.append("Estrategia: pullback con balance positivo.")

    if "sweep" in patron or "sweep" in tipo_setup or "sweep" in subtipo_setup or "liquidity" in patron:
        if "sweep_sin_confirmacion_pa" in riesgos_base:
            ajuste_evidencias -= 4
            motivos.append("Estrategia: sweep sin confirmación PA.")

        if "sweep_con_confirmacion_pa_debil" in riesgos_base:
            ajuste_evidencias -= 3
            motivos.append("Estrategia: sweep con confirmación PA débil.")

        if "sweep_rupTura_confirmable".lower() in subtipo_setup:
            ajuste_evidencias += 1
            motivos.append("Estrategia: sweep con ruptura confirmable.")

    if "call_resistencia_sin_ruptura" in riesgos_base or "call_resistencia" in accion_precio:
        ajuste_evidencias -= 5
        motivos.append("Estrategia: CALL cerca de resistencia sin ruptura.")

    if "put_soporte_sin_ruptura" in riesgos_base or "put_soporte" in accion_precio:
        ajuste_evidencias -= 2
        motivos.append("Estrategia: PUT cerca de soporte sin ruptura.")

    if "reaccion_confirmada" in fortalezas_base or "zona_rechazo_confirmado" in subtipo_setup:
        ajuste_evidencias += 2
        motivos.append("Estrategia: reacción/zona confirmada.")

    if "continuacion_tendencia_insuficiente" in riesgos_base:
        ajuste_evidencias -= 3
        motivos.append("Estrategia: continuación con tendencia insuficiente.")

    confianza = round(max(0, min(100, confianza + ajuste_evidencias)), 2)
    ponderacion = calcular_ponderacion_estadistica(evidencia)

    ajuste_ponderacion = ponderacion.get("ajuste_ponderacion", 0)
    confianza = round(max(0, min(100, confianza + ajuste_ponderacion)), 2)
    
    motivos.extend(ponderacion.get("motivos_ponderacion", []))
    # =========================
    # DECISIÓN FINAL ÚNICA RECALIBRADA
    # =========================
    
    if riesgo_nivel == "EXTREMO" and confianza < 52:
        decision = "NO_OPERAR"
        operar = False
        motivos.append("Cerebro único: riesgo extremo con confianza insuficiente.")
    
    elif riesgo_nivel == "EXTREMO" and confianza >= 52:
        decision = "OPERAR_CON_PROTOCOLO"
        operar = True
        motivos.append("Cerebro único: riesgo extremo compensado; solo protocolo estricto.")
    elif confianza >= 62 and riesgo_nivel in ["BAJO", "MEDIO"]:
        decision = "OPERAR"
        operar = True
        motivos.append("Cerebro único: confianza alta y riesgo aceptable.")
    
    elif confianza >= 48:
        decision = "OPERAR_CON_PROTOCOLO"
        operar = True
        motivos.append("Cerebro único: confianza media, requiere protocolo.")
    
    else:
        decision = "NO_OPERAR"
        operar = False
        motivos.append("Cerebro único: confianza insuficiente.")
    return {
        "operar": operar,
        "decision": decision,
        "confianza": confianza,
        "confianza_base": confianza_base,
        "ajuste_evidencias": round(ajuste_evidencias, 2),
        "riesgo_nivel": riesgo_nivel,
        "riesgo_puntos": riesgo_puntos,
        "motivos": motivos,
        "detalle_inferencia": resultado_inferencia,
        "riesgo_compuesto": riesgo_compuesto,
        "aprendizaje_historico": aprendizaje,
        "decision_aprendizaje": aprendizaje.get("decision_aprendizaje", ""),
        "ajuste_confianza_aprendizaje": ajuste_aprendizaje,
        "ajuste_ponderacion": ajuste_ponderacion,
        "ponderacion_estadistica": ponderacion,
    }