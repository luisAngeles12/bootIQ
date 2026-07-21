from motor_inferencia import inferir_confianza
from detector_riesgo_compuesto import evaluar_riesgo_compuesto
from motor_aprendizaje_historico import evaluar_aprendizaje_historico
from motor_ponderacion import calcular_ponderacion_estadistica


UMBRAL_OPERAR_DIRECTO = 65.0
UMBRAL_OPERAR_NORMAL = 50.0
UMBRAL_PROTOCOLO_ESTRICTO = 38.0

# ============================================================
# UMBRALES OFICIALES DEL CEREBRO ÚNICO
# ============================================================

UMBRAL_CEREBRO_OPERAR = 62.0
UMBRAL_CEREBRO_PROTOCOLO = 55.0

PESO_MINIMO_DECISION = 0.55
PESO_MAXIMO_DECISION = 1.30


def _txt(v):
    return str(v or "").lower().strip()


def _num(v, default=0.0):
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
        return float(default)


# ============================================================
# ESPECIALISTAS INTERNOS DEL CEREBRO ÚNICO
# ============================================================

def evaluar_price_action_decision(evidencia):
    """
    Evalúa únicamente las evidencias de Price Action.

    No decide la operación.
    No bloquea.
    No modifica la evidencia.
    Solo devuelve ajuste y motivos.
    """

    direccion = _txt(evidencia.get("direccion", ""))
    pa_evidencias = evidencia.get("pa_evidencias", [])

    if not isinstance(pa_evidencias, list):
        pa_evidencias = []

    ajuste_evidencias = 0.0
    motivos = []
    evidencias_validas = 0

    for ev in pa_evidencias:
        if not isinstance(ev, dict):
            continue

        evidencias_validas += 1

        tipo = _txt(ev.get("tipo", ""))
        direccion_ev = _txt(ev.get("direccion", ""))
        peso = _num(ev.get("peso", 0))
        fuerza = _num(ev.get("fuerza", 0))
        confirmada = bool(ev.get("confirmada", False))

        if tipo == "contradiccion_pa":
            ajuste_evidencias -= 6
            motivos.append("PA: contradicción interna detectada.")
            continue

        if direccion_ev not in ["call", "put"]:
            continue

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

    return {
        "ajuste": round(ajuste_evidencias, 2),
        "motivos": motivos,
        "total_evidencias": len(pa_evidencias),
        "evidencias_validas": evidencias_validas,
    }


def evaluar_mercado_decision(evidencia):
    """
    Especialista de contexto de mercado.

    No decide la operación.
    No bloquea.
    No modifica la evidencia.

    Evalúa el régimen y la calidad general del mercado.
    Price Action y estrategia son responsables de evaluar
    la dirección concreta de la operación.
    """

    mercado_evidencias = evidencia.get(
        "mercado_evidencias",
        [],
    )

    if not isinstance(mercado_evidencias, list):
        mercado_evidencias = []

    tipos_mercado = set()
    motivos = []
    evidencias_validas = 0

    for ev in mercado_evidencias:
        if not isinstance(ev, dict):
            continue

        evidencias_validas += 1

        tipo = _txt(
            ev.get("tipo", "")
        )

        if tipo:
            tipos_mercado.add(tipo)

    ajuste = 0.0

    # ========================================================
    # TIPO PRINCIPAL DE MERCADO
    # ========================================================

    if "mercado_rango" in tipos_mercado:
        ajuste += 3

        motivos.append(
            "Mercado: rango con rendimiento histórico favorable."
        )

    elif "mercado_normal" in tipos_mercado:
        motivos.append(
            "Mercado: calidad normal operable, sin bono automático."
        )

    # ========================================================
    # CALIDAD
    # ========================================================

    if "mercado_limpio" in tipos_mercado:
        ajuste -= 2

        motivos.append(
            "Mercado: clasificación LIMPIO no mostró ventaja histórica."
        )

    if "mercado_sucio" in tipos_mercado:
        ajuste -= 4

        motivos.append(
            "Mercado: contexto sucio o caótico."
        )

    # ========================================================
    # ESTADO DE TENDENCIA
    # ========================================================

    if (
        "tendencia_alcista" in tipos_mercado
        and "tendencia_fuerte" in tipos_mercado
    ):
        ajuste -= 3

        motivos.append(
            "Mercado: tendencia alcista fuerte históricamente débil."
        )

    if "tendencia_agotada" in tipos_mercado:
        ajuste -= 3

        motivos.append(
            "Mercado: tendencia agotada."
        )

    # TENDENCIA_DEBIL queda como diagnóstico.
    # El backtest no justificó una penalización automática.

    if "tendencia_debil" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia débil sin penalización automática."
        )

    # TENDENCIA_LIMPIA queda como diagnóstico.
    # No se premia automáticamente.

    if "tendencia_limpia" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia limpia sin bono automático."
        )

    # ========================================================
    # RÉGIMEN Y RIESGO
    # ========================================================

    if "expansion_peligrosa" in tipos_mercado:
        ajuste -= 4

        motivos.append(
            "Mercado: expansión peligrosa."
        )

    if "rango_sucio" in tipos_mercado:
        ajuste -= 4

        motivos.append(
            "Mercado: rango sucio."
        )

    if "riesgo_mercado_alto" in tipos_mercado:
        ajuste -= 3

        motivos.append(
            "Mercado: riesgo general alto."
        )

    # ========================================================
    # SCORE DE MERCADO
    # Valores deliberadamente moderados.
    # ========================================================

    if "score_mercado_alto" in tipos_mercado:
        motivos.append(
            "Mercado: score alto sin bono automático."
        )

    if "score_mercado_bajo" in tipos_mercado:
        ajuste -= 2

        motivos.append(
            "Mercado: score bajo."
        )

    return {
        "ajuste": round(ajuste, 2),
        "motivos": motivos,
        "tipos_mercado": sorted(tipos_mercado),
        "total_evidencias": len(mercado_evidencias),
        "evidencias_validas": evidencias_validas,
    }
def evaluar_estrategia_decision(evidencia):
    """
    Evalúa la estrategia, el setup, las zonas y los riesgos estructurales.

    No decide la operación.
    No bloquea.
    No modifica la evidencia.
    Solo devuelve ajuste, motivos y familias detectadas.
    """

    patron = _txt(evidencia.get("patron", ""))
    tipo_setup = _txt(evidencia.get("tipo_setup", ""))
    subtipo_setup = _txt(evidencia.get("subtipo_setup", ""))
    accion_precio = _txt(evidencia.get("accion_precio", ""))
    riesgos_base = _txt(evidencia.get("riesgos_base", ""))
    fortalezas_base = _txt(evidencia.get("fortalezas_base", ""))

    ajuste = 0.0
    motivos = []
    familias_detectadas = []

    es_choch = (
        "choch" in patron
        or "choch" in tipo_setup
        or "choch" in subtipo_setup
    )

    if es_choch:
        familias_detectadas.append("CHOCH")

        if "choch_con_pa_a_favor" in subtipo_setup:
             motivos.append(
                 "Estrategia: CHOCH con PA a favor, sin ajuste automático."
             )
        if "choch_con_tendencia_debil" in riesgos_base:
            ajuste -= 5
            motivos.append("Estrategia: CHOCH con tendencia débil.")

        if "choch_sin_pa_valido" in riesgos_base:
            ajuste -= 4
            motivos.append("Estrategia: CHOCH sin PA válido.")

    es_pullback = (
        "pullback" in patron
        or "pullback" in tipo_setup
        or "pullback" in subtipo_setup
    )

    if es_pullback:
        familias_detectadas.append("PULLBACK")

        if "pullback_tendencia_insuficiente" in riesgos_base:
            ajuste -= 1
            motivos.append(
                "Estrategia: pullback con tendencia insuficiente; "
                "penalización estadística leve."
            )
        if "pullback_con_pa_y_tendencia" in fortalezas_base:
            ajuste += 1
            motivos.append(
                "Estrategia: pullback con PA y tendencia; "
                "bono moderado por muestra limitada."
            )

        if "pullback_balance_positivo" in subtipo_setup:
            motivos.append(
                "Estrategia: pullback con balance positivo, "
                "sin bono adicional para evitar duplicación."
            )

    es_sweep = (
        "sweep" in patron
        or "sweep" in tipo_setup
        or "sweep" in subtipo_setup
        or "liquidity" in patron
    )

    if es_sweep:
        familias_detectadas.append("SWEEP")

        if "sweep_sin_confirmacion_pa" in riesgos_base:
            motivos.append(
                "Estrategia: sweep sin confirmación PA, "
                "sin penalización automática."
            )

        if "sweep_con_confirmacion_pa_debil" in riesgos_base:
            motivos.append(
                "Estrategia: sweep con confirmación PA débil, "
                "sin penalización automática."
            )

        if "sweep_ruptura_confirmable" in subtipo_setup:
            motivos.append(
                "Estrategia: sweep con ruptura confirmable, "
                "sin bono automático."
            )
    if (
        "call_resistencia_sin_ruptura" in riesgos_base
        or "call_resistencia" in accion_precio
    ):
        motivos.append(
            "Estrategia: CALL cerca de resistencia sin ruptura, "
            "sin penalización automática."
        )

    if (
        "put_soporte_sin_ruptura" in riesgos_base
        or "put_soporte" in accion_precio
    ):
        motivos.append(
            "Estrategia: PUT cerca de soporte sin ruptura, "
            "sin penalización automática."
        )

    if (
        "reaccion_confirmada" in fortalezas_base
        or "zona_rechazo_confirmado" in subtipo_setup
    ):
        motivos.append(
            "Estrategia: reacción/zona confirmada, "
            "sin bono automático."
        )
    if "continuacion_tendencia_insuficiente" in riesgos_base:
        motivos.append(
            "Estrategia: continuación con tendencia insuficiente, "
            "sin penalización automática."
        )

    return {
        "ajuste": round(ajuste, 2),
        "motivos": motivos,
        "familias_detectadas": familias_detectadas,
    }


def calcular_confianza_cerebro(
    confianza_base,
    ajuste_aprendizaje,
    ajuste_evidencias,
    ajuste_ponderacion,
):
    """
    Calcula la confianza final del Cerebro Único y conserva su desglose.
    """

    confianza_base = _num(confianza_base, 50.0)
    ajuste_aprendizaje = _num(ajuste_aprendizaje, 0.0)
    ajuste_evidencias = _num(ajuste_evidencias, 0.0)
    ajuste_ponderacion = _num(ajuste_ponderacion, 0.0)

    confianza_antes_ponderacion = (
        confianza_base
        + ajuste_aprendizaje
        + ajuste_evidencias
    )

    confianza_antes_ponderacion = round(
        max(0, min(100, confianza_antes_ponderacion)),
        2,
    )

    confianza_final = confianza_antes_ponderacion + ajuste_ponderacion
    confianza_final = round(max(0, min(100, confianza_final)), 2)

    return {
        "confianza": confianza_final,
        "confianza_base": round(confianza_base, 2),
        "ajuste_aprendizaje": round(ajuste_aprendizaje, 2),
        "ajuste_evidencias": round(ajuste_evidencias, 2),
        "ajuste_ponderacion": round(ajuste_ponderacion, 2),
        "confianza_antes_ponderacion": confianza_antes_ponderacion,
    }


def clasificar_decision_final(confianza, riesgo_nivel):
    """
    Traduce la confianza y el riesgo final a la decisión
    operativa oficial del Cerebro Único.

    Esta es la única función que define:
    - si se permite operar;
    - si se requiere protocolo;
    - el modo de ejecución;
    - si existe bloqueo por riesgo.

    Los módulos externos solamente informan.
    No ejecuta protocolos ni operaciones.
    """

    confianza = _num(confianza, 0.0)

    riesgo_nivel = str(
        riesgo_nivel or "BAJO"
    ).upper().strip()

    # ========================================================
    # BLOQUEO OFICIAL POR RIESGO EXTREMO
    # ========================================================
    # detector_riesgo_compuesto.py solamente calcula el riesgo.
    # La decisión de bloquear pertenece al Cerebro Único.
    # ========================================================

    if riesgo_nivel == "EXTREMO":
        return {
            "decision": "NO_OPERAR",
            "decision_legacy": "NO_OPERAR",
            "operar": False,
            "requiere_protocolo": False,
            "modo_ejecucion": "BLOQUEADA",
            "bloquear_por_riesgo": True,
            "motivo": (
                "Cerebro único: operación rechazada "
                "por riesgo extremo."
            ),
        }

    # ========================================================
    # CONFIANZA ALTA
    # ========================================================

    if confianza >= UMBRAL_CEREBRO_OPERAR:
        return {
            "decision": "OPERAR",
            "decision_legacy": "OPERAR_DIRECTO_O_CONFIRMADO",
            "operar": True,
            "requiere_protocolo": False,
            "modo_ejecucion": "DIRECTA",
            "bloquear_por_riesgo": False,
            "motivo": (
                "Cerebro único: confianza alta; "
                "entrada directa autorizada."
            ),
        }

    # ========================================================
    # CONFIANZA INTERMEDIA
    # ========================================================

    if confianza >= UMBRAL_CEREBRO_PROTOCOLO:
        return {
            "decision": "OPERAR_CON_PROTOCOLO",
            "decision_legacy": "OPERAR_CON_CONFIRMACION",
            "operar": True,
            "requiere_protocolo": True,
            "modo_ejecucion": "PROTOCOLO",
            "bloquear_por_riesgo": False,
            "motivo": (
                "Cerebro único: confianza intermedia; "
                "requiere confirmación del protocolo."
            ),
        }

    # ========================================================
    # CONFIANZA INSUFICIENTE
    # ========================================================

    return {
        "decision": "NO_OPERAR",
        "decision_legacy": "NO_OPERAR",
        "operar": False,
        "requiere_protocolo": False,
        "modo_ejecucion": "BLOQUEADA",
        "bloquear_por_riesgo": False,
        "motivo": (
            "Cerebro único: confianza inferior "
            "al mínimo operativo."
        ),
    }
def limitar_peso(peso):
    return max(PESO_MINIMO_DECISION, min(PESO_MAXIMO_DECISION, peso))


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

    if (
        "sin_contexto_claro" in riesgos_base
        or pa_tipo == "sin_contexto_claro"
    ):
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
    confianza_setup = _num(evidencia.get("confianza_setup", 50), 50)
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
        return (
            True,
            "Bloqueo duro: impulso alcista débil histórico + consenso bajo.",
        )

    if (
        protocolo_sugerido == "protocolo_ruptura_resistencia"
        and estado_setup == "pendiente_confirmacion"
        and nivel_setup in ["medio_bajo", "bajo"]
        and confianza_setup < 50
        and nivel_consenso in ["muy_bajo", "bajo"]
    ):
        return (
            True,
            "Bloqueo duro: ruptura de resistencia pendiente + "
            "setup débil + consenso bajo.",
        )

    if (
        direccion == "call"
        and "call_resistencia_cerca_sin_ruptura" in accion_precio
        and nivel_consenso in ["muy_bajo", "bajo"]
        and confianza_setup < 52
    ):
        return (
            True,
            "Bloqueo duro: CALL contra resistencia sin ruptura + "
            "consenso bajo.",
        )

    if (
        "call_resistencia_sin_ruptura" in riesgos_base
        and "pa_a_favor_call" not in fortalezas_base
        and pa_tipo
        not in ["impulso_alcista_fuerte", "rechazo_comprador_confirmado"]
        and nivel_consenso in ["muy_bajo", "bajo"]
    ):
        return (
            True,
            "Bloqueo duro: resistencia sin ruptura sin PA alcista ni consenso.",
        )

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

    if (
        confianza >= UMBRAL_OPERAR_DIRECTO
        and riesgo_nivel in ["BAJO", "MEDIO"]
    ):
        return "DIRECTA_PERMITIDA"

    if confianza >= UMBRAL_OPERAR_NORMAL:
        return "ENTRADA_CONFIRMADA"

    return "PROTOCOLO_ESTRICTO"


def evaluar_decision(evidencia):
    """
    Ruta legacy conservada temporalmente para validador_fase4.py.
    """

    resultado_inferencia = inferir_confianza(evidencia)

    confianza_base = resultado_inferencia.get("confianza", 50.0)
    decision_inferencia = resultado_inferencia.get("decision", "NEUTRA")
    peso_inferencia = resultado_inferencia.get("peso_final", 1.0)

    peso_reglas, motivos_reglas = aplicar_reglas_generales(evidencia)
    riesgo_compuesto = evaluar_riesgo_compuesto(evidencia)
    aprendizaje = evaluar_aprendizaje_historico(evidencia)

    peso_final = limitar_peso(round(peso_inferencia * peso_reglas, 3))

    confianza = round(
        max(0, min(100, confianza_base * peso_final)),
        2,
    )

    confianza += aprendizaje.get("ajuste_confianza_aprendizaje", 0)
    confianza = round(max(0, min(100, confianza)), 2)

    riesgo_nivel = riesgo_compuesto.get("riesgo_nivel", "BAJO")
    riesgo_puntos = riesgo_compuesto.get("riesgo_puntos", 0)
    pa_evidencias = evidencia.get("pa_evidencias", [])

    if not isinstance(pa_evidencias, list):
        pa_evidencias = []

    ajuste_evidencias = 0.0
    motivos_evidencias = []
    direccion = _txt(evidencia.get("direccion", ""))

    motivos = []
    motivos.extend(resultado_inferencia.get("motivos", []))
    motivos.extend(motivos_reglas)
    motivos.extend(riesgo_compuesto.get("motivos_riesgo", []))

    motivo_aprendizaje = aprendizaje.get("motivo_aprendizaje", "")
    if motivo_aprendizaje:
        motivos.append(motivo_aprendizaje)

    for ev in pa_evidencias:
        if not isinstance(ev, dict):
            continue

        tipo = _txt(ev.get("tipo", ""))
        direccion_ev = _txt(ev.get("direccion", ""))
        peso = _num(ev.get("peso", 0))
        fuerza = _num(ev.get("fuerza", 0))

        if direccion_ev == direccion and fuerza >= 0.45:
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
        evidencia=evidencia,
    )

    operar = True
    decision = "OPERAR_CON_PROTOCOLO"

    if bloqueo_duro:
        operar = False
        decision = "NO_OPERAR"
        motivos.append(motivo_bloqueo)
        confianza = round(
            max(0, min(100, confianza + ajuste_evidencias)),
            2,
        )
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
        motivos.append(
            "Confianza baja: no entrada directa; "
            "solo permitir si el protocolo confirma fuerte."
        )

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
        "bloquear_por_riesgo_y_confianza": (
            bloqueo_duro or riesgo_nivel == "EXTREMO"
        ),
        "aprendizaje_historico": aprendizaje,
        "decision_aprendizaje": aprendizaje.get(
            "decision_aprendizaje",
            "",
        ),
        "ajuste_confianza_aprendizaje": aprendizaje.get(
            "ajuste_confianza_aprendizaje",
            0,
        ),
    }


# ============================================================
# CEREBRO ÚNICO OFICIAL BOOTIQ
# ============================================================
# Esta es la única función autorizada para tomar la decisión final.
#
# Ruta activa:
#   constructor_evidencia.py
#       -> decision_bootiq.py
#       -> evaluar_decision_cerebro_unico()
#       -> bot.py
#       -> entrada.py
#       -> operaciones.py
# ============================================================

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
    ponderacion = calcular_ponderacion_estadistica(evidencia)

    resultado_pa = evaluar_price_action_decision(evidencia)
    resultado_mercado = evaluar_mercado_decision(evidencia)
    resultado_estrategia = evaluar_estrategia_decision(evidencia)

    confianza_base = resultado_inferencia.get("confianza", 50.0)
    ajuste_aprendizaje = aprendizaje.get(
        "ajuste_confianza_aprendizaje",
        0,
    )
    ajuste_ponderacion = ponderacion.get("ajuste_ponderacion", 0)

    ajuste_evidencias = (
        resultado_pa.get("ajuste", 0)
        + resultado_mercado.get("ajuste", 0)
        + resultado_estrategia.get("ajuste", 0)
    )

    resultado_confianza = calcular_confianza_cerebro(
        confianza_base=confianza_base,
        ajuste_aprendizaje=ajuste_aprendizaje,
        ajuste_evidencias=ajuste_evidencias,
        ajuste_ponderacion=ajuste_ponderacion,
    )

    confianza = resultado_confianza["confianza"]
    riesgo_nivel = riesgo_compuesto.get("riesgo_nivel", "BAJO")
    riesgo_puntos = riesgo_compuesto.get("riesgo_puntos", 0)

    resultado_decision = clasificar_decision_final(
        confianza=confianza,
        riesgo_nivel=riesgo_nivel,
    )

    decision = resultado_decision["decision"]
    operar = resultado_decision["operar"]
    
    decision_legacy = resultado_decision.get(
        "decision_legacy",
        decision,
    )
    
    requiere_protocolo = bool(
        resultado_decision.get("requiere_protocolo", False)
    )
    
    modo_ejecucion = resultado_decision.get(
        "modo_ejecucion",
        "BLOQUEADA",
    )
    
    bloquear_por_riesgo = bool(
        resultado_decision.get("bloquear_por_riesgo", False)
    )

    motivos = []
    motivos.extend(resultado_inferencia.get("motivos", []))
    motivos.extend(riesgo_compuesto.get("motivos_riesgo", []))

    motivo_aprendizaje = aprendizaje.get("motivo_aprendizaje", "")
    if motivo_aprendizaje:
        motivos.append(motivo_aprendizaje)

    motivos.extend(resultado_pa.get("motivos", []))
    motivos.extend(resultado_mercado.get("motivos", []))
    motivos.extend(resultado_estrategia.get("motivos", []))
    motivos.extend(ponderacion.get("motivos_ponderacion", []))

    motivo_decision = resultado_decision.get("motivo", "")

    if motivo_decision:
        motivos.append(motivo_decision)
    # ========================================================
    # EVIDENCIAS OFICIALES UTILIZADAS POR EL CEREBRO
    # ========================================================

    pa_evidencias = evidencia.get("pa_evidencias", [])
    if not isinstance(pa_evidencias, list):
        pa_evidencias = []

    mercado_evidencias = evidencia.get("mercado_evidencias", [])
    if not isinstance(mercado_evidencias, list):
        mercado_evidencias = []

    return {
        "operar": operar,
        "decision": decision,
        "decision_legacy": decision_legacy,
        "requiere_protocolo": requiere_protocolo,
        "modo_ejecucion": modo_ejecucion,
        "bloquear_por_riesgo": bloquear_por_riesgo,
        "pa_evidencias": pa_evidencias,
        "mercado_evidencias": mercado_evidencias,
        "confianza": confianza,
        "confianza_base": confianza_base,
        "ajuste_evidencias": round(ajuste_evidencias, 2),
        "resultado_price_action": resultado_pa,
        "resultado_mercado": resultado_mercado,
        "resultado_estrategia": resultado_estrategia,
        "resultado_confianza": resultado_confianza,
        "resultado_decision_final": resultado_decision,
        "riesgo_nivel": riesgo_nivel,
        "riesgo_puntos": riesgo_puntos,
        "motivos": motivos,
        "detalle_inferencia": resultado_inferencia,
        "riesgo_compuesto": riesgo_compuesto,
        "aprendizaje_historico": aprendizaje,
        "decision_aprendizaje": aprendizaje.get(
            "decision_aprendizaje",
            "",
        ),
        "ajuste_confianza_aprendizaje": ajuste_aprendizaje,
        "ajuste_ponderacion": ajuste_ponderacion,
        "ponderacion_estadistica": ponderacion,
    }