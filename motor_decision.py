from motor_inferencia import inferir_confianza
from detector_riesgo_compuesto import evaluar_riesgo_compuesto

UMBRAL_OPERAR = 60.0
UMBRAL_NO_OPERAR = 45.0

PENALIZACION_SUAVE = 0.92
PENALIZACION_MEDIA = 0.84
PENALIZACION_FUERTE = 0.70

BONO_SUAVE = 1.06
BONO_MEDIO = 1.12

PESO_MINIMO_DECISION = 0.50
PESO_MAXIMO_DECISION = 1.35


def limitar_peso(peso):
    return max(PESO_MINIMO_DECISION, min(PESO_MAXIMO_DECISION, peso))


def aplicar_reglas_generales(evidencia):
    """
    Reglas generales basadas en hallazgos estadísticos.
    No reemplazan la base de conocimiento.
    Solo ayudan cuando la muestra histórica es pequeña.
    """

    peso = 1.0
    motivos = []

    patron = str(evidencia.get("patron", "")).lower()
    direccion = str(evidencia.get("direccion", "")).lower()
    tipo_mercado = str(evidencia.get("tipo_mercado", "")).lower()
    estado_tendencia = str(evidencia.get("estado_tendencia", "")).lower()
    pa_tipo = str(evidencia.get("pa_tipo", "")).lower()
    pa_direccion = str(evidencia.get("pa_direccion", "")).lower()
    accion_precio = str(evidencia.get("accion_precio", "")).lower()
    nivel_consenso = str(evidencia.get("nivel_consenso", "")).lower()
    base_estrategia = str(evidencia.get("base_estrategia", "")).lower()
    fortalezas_base = str(evidencia.get("fortalezas_base", "")).lower()
    riesgos_base = str(evidencia.get("riesgos_base", "")).lower()

    # ==========================
    # PENALIZACIONES CALL
    # ==========================
    if direccion == "call":
        if "pullback_alcista" in patron or "pullback alcista" in patron:
            peso *= PENALIZACION_FUERTE
            motivos.append("Penalización fuerte: pullback alcista históricamente débil.")

        if "choch_alcista" in patron or "choch alcista" in patron:
            peso *= PENALIZACION_MEDIA
            motivos.append("Penalización media: CHOCH alcista con rendimiento bajo.")

        if tipo_mercado == "tendencia_alcista" and estado_tendencia == "alcista_normal":
            peso *= PENALIZACION_MEDIA
            motivos.append("Penalización media: ALCISTA_NORMAL ha mostrado bajo rendimiento.")

        if pa_direccion == "call":
            peso *= PENALIZACION_MEDIA
            motivos.append("Penalización media: PA a favor de CALL ha sido débil en validación.")

        if "impulso_alcista_fuerte" in pa_tipo:
            peso *= PENALIZACION_FUERTE
            motivos.append("Penalización fuerte: impulso alcista fuerte terminó siendo mala señal.")

        if "call_resistencia_cerca_sin_ruptura" in accion_precio:
            peso *= PENALIZACION_MEDIA
            motivos.append("Penalización media: CALL con resistencia cerca sin ruptura.")

    # ==========================
    # PENALIZACIONES PUT
    # ==========================
    if direccion == "put":
        if "liquidity_sweep_bajista" in patron and tipo_mercado == "tendencia_alcista":
            peso *= PENALIZACION_MEDIA
            motivos.append("Penalización media: sweep bajista contra tendencia alcista.")

        if pa_direccion == "call":
            peso *= PENALIZACION_MEDIA
            motivos.append("Penalización media: PA contradice operación PUT.")

    # ==========================
    # REGLAS GENERALES DE RIESGO
    # ==========================
    if nivel_consenso == "bajo":
        peso *= PENALIZACION_SUAVE
        motivos.append("Penalización suave: consenso bajo.")

    if nivel_consenso == "medio":
        peso *= PENALIZACION_SUAVE
        motivos.append("Penalización suave: consenso medio.")

    if base_estrategia == "media":
        peso *= PENALIZACION_MEDIA
        motivos.append("Penalización media: base de estrategia MEDIA tuvo bajo rendimiento.")

    if "call_resistencia_sin_ruptura" in riesgos_base:
        peso *= PENALIZACION_MEDIA
        motivos.append("Penalización media: riesgo CALL resistencia sin ruptura.")

    # ==========================
    # BONOS
    # ==========================
    if tipo_mercado == "rango":
        peso *= BONO_SUAVE
        motivos.append("Bono suave: mercado en rango ha tenido buen rendimiento.")

    if tipo_mercado == "tendencia_bajista":
        peso *= BONO_SUAVE
        motivos.append("Bono suave: tendencia bajista ha tenido buen rendimiento.")

    if estado_tendencia == "bajista_normal":
        peso *= BONO_MEDIO
        motivos.append("Bono medio: BAJISTA_NORMAL ha sido contexto fuerte.")

    if pa_direccion == "put":
        peso *= BONO_MEDIO
        motivos.append("Bono medio: PA a favor de PUT ha sido fuerte.")

    if "rechazo_vendedor_confirmado" in pa_tipo:
        peso *= BONO_MEDIO
        motivos.append("Bono medio: rechazo vendedor confirmado.")

    if "impulso_bajista_fuerte" in pa_tipo:
        peso *= BONO_MEDIO
        motivos.append("Bono medio: impulso bajista fuerte.")

    if "pa_a_favor_put" in fortalezas_base:
        peso *= BONO_MEDIO
        motivos.append("Bono medio: fortaleza PA a favor PUT.")

    return limitar_peso(round(peso, 3)), motivos


def evaluar_decision(evidencia):
    """
    Motor central de decisión BootIQ.
    Combina inferencia histórica + reglas generales de robustez.
    """

    resultado_inferencia = inferir_confianza(evidencia)

    confianza_base = resultado_inferencia.get("confianza", 50.0)
    decision_inferencia = resultado_inferencia.get("decision", "NEUTRA")
    peso_inferencia = resultado_inferencia.get("peso_final", 1.0)

    peso_reglas, motivos_reglas = aplicar_reglas_generales(evidencia)
    riesgo_compuesto = evaluar_riesgo_compuesto(evidencia)
    peso_final = limitar_peso(round(peso_inferencia * peso_reglas, 3))
    confianza = round(max(0, min(100, 50.0 * peso_final)), 2)

    motivos = []
    motivos.extend(resultado_inferencia.get("motivos", []))
    motivos.extend(motivos_reglas)
    motivos.extend(riesgo_compuesto.get("motivos_riesgo", []))

    operar = True
    decision = "OPERAR"
    riesgo_nivel = riesgo_compuesto.get("riesgo_nivel", "BAJO")
    
    bloquear_por_riesgo_y_confianza = (
        riesgo_nivel == "EXTREMO"
        or (
            riesgo_nivel == "ALTO"
            and confianza < 50
        )
    )
    
    if (
        bloquear_por_riesgo_y_confianza
        or confianza <= UMBRAL_NO_OPERAR
        or decision_inferencia == "DEBIL"
    ):
        operar = False
        decision = "NO_OPERAR"
        motivos.append("Bloqueada por motor de decisión: baja confianza final.")

    elif confianza >= UMBRAL_OPERAR:
        operar = True
        decision = "OPERAR"
        motivos.append("Aprobada por motor de decisión: confianza suficiente.")

    else:
        operar = True
        decision = "OPERAR_OBSERVACION"
        motivos.append("Permitida en observación: confianza intermedia.")

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
        "riesgo_nivel": riesgo_compuesto.get("riesgo_nivel"),
        "riesgo_puntos": riesgo_compuesto.get("riesgo_puntos"),
        "bloquear_por_riesgo_y_confianza": bloquear_por_riesgo_y_confianza,
    }


def probar_motor_decision():
    ejemplos = [
        {
            "activo": "BIDU-OTC",
            "direccion": "put",
            "patron": "CHOCH bajista",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
            "pa_direccion": "PUT",
            "calidad_mercado": "NORMAL",
            "nivel_consenso": "PREMIUM",
            "base_estrategia": "FUERTE",
            "fortalezas_base": "PA_A_FAVOR_PUT|IMPULSO_BAJISTA_FUERTE",
            "riesgos_base": "",
        },
        {
            "activo": "COCOA-OTC",
            "direccion": "call",
            "patron": "pullback alcista a EMA",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
            "pa_tipo": "IMPULSO_ALCISTA_FUERTE",
            "pa_direccion": "CALL",
            "accion_precio": "CALL_RESISTENCIA_CERCA_SIN_RUPTURA",
            "calidad_mercado": "NORMAL",
            "nivel_consenso": "BAJO",
            "base_estrategia": "MEDIA",
            "fortalezas_base": "PA_A_FAVOR_CALL|IMPULSO_ALCISTA_FUERTE",
            "riesgos_base": "CALL_RESISTENCIA_SIN_RUPTURA",
        }
    ]

    print("\n===== PRUEBA MOTOR DECISIÓN BOOTIQ =====")

    for i, evidencia in enumerate(ejemplos, start=1):
        resultado = evaluar_decision(evidencia)

        print(f"\n--- EJEMPLO {i} ---")
        print("Patrón:", evidencia["patron"])
        print("Dirección:", evidencia["direccion"])
        print("Confianza:", resultado["confianza"])
        print("Decisión:", resultado["decision"])
        print("Operar:", resultado["operar"])
        print("Peso inferencia:", resultado["peso_inferencia"])
        print("Peso reglas:", resultado["peso_reglas"])
        print("Peso final:", resultado["peso_final"])

        for motivo in resultado["motivos"]:
            print("-", motivo)


if __name__ == "__main__":
    probar_motor_decision()