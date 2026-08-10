from motor_inferencia import inferir_confianza
from detector_riesgo_compuesto import evaluar_riesgo_compuesto
from motor_aprendizaje_historico import evaluar_aprendizaje_historico
from motor_ponderacion import calcular_ponderacion_estadistica


# ============================================================
# UMBRALES OFICIALES DEL CEREBRO ÚNICO
# ============================================================

UMBRAL_CEREBRO_OPERAR = 62.0
UMBRAL_CEREBRO_PROTOCOLO = 55.0

# ============================================================
# MODO SOMBRA ESTADÍSTICO BOOTIQ V3
# ============================================================
# Estos umbrales NO autorizan operaciones. Solo clasifican la
# probabilidad nueva para medirla en el backtest.
MODO_SOMBRA_ESTADISTICO = True
UMBRAL_PROBABILIDAD_SOMBRA_OPERAR = 55.0
UMBRAL_PROBABILIDAD_SOMBRA_PROTOCOLO = 50.0
MIN_MUESTRA_SOMBRA = 12

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
    No altera la confianza.

    Su función es únicamente detectar, organizar y describir
    el contexto de mercado para que el aprendizaje histórico
    y el Cerebro Único utilicen esa información.
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

        tipo = _txt(ev.get("tipo", ""))

        if tipo:
            tipos_mercado.add(tipo)

    # ========================================================
    # MERCADO SOLO DIAGNOSTICA
    # ========================================================
    # No se aplican bonos ni penalizaciones manuales.
    # El valor estadístico del contexto debe provenir del
    # motor_aprendizaje_historico.py.
    # ========================================================

    ajuste = 0.0

    # ========================================================
    # TIPO PRINCIPAL DE MERCADO
    # ========================================================

    if "mercado_rango" in tipos_mercado:
        motivos.append(
            "Mercado: rango detectado, sin ajuste automático."
        )

    if "mercado_normal" in tipos_mercado:
        motivos.append(
            "Mercado: calidad normal operable, sin ajuste automático."
        )

    # ========================================================
    # CALIDAD
    # ========================================================

    if "mercado_limpio" in tipos_mercado:
        motivos.append(
            "Mercado: contexto limpio detectado, sin ajuste automático."
        )

    if "mercado_sucio" in tipos_mercado:
        motivos.append(
            "Mercado: contexto sucio o caótico detectado, "
            "sin ajuste automático."
        )

    # ========================================================
    # ESTADO DE TENDENCIA
    # ========================================================

    if "tendencia_alcista" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia alcista detectada."
        )

    if "tendencia_bajista" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia bajista detectada."
        )

    if "tendencia_fuerte" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia fuerte detectada, "
            "sin ajuste automático."
        )

    if "tendencia_agotada" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia agotada detectada, "
            "sin ajuste automático."
        )

    if "tendencia_debil" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia débil detectada, "
            "sin ajuste automático."
        )

    if "tendencia_limpia" in tipos_mercado:
        motivos.append(
            "Mercado: tendencia limpia detectada, "
            "sin ajuste automático."
        )

    # ========================================================
    # RÉGIMEN Y RIESGO
    # ========================================================

    if "expansion_peligrosa" in tipos_mercado:
        motivos.append(
            "Mercado: expansión peligrosa detectada, "
            "sin ajuste automático."
        )

    if "rango_sucio" in tipos_mercado:
        motivos.append(
            "Mercado: rango sucio detectado, "
            "sin ajuste automático."
        )

    if "riesgo_mercado_alto" in tipos_mercado:
        motivos.append(
            "Mercado: riesgo general alto detectado, "
            "sin ajuste automático."
        )

    # ========================================================
    # SCORE DE MERCADO
    # ========================================================

    if "score_mercado_alto" in tipos_mercado:
        motivos.append(
            "Mercado: score alto detectado, "
            "sin ajuste automático."
        )

    if "score_mercado_bajo" in tipos_mercado:
        motivos.append(
            "Mercado: score bajo detectado, "
            "sin ajuste automático."
        )

    return {
        "ajuste": round(ajuste, 2),
        "motivos": motivos,
        "tipos_mercado": sorted(tipos_mercado),
        "total_evidencias": len(mercado_evidencias),
        "evidencias_validas": evidencias_validas,
        "modo": "DIAGNOSTICO",
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
    ajuste_price_action,
    ajuste_mercado,
    ajuste_estrategia,
    ajuste_ponderacion,
):
    """
    Calcula la confianza final del Cerebro Único
    y conserva el desglose completo de cada componente.

    Esta función no decide.
    Solamente calcula y registra.
    """

    confianza_base = _num(confianza_base, 50.0)
    ajuste_aprendizaje = _num(ajuste_aprendizaje, 0.0)
    ajuste_price_action = _num(ajuste_price_action, 0.0)
    ajuste_mercado = _num(ajuste_mercado, 0.0)
    ajuste_estrategia = _num(ajuste_estrategia, 0.0)
    ajuste_ponderacion = _num(ajuste_ponderacion, 0.0)

    ajuste_evidencias = (
        ajuste_price_action
        + ajuste_mercado
        + ajuste_estrategia
    )

    confianza_antes_ponderacion = (
        confianza_base
        + ajuste_aprendizaje
        + ajuste_evidencias
    )

    confianza_antes_ponderacion = round(
        max(0.0, min(100.0, confianza_antes_ponderacion)),
        2,
    )

    confianza_final = (
        confianza_antes_ponderacion
        + ajuste_ponderacion
    )

    confianza_final = round(
        max(0.0, min(100.0, confianza_final)),
        2,
    )

    auditoria_confianza = {
        "base": round(confianza_base, 2),
        "aprendizaje": round(ajuste_aprendizaje, 2),
        "price_action": round(ajuste_price_action, 2),
        "mercado": round(ajuste_mercado, 2),
        "estrategia": round(ajuste_estrategia, 2),
        "evidencias_total": round(ajuste_evidencias, 2),
        "ponderacion": round(ajuste_ponderacion, 2),
        "antes_ponderacion": confianza_antes_ponderacion,
        "total": confianza_final,
    }

    return {
        "confianza": confianza_final,
        "confianza_base": round(confianza_base, 2),
        "ajuste_aprendizaje": round(
            ajuste_aprendizaje,
            2,
        ),
        "ajuste_price_action": round(
            ajuste_price_action,
            2,
        ),
        "ajuste_mercado": round(
            ajuste_mercado,
            2,
        ),
        "ajuste_estrategia": round(
            ajuste_estrategia,
            2,
        ),
        "ajuste_evidencias": round(
            ajuste_evidencias,
            2,
        ),
        "ajuste_ponderacion": round(
            ajuste_ponderacion,
            2,
        ),
        "confianza_antes_ponderacion": (
            confianza_antes_ponderacion
        ),
        "auditoria_confianza": auditoria_confianza,
    }

def clasificar_decision_estadistica_sombra(
    probabilidad,
    intervalo_inferior,
    intervalo_superior,
    muestra,
    confiabilidad,
    fuente_principal=None,
):
    """Clasifica la probabilidad nueva sin afectar la operación real."""
    probabilidad = _num(probabilidad, 0.0)
    intervalo_inferior = _num(intervalo_inferior, probabilidad)
    intervalo_superior = _num(intervalo_superior, probabilidad)

    try:
        muestra = int(float(muestra or 0))
    except (TypeError, ValueError):
        muestra = 0

    confiabilidad = str(confiabilidad or "SIN_DATOS").upper().strip()
    fuente_principal = (
        fuente_principal if isinstance(fuente_principal, dict) else {}
    )
    nivel = str(fuente_principal.get("nivel", "") or "").upper().strip()
    clave = str(fuente_principal.get("clave", "") or "").strip()

    if not MODO_SOMBRA_ESTADISTICO:
        return {
            "decision": "SOMBRA_DESACTIVADA",
            "operar": False,
            "requiere_protocolo": False,
            "modo": "DIAGNOSTICO",
            "motivo": "Modo sombra estadístico desactivado.",
            "nivel": nivel,
            "clave": clave,
        }

    if not fuente_principal or muestra <= 0:
        return {
            "decision": "SIN_DATOS_ESTADISTICOS",
            "operar": False,
            "requiere_protocolo": False,
            "modo": "DIAGNOSTICO",
            "motivo": "Sin fuente histórica principal utilizable.",
            "nivel": nivel,
            "clave": clave,
        }

    if muestra < MIN_MUESTRA_SOMBRA:
        return {
            "decision": "NO_OPERAR_SOMBRA_MUESTRA_INSUFICIENTE",
            "operar": False,
            "requiere_protocolo": False,
            "modo": "DIAGNOSTICO",
            "motivo": (
                f"Probabilidad sombra {probabilidad:.2f}%, pero muestra "
                f"{muestra} < {MIN_MUESTRA_SOMBRA}."
            ),
            "nivel": nivel,
            "clave": clave,
        }

    if probabilidad >= UMBRAL_PROBABILIDAD_SOMBRA_OPERAR:
        decision = "OPERAR_SOMBRA"
        operar_sombra = True
        requiere_protocolo_sombra = False
    elif probabilidad >= UMBRAL_PROBABILIDAD_SOMBRA_PROTOCOLO:
        decision = "OPERAR_CON_PROTOCOLO_SOMBRA"
        operar_sombra = True
        requiere_protocolo_sombra = True
    else:
        decision = "NO_OPERAR_SOMBRA"
        operar_sombra = False
        requiere_protocolo_sombra = False

    motivo = (
        f"Probabilidad sombra {probabilidad:.2f}% | intervalo "
        f"{intervalo_inferior:.2f}%–{intervalo_superior:.2f}% | "
        f"muestra {muestra} | confiabilidad {confiabilidad}."
    )

    return {
        "decision": decision,
        "operar": operar_sombra,
        "requiere_protocolo": requiere_protocolo_sombra,
        "modo": "DIAGNOSTICO",
        "motivo": motivo,
        "nivel": nivel,
        "clave": clave,
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
    # RIESGO EXTREMO EN MODO DIAGNÓSTICO
    # ========================================================
    # El backtest mostró que la categoría EXTREMO no justifica
    # un bloqueo automático:
    #
    # 701 señales
    # 360 WIN
    # 341 LOSS
    # 51.36% de winrate
    #
    # El riesgo continúa registrado, pero la decisión dependerá
    # de la confianza y de los umbrales oficiales del Cerebro.
    # ========================================================
    
    riesgo_extremo_diagnostico = riesgo_nivel == "EXTREMO"

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
            "riesgo_extremo_diagnostico": riesgo_extremo_diagnostico,
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
            "riesgo_extremo_diagnostico": riesgo_extremo_diagnostico,
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
        "riesgo_extremo_diagnostico": riesgo_extremo_diagnostico,
        "motivo": (
            "Cerebro único: confianza inferior "
            "al mínimo operativo."
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

    ajuste_price_action = _num(
        resultado_pa.get("ajuste", 0),
        0.0,
    )
    
    ajuste_mercado = _num(
        resultado_mercado.get("ajuste", 0),
        0.0,
    )
    
    ajuste_estrategia = _num(
        resultado_estrategia.get("ajuste", 0),
        0.0,
    )

    ajuste_evidencias = (
        ajuste_price_action
        + ajuste_mercado
        + ajuste_estrategia
    )

    resultado_confianza = calcular_confianza_cerebro(
        confianza_base=confianza_base,
        ajuste_aprendizaje=ajuste_aprendizaje,
        ajuste_price_action=ajuste_price_action,
        ajuste_mercado=ajuste_mercado,
        ajuste_estrategia=ajuste_estrategia,
        ajuste_ponderacion=ajuste_ponderacion,
    )

    confianza = resultado_confianza["confianza"]
    auditoria_confianza = resultado_confianza.get(
        "auditoria_confianza",
        {},
    )
    riesgo_nivel = riesgo_compuesto.get("riesgo_nivel", "BAJO")
    riesgo_puntos = riesgo_compuesto.get("riesgo_puntos", 0)

    # Probabilidad estadística paralela. No participa en la decisión oficial.
    probabilidad_estimada = _num(
        aprendizaje.get("probabilidad_estimada", 0.0),
        0.0,
    )
    intervalo_probabilidad_inferior = _num(
        aprendizaje.get(
            "intervalo_probabilidad_inferior",
            probabilidad_estimada,
        ),
        probabilidad_estimada,
    )
    intervalo_probabilidad_superior = _num(
        aprendizaje.get(
            "intervalo_probabilidad_superior",
            probabilidad_estimada,
        ),
        probabilidad_estimada,
    )
    muestra_probabilidad = aprendizaje.get("muestra_historica", 0)
    wins_probabilidad = aprendizaje.get("wins", 0)
    losses_probabilidad = aprendizaje.get("losses", 0)
    confiabilidad_probabilidad = aprendizaje.get(
        "confiabilidad_muestra",
        "SIN_DATOS",
    )
    fuente_probabilidad_principal = aprendizaje.get(
        "fuente_probabilidad_principal"
    )
    fuente_probabilidad_respaldo = aprendizaje.get(
        "fuente_probabilidad_respaldo"
    )
    modo_probabilidad = aprendizaje.get("modo_probabilidad", "SOMBRA")

    resultado_decision_sombra = clasificar_decision_estadistica_sombra(
        probabilidad=probabilidad_estimada,
        intervalo_inferior=intervalo_probabilidad_inferior,
        intervalo_superior=intervalo_probabilidad_superior,
        muestra=muestra_probabilidad,
        confiabilidad=confiabilidad_probabilidad,
        fuente_principal=fuente_probabilidad_principal,
    )

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
    riesgo_extremo_diagnostico = bool(
        resultado_decision.get(
            "riesgo_extremo_diagnostico",
            False,
        )
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

    motivo_sombra = resultado_decision_sombra.get("motivo", "")
    if motivo_sombra:
        motivos.append("Sombra estadística: " + motivo_sombra)
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
        "riesgo_extremo_diagnostico": riesgo_extremo_diagnostico,
        "pa_evidencias": pa_evidencias,
        "mercado_evidencias": mercado_evidencias,
        "confianza": confianza,
        "confianza_base": confianza_base,
        "ajuste_evidencias": round(ajuste_evidencias, 2),
        "resultado_price_action": resultado_pa,
        "resultado_mercado": resultado_mercado,
        "resultado_estrategia": resultado_estrategia,
        "resultado_confianza": resultado_confianza,
        "auditoria_confianza": auditoria_confianza,
        "ajuste_price_action": ajuste_price_action,
        "ajuste_mercado": ajuste_mercado,
        "ajuste_estrategia": ajuste_estrategia,
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

        # Salida estadística sombra BootIQ V3.
        "modo_probabilidad": modo_probabilidad,
        "probabilidad_estimada": round(probabilidad_estimada, 2),
        "intervalo_probabilidad_inferior": round(
            intervalo_probabilidad_inferior, 2
        ),
        "intervalo_probabilidad_superior": round(
            intervalo_probabilidad_superior, 2
        ),
        "muestra_probabilidad": muestra_probabilidad,
        "wins_probabilidad": wins_probabilidad,
        "losses_probabilidad": losses_probabilidad,
        "confiabilidad_probabilidad": confiabilidad_probabilidad,
        "fuente_probabilidad_principal": fuente_probabilidad_principal,
        "fuente_probabilidad_respaldo": fuente_probabilidad_respaldo,
        "decision_estadistica_sombra": resultado_decision_sombra.get(
            "decision", "SIN_DATOS"
        ),
        "operar_estadistico_sombra": bool(
            resultado_decision_sombra.get("operar", False)
        ),
        "requiere_protocolo_estadistico_sombra": bool(
            resultado_decision_sombra.get("requiere_protocolo", False)
        ),
        "nivel_probabilidad_principal": resultado_decision_sombra.get(
            "nivel", ""
        ),
        "clave_probabilidad_principal": resultado_decision_sombra.get(
            "clave", ""
        ),
        "motivo_decision_estadistica_sombra": resultado_decision_sombra.get(
            "motivo", ""
        ),
        "resultado_decision_estadistica_sombra": resultado_decision_sombra,
    }