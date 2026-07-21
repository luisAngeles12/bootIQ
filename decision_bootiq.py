def _lista_segura(valor):
    return valor if isinstance(valor, list) else []


def _texto_lista(valor):
    if isinstance(valor, list):
        return " | ".join(str(x) for x in valor if str(x).strip())
    if valor is None:
        return ""
    return str(valor)

def validar_contrato_cerebro(decision_cerebro):
    """
    Verifica que la respuesta del Cerebro Único cumpla el contrato
    estructural y que sus campos sean coherentes entre sí.

    No modifica la decisión.
    No recalcula confianza.
    No crea bloqueos nuevos.
    """

    if not isinstance(decision_cerebro, dict):
        raise TypeError(
            "El Cerebro Único no devolvió un diccionario."
        )

    campos_obligatorios = (
        "decision",
        "operar",
        "confianza",
        "requiere_protocolo",
        "modo_ejecucion",
        "bloquear_por_riesgo",
    )

    campos_faltantes = [
        campo
        for campo in campos_obligatorios
        if campo not in decision_cerebro
    ]

    if campos_faltantes:
        raise KeyError(
            "Respuesta incompleta del Cerebro Único. "
            f"Faltan campos: {', '.join(campos_faltantes)}"
        )

    decision = str(
        decision_cerebro.get("decision", "")
    ).upper().strip()

    operar = bool(decision_cerebro.get("operar", False))

    requiere_protocolo = bool(
        decision_cerebro.get("requiere_protocolo", False)
    )

    modo_ejecucion = str(
        decision_cerebro.get("modo_ejecucion", "")
    ).upper().strip()

    contratos_validos = {
        "OPERAR": {
            "operar": True,
            "requiere_protocolo": False,
            "modo_ejecucion": "DIRECTA",
        },
        "OPERAR_CON_PROTOCOLO": {
            "operar": True,
            "requiere_protocolo": True,
            "modo_ejecucion": "PROTOCOLO",
        },
        "NO_OPERAR": {
            "operar": False,
            "requiere_protocolo": False,
            "modo_ejecucion": "BLOQUEADA",
        },
    }

    if decision not in contratos_validos:
        raise ValueError(
            f"Decisión oficial desconocida: {decision}"
        )

    esperado = contratos_validos[decision]

    if operar != esperado["operar"]:
        raise ValueError(
            f"Contrato incoherente: {decision} tiene "
            f"operar={operar}."
        )

    if (
        requiere_protocolo
        != esperado["requiere_protocolo"]
    ):
        raise ValueError(
            f"Contrato incoherente: {decision} tiene "
            f"requiere_protocolo={requiere_protocolo}."
        )

    if modo_ejecucion != esperado["modo_ejecucion"]:
        raise ValueError(
            f"Contrato incoherente: {decision} tiene "
            f"modo_ejecucion={modo_ejecucion}."
        )

    try:
        confianza = float(
            decision_cerebro.get("confianza", 0)
        )
    except (TypeError, ValueError):
        raise TypeError(
            "La confianza del Cerebro Único no es numérica."
        )

    if not 0 <= confianza <= 100:
        raise ValueError(
            f"Confianza fuera de rango: {confianza}"
        )

    return True
def crear_decision_bootiq(senal=None, ctx=None):
    """
    Contrato central de decisión BootIQ.

    Este módulo no decide, no recalcula confianza y no crea bloqueos.
    Solo organiza la información ya producida por el Cerebro Único.
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
            "tipo_mercado": senal.get(
                "tipo_mercado", ctx.get("tipo_mercado", "")
            ),
            "calidad_mercado": senal.get(
                "calidad_mercado", ctx.get("calidad_mercado", "")
            ),
            "score_mercado": senal.get(
                "score_mercado", ctx.get("score_mercado", 0)
            ),
            "estado_tendencia": senal.get(
                "estado_tendencia", ctx.get("estado_tendencia", "")
            ),
            "fuerza_tendencia": senal.get(
                "fuerza_tendencia", ctx.get("fuerza_tendencia", 0)
            ),
            "direccion_tendencia": senal.get(
                "direccion_tendencia", ctx.get("direccion_tendencia", "")
            ),
        },
        "price_action": {
            "accion_precio": senal.get(
                "accion_precio", ctx.get("accion_precio", "")
            ),
            "razon_accion_precio": senal.get(
                "razon_accion_precio", ctx.get("razon_accion_precio", "")
            ),
            "pa_tipo": senal.get("pa_tipo", ctx.get("pa_tipo", "")),
            "pa_direccion": senal.get(
                "pa_direccion", ctx.get("pa_direccion", "")
            ),
            "pa_fuerza": senal.get("pa_fuerza", ctx.get("pa_fuerza", 0)),
            "pa_razon": senal.get("pa_razon", ctx.get("pa_razon", "")),
        },
        "evidencias": {
            "price_action": senal.get(
                "pa_evidencias", ctx.get("pa_evidencias", [])
            ),
            "mercado": senal.get(
                "mercado_evidencias", ctx.get("mercado_evidencias", [])
            ),
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
            "razones_clasificador_setup": senal.get(
                "razones_clasificador_setup", ""
            ),
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
            "nivel_riesgo_protocolo": senal.get(
                "nivel_riesgo_protocolo", ""
            ),
            "razon_riesgo_protocolo": senal.get(
                "razon_riesgo_protocolo", ""
            ),
            "indice_confirmacion_ia": senal.get("indice_confirmacion_ia", 0),
            "nivel_confirmacion_ia": senal.get("nivel_confirmacion_ia", ""),
            "accion_confirmacion_ia": senal.get(
                "accion_confirmacion_ia", ""
            ),
            "razon_confirmacion_ia": senal.get(
                "razon_confirmacion_ia", ""
            ),
            "requiere_protocolo": senal.get(
                "cerebro_unico_requiere_protocolo", False
            ),
            "modo_ejecucion": senal.get(
                "cerebro_unico_modo_ejecucion", "BLOQUEADA"
            ),
        },
        "fase4": {
            "fase4_evaluada": senal.get("fase4_evaluada", False),
            "fase4_permitir_operacion": senal.get(
                "fase4_permitir_operacion", False
            ),
            "fase4_modo": senal.get("fase4_modo", ""),
            "fase4_confianza": senal.get("fase4_confianza", 50.0),
            "fase4_decision": senal.get("fase4_decision", ""),
            "fase4_debe_bloquear": senal.get(
                "fase4_debe_bloquear", False
            ),
            "fase4_motivo": senal.get("fase4_motivo", ""),
        },
        "decision_unificada": {
            "accion": senal.get("cerebro_unico_decision", ""),
            "accion_legacy": senal.get("decision_unificada_accion_legacy", ""),
            "score": senal.get("cerebro_unico_confianza", 0),
            "confianza": senal.get("cerebro_unico_confianza", 0),
            "razones": senal.get("decision_unificada_razones", ""),
            "advertencias": senal.get(
                "decision_unificada_advertencias", ""
            ),
            "bloqueos": senal.get("decision_unificada_bloqueos", ""),
            "operar": senal.get("cerebro_unico_operar", False),
            "requiere_protocolo": senal.get(
                "cerebro_unico_requiere_protocolo", False
            ),
            "modo_ejecucion": senal.get(
                "cerebro_unico_modo_ejecucion", "BLOQUEADA"
            ),
            "bloquear_por_riesgo": senal.get(
                "cerebro_unico_bloquear_por_riesgo", False
            ),
            "riesgo_nivel": senal.get("cerebro_unico_riesgo", ""),
            "riesgo_puntos": senal.get("cerebro_unico_riesgo_puntos", 0),
            "ajuste_ponderacion": senal.get("ajuste_ponderacion", 0),
            "motivos_ponderacion": senal.get("motivos_ponderacion", ""),
            "pesos_aplicados": senal.get("pesos_aplicados", ""),
            "confianza_final_cerebro": senal.get(
                "confianza_final_cerebro", 0
            ),
        },
        "riesgos": {
            "riesgos_base": senal.get("riesgos_base", ""),
            "riesgo_extra_setup": senal.get("riesgo_extra_setup", 0),
            "riesgo_protocolo": senal.get("riesgo_protocolo", 0),
            "nivel_riesgo_protocolo": senal.get(
                "nivel_riesgo_protocolo", ""
            ),
            "razon_riesgo_protocolo": senal.get(
                "razon_riesgo_protocolo", ""
            ),
            "riesgo_nivel_cerebro": senal.get("cerebro_unico_riesgo", ""),
            "riesgo_puntos_cerebro": senal.get(
                "cerebro_unico_riesgo_puntos", 0
            ),
            "bloquear_por_riesgo": senal.get(
                "cerebro_unico_bloquear_por_riesgo", False
            ),
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
            "confianza_cerebro": senal.get("cerebro_unico_confianza", 0),
        },
        "debug": {
            "razon": senal.get("razon", ""),
            "razones_setup": senal.get("razones_setup", ""),
            "razones_consenso": senal.get("razones_consenso", ""),
            "razon_confirmacion_ia": senal.get(
                "razon_confirmacion_ia", ""
            ),
            "razon_accion_precio": senal.get(
                "razon_accion_precio", ""
            ),
            "razon_ruptura": senal.get("razon_ruptura", ""),
            "cerebro_unico_motivos": senal.get("cerebro_unico_motivos", ""),
        },
        "resultado": {
            "estado_operacion": senal.get("estado_operacion", ""),
            "motivo_ejecucion": senal.get("motivo_ejecucion", ""),
            "resultado": senal.get("resultado", ""),
            "resultado_hipotetico": senal.get("resultado_hipotetico", ""),
        },
    }


def aplanar_decision_bootiq(decision):
    """
    Convierte el contrato BootIQ en columnas planas para CSV.
    No altera la decisión.
    """

    plano = {}

    for seccion, datos in (decision or {}).items():
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
    Construye evidencia, llama una sola vez al Cerebro Único y sincroniza
    su resultado con la señal.

    No ejecuta operaciones, no aplica protocolos, no recalcula confianza y
    no toma una decisión alternativa.
    """

    senal = senal if isinstance(senal, dict) else {}
    ctx = ctx if isinstance(ctx, dict) else {}

    try:
        from constructor_evidencia import construir_evidencia_operacion
        from motor_decision import evaluar_decision_cerebro_unico

        evidencia = construir_evidencia_operacion(senal, ctx)
        decision_cerebro = evaluar_decision_cerebro_unico(evidencia)

        validar_contrato_cerebro(decision_cerebro)
        
        decision_oficial = str(
            decision_cerebro["decision"]
        ).upper().strip()
        decision_legacy = decision_cerebro.get(
            "decision_legacy", decision_oficial
        )
        operar = bool(decision_cerebro["operar"])
        confianza = decision_cerebro["confianza"]
        
        requiere_protocolo = bool(
            decision_cerebro["requiere_protocolo"]
        )
        
        modo_ejecucion = decision_cerebro["modo_ejecucion"]
        
        bloquear_por_riesgo = bool(
            decision_cerebro["bloquear_por_riesgo"]
        )
        riesgo_nivel = decision_cerebro.get(
            "riesgo_nivel",
            "BAJO",
        )
        
        riesgo_puntos = decision_cerebro.get(
            "riesgo_puntos",
            0,
        )
        motivos = _lista_segura(decision_cerebro.get("motivos", []))
        motivos_texto = _texto_lista(motivos)

        riesgo_compuesto = decision_cerebro.get("riesgo_compuesto", {})
        if not isinstance(riesgo_compuesto, dict):
            riesgo_compuesto = {}

        motivos_riesgo = _texto_lista(
            riesgo_compuesto.get("motivos_riesgo", [])
        )

        ponderacion = decision_cerebro.get("ponderacion_estadistica", {})
        if not isinstance(ponderacion, dict):
            ponderacion = {}

        motivos_ponderacion = _texto_lista(
            ponderacion.get("motivos_ponderacion", [])
        )
        pesos_aplicados = _texto_lista(
            ponderacion.get("pesos_aplicados", [])
        )

        # Salida oficial del Cerebro Único.
        senal["cerebro_unico_decision"] = decision_oficial
        senal["cerebro_unico_decision_legacy"] = decision_legacy
        senal["cerebro_unico_operar"] = operar
        senal["cerebro_unico_confianza"] = confianza
        senal["cerebro_unico_requiere_protocolo"] = requiere_protocolo
        senal["cerebro_unico_modo_ejecucion"] = modo_ejecucion
        senal["cerebro_unico_riesgo"] = riesgo_nivel
        senal["cerebro_unico_riesgo_puntos"] = riesgo_puntos
        senal["cerebro_unico_bloquear_por_riesgo"] = bloquear_por_riesgo
        senal["cerebro_unico_motivos"] = motivos_texto

        # Alias de Fase 4: no representan una segunda decisión.
        senal["fase4_evaluada"] = True
        senal["fase4_confianza"] = confianza
        senal["fase4_decision"] = decision_legacy
        senal["fase4_permitir_operacion"] = operar
        senal["fase4_debe_bloquear"] = not operar
        senal["fase4_modo"] = modo_ejecucion
        senal["fase4_motivo"] = motivos_texto

        # Compatibilidad legacy: todos los campos reflejan el mismo resultado.
        senal["decision_unificada_accion"] = decision_oficial
        senal["decision_unificada_accion_legacy"] = decision_legacy
        senal["decision_unificada_score"] = confianza
        senal["decision_unificada_confianza"] = confianza
        senal["decision_unificada_razones"] = motivos_texto
        senal["decision_unificada_advertencias"] = ""
        senal["decision_unificada_bloqueos"] = (
            motivos_riesgo if not operar else ""
        )

        senal["ajuste_ponderacion"] = decision_cerebro.get(
            "ajuste_ponderacion", 0
        )
        senal["motivos_ponderacion"] = motivos_ponderacion
        senal["pesos_aplicados"] = pesos_aplicados
        senal["confianza_final_cerebro"] = confianza

        senal["pa_evidencias"] = decision_cerebro.get(
            "pa_evidencias",
            evidencia.get(
                "pa_evidencias",
                senal.get("pa_evidencias", []),
            ),
        )
        
        senal["mercado_evidencias"] = decision_cerebro.get(
            "mercado_evidencias",
            evidencia.get(
                "mercado_evidencias",
                senal.get("mercado_evidencias", []),
            ),
        )
        senal["evidencia_operacion"] = evidencia

        # =====================================================
        # Sincronizar evidencias oficiales del contrato BootIQ
        # =====================================================
        
        senal["pa_evidencias"] = _lista_segura(
            evidencia.get(
                "pa_evidencias",
                senal.get("pa_evidencias", []),
            )
        )
        
        senal["mercado_evidencias"] = _lista_segura(
            evidencia.get(
                "mercado_evidencias",
                senal.get("mercado_evidencias", []),
            )
        )
        
        senal["setup_evidencias"] = _lista_segura(
            evidencia.get(
                "setup_evidencias",
                senal.get("setup_evidencias", []),
            )
        )
        
        senal["riesgo_evidencias"] = _lista_segura(
            evidencia.get(
                "riesgo_evidencias",
                senal.get("riesgo_evidencias", []),
            )
        )
        
        senal["historial_evidencias"] = _lista_segura(
            evidencia.get(
                "historial_evidencias",
                senal.get("historial_evidencias", []),
            )
        )
        
        decision = crear_decision_bootiq(senal, ctx)
        return {
            "permitida": operar,
            "requiere_protocolo": requiere_protocolo,
            "modo_ejecucion": modo_ejecucion,
            "bloquear_por_riesgo": bloquear_por_riesgo,
            "senal": senal,
            "decision": decision,
            "resultado": decision_cerebro,
            "razon": "decisión aplicada por Cerebro Único",
        }

    except Exception as exc:
        mensaje_error = f"error decision_bootiq: {exc}"

        senal["cerebro_unico_decision"] = "ERROR"
        senal["cerebro_unico_operar"] = False
        senal["cerebro_unico_requiere_protocolo"] = False
        senal["cerebro_unico_modo_ejecucion"] = "BLOQUEADA"
        senal["cerebro_unico_bloquear_por_riesgo"] = True
        senal["cerebro_unico_motivos"] = mensaje_error

        senal["fase4_evaluada"] = True
        senal["fase4_permitir_operacion"] = False
        senal["fase4_debe_bloquear"] = True
        senal["fase4_decision"] = "ERROR"
        senal["fase4_modo"] = "BLOQUEADA"
        senal["fase4_motivo"] = mensaje_error

        senal["decision_unificada_accion"] = "ERROR"
        senal["decision_unificada_accion_legacy"] = "ERROR"
        senal["decision_unificada_score"] = 0
        senal["decision_unificada_confianza"] = 0
        senal["decision_unificada_razones"] = ""
        senal["decision_unificada_advertencias"] = mensaje_error
        senal["decision_unificada_bloqueos"] = "error"

        return {
            "permitida": False,
            "requiere_protocolo": False,
            "modo_ejecucion": "BLOQUEADA",
            "bloquear_por_riesgo": True,
            "senal": senal,
            "decision": crear_decision_bootiq(senal, ctx),
            "resultado": {},
            "razon": f"error aplicando DecisionBootIQ: {exc}",
        }