from motor_inferencia import inferir_confianza
from detector_riesgo_compuesto import evaluar_riesgo_compuesto
from motor_aprendizaje_historico import evaluar_aprendizaje_historico

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

    motivos = []
    motivos.extend(resultado_inferencia.get("motivos", []))
    motivos.extend(motivos_reglas)
    motivos.extend(riesgo_compuesto.get("motivos_riesgo", []))
    motivos.append(aprendizaje.get("motivo_aprendizaje", ""))
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