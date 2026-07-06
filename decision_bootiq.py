def crear_decision_bootiq(senal=None, ctx=None):
    """
    Contrato central de decisión BootIQ.

    Fase 6:
    - No decide.
    - No bloquea.
    - No cambia reglas de trading.
    - Solo organiza la información en secciones.
    """

    senal = senal or {}
    ctx = ctx or {}

    return {
        "identidad": {
            "activo": senal.get("activo", ctx.get("activo", "")),
            "tipo": senal.get("tipo", ""),
            "direccion": senal.get("direccion", ""),
            "patron": senal.get("patron", ""),
            "fecha": senal.get("fecha", ""),
        },

        "estrategia": {
            "puntaje": senal.get("puntaje", 0),
            "prioridad": senal.get("prioridad", 0),
            "score_final": senal.get("score_final", 0),
            "calidad": senal.get("calidad", ""),
            "razon": senal.get("razon", ""),
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
            "razon_accion_precio": senal.get("razon_accion_precio", ctx.get("razon_accion_precio", "")),
            "pa_tipo": senal.get("pa_tipo", ctx.get("pa_tipo", "")),
            "pa_direccion": senal.get("pa_direccion", ctx.get("pa_direccion", "")),
            "pa_fuerza": senal.get("pa_fuerza", ctx.get("pa_fuerza", 0)),
            "pa_razon": senal.get("pa_razon", ctx.get("pa_razon", "")),
        },
        "evidencias": {
            "price_action": senal.get("pa_evidencias", ctx.get("pa_evidencias", [])),
            "mercado": senal.get("mercado_evidencias", ctx.get("mercado_evidencias", [])),
            "setup": senal.get("setup_evidencias", []),
            "riesgo": senal.get("riesgo_evidencias", []),
            "historial": senal.get("historial_evidencias", []),
        },
        "setup": {
            "tipo_setup": senal.get("tipo_setup", ""),
            "calidad_setup": senal.get("calidad_setup", ""),
            "modo_entrada_setup": senal.get("modo_entrada_setup", ""),
            "puntaje_extra_setup": senal.get("puntaje_extra_setup", 0),
            "riesgo_extra_setup": senal.get("riesgo_extra_setup", 0),
            "balance_setup": senal.get("balance_setup", 0),
            "familia_setup": senal.get("familia_setup", ""),
            "subtipo_setup": senal.get("subtipo_setup", ""),
            "nivel_setup": senal.get("nivel_setup", ""),
            "estado_setup": senal.get("estado_setup", ""),
            "confianza_setup": senal.get("confianza_setup", 0),
            "razones_setup": senal.get("razones_setup", ""),
            "razones_clasificador_setup": senal.get("razones_clasificador_setup", ""),
        },

        "consenso": {
            "consenso": senal.get("consenso", 0),
            "nivel_consenso": senal.get("nivel_consenso", ""),
            "ajuste_consenso": senal.get("ajuste_consenso", 0),
            "razones_consenso": senal.get("razones_consenso", ""),
        },

        "protocolo": {
            "protocolo_sugerido": senal.get("protocolo_sugerido", ""),
            "riesgo_protocolo": senal.get("riesgo_protocolo", 0),
            "nivel_riesgo_protocolo": senal.get("nivel_riesgo_protocolo", ""),
            "razon_riesgo_protocolo": senal.get("razon_riesgo_protocolo", ""),
            "indice_confirmacion_ia": senal.get("indice_confirmacion_ia", 0),
            "nivel_confirmacion_ia": senal.get("nivel_confirmacion_ia", ""),
            "accion_confirmacion_ia": senal.get("accion_confirmacion_ia", ""),
            "razon_confirmacion_ia": senal.get("razon_confirmacion_ia", ""),
        },

        "fase4": {
            "fase4_evaluada": senal.get("fase4_evaluada", False),
            "fase4_permitir_operacion": senal.get("fase4_permitir_operacion", True),
            "fase4_modo": senal.get("fase4_modo", ""),
            "fase4_confianza": senal.get("fase4_confianza", 50.0),
            "fase4_decision": senal.get("fase4_decision", ""),
            "fase4_debe_bloquear": senal.get("fase4_debe_bloquear", False),
            "fase4_motivo": senal.get("fase4_motivo", ""),
        },

        "decision_unificada": {
            "accion": senal.get("decision_unificada_accion", ""),
            "score": senal.get("decision_unificada_score", 0),
            "confianza": senal.get("decision_unificada_confianza", ""),
            "razones": senal.get("decision_unificada_razones", ""),
            "advertencias": senal.get("decision_unificada_advertencias", ""),
            "bloqueos": senal.get("decision_unificada_bloqueos", ""),
        },
        "riesgos": {
            "riesgos_base": senal.get("riesgos_base", ""),
            "riesgo_extra_setup": senal.get("riesgo_extra_setup", 0),
            "riesgo_protocolo": senal.get("riesgo_protocolo", 0),
            "nivel_riesgo_protocolo": senal.get("nivel_riesgo_protocolo", ""),
            "razon_riesgo_protocolo": senal.get("razon_riesgo_protocolo", ""),
        },

        "fortalezas": {
            "fortalezas_base": senal.get("fortalezas_base", ""),
            "a_favor_tendencia": senal.get("a_favor_tendencia", False),
            "balance_setup": senal.get("balance_setup", 0),
            "confianza_setup": senal.get("confianza_setup", 0),
        },

        "historial": {
            "fase4_confianza": senal.get("fase4_confianza", 50),
            "fase4_decision": senal.get("fase4_decision", ""),
            "fase4_motivo": senal.get("fase4_motivo", ""),
        },

        "metricas": {
            "puntaje": senal.get("puntaje", 0),
            "prioridad": senal.get("prioridad", 0),
            "score_final": senal.get("score_final", 0),
            "consenso": senal.get("consenso", 0),
            "indice_confirmacion_ia": senal.get("indice_confirmacion_ia", 0),
            "score_mercado": senal.get("score_mercado", 0),
        },

        "debug": {
            "razon": senal.get("razon", ""),
            "razones_setup": senal.get("razones_setup", ""),
            "razones_consenso": senal.get("razones_consenso", ""),
            "razon_confirmacion_ia": senal.get("razon_confirmacion_ia", ""),
            "razon_accion_precio": senal.get("razon_accion_precio", ""),
            "razon_ruptura": senal.get("razon_ruptura", ""),
        },
        "resultado": {
            "estado_operacion": senal.get("estado_operacion", ""),
            "motivo_ejecucion": senal.get("motivo_ejecucion", ""),
            "resultado": senal.get("resultado", ""),
            "resultado_hipotetico": senal.get("resultado_hipotetico", ""),
        }
    }


def aplanar_decision_bootiq(decision):
    """
    Convierte el contrato BootIQ en columnas planas para CSV.
    No altera la decisión.
    """

    plano = {}

    for seccion, datos in decision.items():
        if not isinstance(datos, dict):
            plano[seccion] = datos
            continue

        for clave, valor in datos.items():
            if isinstance(valor, list):
                plano[f"bootiq_{seccion}_{clave}"] = " | ".join(
                    str(x.get("tipo", x)) if isinstance(x, dict) else str(x)
                    for x in valor
                )
            else:
                plano[f"bootiq_{seccion}_{clave}"] = valor
    return plano
def aplicar_decision_unificada_a_senal(senal, ctx=None):
    """
    Evalúa una señal candidata usando el contrato central BootIQ.

    No ejecuta operación.
    No toca broker.
    No cambia protocolo.
    Solo centraliza la decisión y escribe el resultado en la señal.
    """

    try:
        from motor_consenso import aplicar_consenso_decision
        from motor_setup import aplicar_setup_decision
        from motor_riesgo import aplicar_riesgo_decision
        from motor_confirmacion import aplicar_confirmacion_decision
        from motor_decision_unificado import evaluar_decision_bootiq

        ctx = ctx or {}

        decision = crear_decision_bootiq(senal, ctx)

        decision = aplicar_consenso_decision(decision)
        decision = aplicar_setup_decision(decision)
        decision = aplicar_riesgo_decision(decision)
        decision = aplicar_confirmacion_decision(decision)

        resultado = evaluar_decision_bootiq(decision)

        senal["decision_unificada_accion"] = resultado.get("accion", "")
        senal["decision_unificada_score"] = resultado.get("score", 0)
        senal["decision_unificada_confianza"] = resultado.get("confianza", "")
        senal["decision_unificada_razones"] = " | ".join(resultado.get("razones", []))
        senal["decision_unificada_advertencias"] = " | ".join(resultado.get("advertencias", []))
        senal["decision_unificada_bloqueos"] = " | ".join(resultado.get("bloqueos", []))

        return {
            "permitida": resultado.get("accion") in ["OPERAR", "ESPERAR"],
            "senal": senal,
            "decision": decision,
            "resultado": resultado,
            "razon": "decisión BootIQ aplicada"
        }

    except Exception as e:
        senal["decision_unificada_accion"] = "ERROR"
        senal["decision_unificada_score"] = 0
        senal["decision_unificada_confianza"] = "ERROR"
        senal["decision_unificada_razones"] = ""
        senal["decision_unificada_advertencias"] = "error decision_bootiq: " + str(e)
        senal["decision_unificada_bloqueos"] = "error"

        return {
            "permitida": False,
            "senal": senal,
            "decision": {},
            "resultado": {},
            "razon": "error aplicando DecisionBootIQ: " + str(e)
        }