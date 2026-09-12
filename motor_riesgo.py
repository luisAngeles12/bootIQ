# ============================================================
# MOTOR DE RIESGO BOOTIQ
# ============================================================
# Responsabilidad:
# - cuantificar riesgo técnico/estructural del protocolo;
# - explicar motivos;
# - NO decidir OPERAR / NO_OPERAR;
# - NO volver a juzgar la calidad general de la señal.
#
# La decisión final pertenece exclusivamente a motor_decision.py.
# ============================================================


# ============================================================
# REEVALUACIÓN DE CALIDAD — LEGACY OPCIONAL
# ============================================================
# False:
# - NO usa calidad_setup, balance_setup, nivel_consenso,
#   confianza_setup ni score_final para modificar riesgo.
# - esas variables se conservan para diagnóstico.
#
# True:
# - restaura temporalmente el comportamiento legacy para
#   comparación/backtest.
RIESGO_REEVALUACION_CALIDAD_ACTIVA = False


def _txt(v):
    return str(v or "").lower().strip()


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
        return default


def _bool(v, default=False):
    if isinstance(v, bool):
        return v

    if v is None:
        return default

    texto = str(v).lower().strip()

    if texto in ["true", "1", "si", "sí", "yes"]:
        return True

    if texto in ["false", "0", "no", "none", "null", ""]:
        return False

    return default


def _direccion(senal):
    return _txt(senal.get("direccion"))


def evaluar_riesgo_protocolo(senal):
    """
    Evalúa riesgo técnico del protocolo sin cancelar ni decidir.

    Riesgo operativo activo:
    - riesgo estructural crítico del setup;
    - calidad del mercado;
    - tipo/subtipo del setup;
    - estado/nivel técnico del setup;
    - base de estrategia;
    - price action alineado o contrario.

    Reevaluación legacy opcional:
    - calidad_setup;
    - balance_setup;
    - nivel_consenso;
    - confianza_setup;
    - score_final.

    Estas cinco variables se conservan en diagnóstico, pero con
    RIESGO_REEVALUACION_CALIDAD_ACTIVA=False no modifican el riesgo.
    """

    try:
        riesgo = 0
        motivos = []

        # Campo legacy: se conserva temporalmente como respaldo.
        modo = _txt(senal.get("modo_entrada_setup"))

        # Evidencias neutrales nuevas del motor de setup.
        riesgo_critico_setup = _bool(
            senal.get("riesgo_estructural_critico_setup"),
            default=("no_operar" in modo or "cancelar" in modo),
        )

        requiere_ruptura_setup = _bool(
            senal.get("requiere_ruptura_setup"),
            default=("esperar_ruptura" in modo),
        )

        requiere_confirmacion_setup = _bool(
            senal.get("requiere_confirmacion_setup"),
            default=("esperar_confirmacion" in modo),
        )

        estado_operativo_setup = _txt(
            senal.get("estado_operativo_setup")
        )

        # ====================================================
        # CAMPOS DE DIAGNÓSTICO / COMPATIBILIDAD
        # ====================================================
        calidad = _txt(senal.get("calidad_setup"))
        balance = _num(senal.get("balance_setup"))
        score = _num(senal.get("score_final"))
        nivel_consenso = _txt(senal.get("nivel_consenso"))
        confianza_setup = _num(senal.get("confianza_setup"))

        # ====================================================
        # CAMPOS TÉCNICOS ACTIVOS
        # ====================================================
        tipo_setup = _txt(senal.get("tipo_setup"))
        subtipo = _txt(senal.get("subtipo_setup"))
        estado_setup = _txt(senal.get("estado_setup"))
        nivel_setup = _txt(senal.get("nivel_setup"))
        tendencia = _txt(
            senal.get("tendencia")
            or senal.get("estado_tendencia")
        )
        calidad_mercado = _txt(senal.get("calidad_mercado"))
        base = _txt(senal.get("base_estrategia"))
        pa_tipo = _txt(senal.get("pa_tipo"))
        pa_direccion = _txt(senal.get("pa_direccion"))
        direccion = _direccion(senal)

        # ====================================================
        # 1. RIESGO ESTRUCTURAL REAL DEL SETUP
        # ====================================================
        if riesgo_critico_setup:
            riesgo += 45
            motivos.append(
                "riesgo estructural crítico del setup"
            )

        # ====================================================
        # 2. REEVALUACIÓN DE CALIDAD LEGACY — OPCIONAL
        # ====================================================
        if RIESGO_REEVALUACION_CALIDAD_ACTIVA:
            if calidad in [
                "baja",
                "muy_baja",
                "debil",
                "débil",
            ]:
                riesgo += 35
                motivos.append("calidad setup baja")

            if balance <= -3:
                riesgo += 35
                motivos.append(
                    "balance setup muy negativo"
                )
            elif balance < 0:
                riesgo += 12
                motivos.append("balance setup negativo")
            elif balance >= 2:
                riesgo -= 12
                motivos.append("balance setup positivo")

        # ====================================================
        # 3. MERCADO
        # ====================================================
        if calidad_mercado == "sucio":
            riesgo += 35
            motivos.append("mercado sucio")
        elif calidad_mercado == "normal":
            riesgo += 5
            motivos.append("mercado normal")
        elif calidad_mercado == "limpio":
            riesgo -= 8
            motivos.append("mercado limpio")

        # Contexto técnico específico.
        if (
            tipo_setup == "continuacion"
            and "fuerte" in tendencia
        ):
            riesgo += 15
            motivos.append(
                "continuación en tendencia extrema/fuerte"
            )

        # ====================================================
        # 4. CONSENSO LEGACY — OPCIONAL
        # ====================================================
        if RIESGO_REEVALUACION_CALIDAD_ACTIVA:
            if nivel_consenso == "bueno":
                riesgo += 8
                motivos.append(
                    "consenso bueno, no premium"
                )
            elif nivel_consenso == "alto":
                riesgo -= 10
                motivos.append("consenso alto")
            elif nivel_consenso == "premium":
                riesgo -= 15
                motivos.append("consenso premium")
            elif nivel_consenso in [
                "bajo",
                "muy_bajo",
            ]:
                riesgo += 18
                motivos.append("consenso bajo")

        # ====================================================
        # 5. SUBTIPO / ESTADO / NIVEL DEL SETUP
        # ====================================================
        if subtipo == "zona_sin_ruptura":
            riesgo += 25
            motivos.append("zona sin ruptura")

        if estado_setup == "pendiente_confirmacion":
            riesgo += 18
            motivos.append(
                "setup pendiente confirmación"
            )

        if nivel_setup in ["medio_bajo", "bajo"]:
            riesgo += 15
            motivos.append(
                "nivel setup bajo/medio bajo"
            )

        # ====================================================
        # 6. CONFIANZA SETUP LEGACY — OPCIONAL
        # ====================================================
        if RIESGO_REEVALUACION_CALIDAD_ACTIVA:
            if confianza_setup and confianza_setup < 55:
                riesgo += 15
                motivos.append(
                    "confianza setup baja"
                )
            elif confianza_setup >= 65:
                riesgo -= 8
                motivos.append(
                    "confianza setup aceptable"
                )

        # ====================================================
        # 7. BASE DE ESTRATEGIA
        # ====================================================
        if base == "fuerte":
            riesgo -= 12
            motivos.append(
                "base estrategia fuerte"
            )
        elif base in ["debil", "débil"]:
            riesgo += 12
            motivos.append(
                "base estrategia débil"
            )

        # ====================================================
        # 8. SCORE FINAL LEGACY — OPCIONAL
        # ====================================================
        if RIESGO_REEVALUACION_CALIDAD_ACTIVA:
            if score >= 180:
                riesgo -= 18
                motivos.append("score final alto")
            elif score >= 145:
                riesgo -= 10
                motivos.append(
                    "score final aceptable"
                )
            elif score and score < 100:
                riesgo += 15
                motivos.append("score final bajo")

        # ====================================================
        # 9. PRICE ACTION DIRECCIONAL
        # ====================================================
        if direccion == "call":
            if (
                pa_direccion == "call"
                and "confirmado" in pa_tipo
            ):
                riesgo -= 12
                motivos.append(
                    "PA confirmado a favor CALL"
                )
            elif pa_direccion == "put":
                riesgo += 18
                motivos.append("PA contra CALL")

        if direccion == "put":
            if (
                pa_direccion == "put"
                and "confirmado" in pa_tipo
            ):
                riesgo -= 12
                motivos.append(
                    "PA confirmado a favor PUT"
                )
            elif pa_direccion == "call":
                riesgo += 18
                motivos.append("PA contra PUT")

        # ====================================================
        # NORMALIZACIÓN
        # ====================================================
        if riesgo < 0:
            riesgo = 0

        if riesgo >= 70:
            nivel = "ALTO"
        elif riesgo >= 45:
            nivel = "MEDIO"
        elif riesgo >= 25:
            nivel = "BAJO"
        else:
            nivel = "MUY_BAJO"

        return {
            "riesgo": round(riesgo, 2),
            "nivel": nivel,
            "motivos": motivos,
            "razon": " | ".join(motivos),

            # Trazabilidad del setup.
            "estado_operativo_setup": (
                estado_operativo_setup
            ),
            "riesgo_estructural_critico_setup": (
                riesgo_critico_setup
            ),
            "requiere_ruptura_setup": (
                requiere_ruptura_setup
            ),
            "requiere_confirmacion_setup": (
                requiere_confirmacion_setup
            ),

            # Auditoría de la limpieza.
            "reevaluacion_calidad_activa": (
                RIESGO_REEVALUACION_CALIDAD_ACTIVA
            ),
            "diagnostico_calidad_setup": calidad,
            "diagnostico_balance_setup": balance,
            "diagnostico_nivel_consenso": (
                nivel_consenso
            ),
            "diagnostico_confianza_setup": (
                confianza_setup
            ),
            "diagnostico_score_final": score,
        }

    except Exception as e:
        return {
            "riesgo": 100,
            "nivel": "ERROR",
            "motivos": [
                "error evaluando riesgo protocolo"
            ],
            "razon": (
                "error evaluando riesgo protocolo: "
                + str(e)
            ),
            "reevaluacion_calidad_activa": (
                RIESGO_REEVALUACION_CALIDAD_ACTIVA
            ),
        }


def aplicar_riesgo_decision(decision_bootiq):
    """
    Aplica riesgo al contrato central DecisionBootIQ.

    No cancela.
    No decide.
    Solo escribe evidencia de riesgo.
    """

    try:
        identidad = decision_bootiq.get(
            "identidad",
            {},
        )
        estrategia = decision_bootiq.get(
            "estrategia",
            {},
        )
        mercado = decision_bootiq.get(
            "mercado",
            {},
        )
        price_action = decision_bootiq.get(
            "price_action",
            {},
        )
        setup = decision_bootiq.get(
            "setup",
            {},
        )
        consenso = decision_bootiq.get(
            "consenso",
            {},
        )

        senal_temp = {
            "direccion": identidad.get(
                "direccion",
                "",
            ),
            "patron": identidad.get(
                "patron",
                "",
            ),

            "puntaje": estrategia.get(
                "puntaje",
                0,
            ),
            "prioridad": estrategia.get(
                "prioridad",
                0,
            ),
            "score_final": estrategia.get(
                "score_final",
                0,
            ),
            "calidad": estrategia.get(
                "calidad",
                "",
            ),

            "tipo_mercado": mercado.get(
                "tipo_mercado",
                "",
            ),
            "calidad_mercado": mercado.get(
                "calidad_mercado",
                "",
            ),
            "score_mercado": mercado.get(
                "score_mercado",
                0,
            ),
            "estado_tendencia": mercado.get(
                "estado_tendencia",
                "",
            ),
            "fuerza_tendencia": mercado.get(
                "fuerza_tendencia",
                0,
            ),
            "direccion_tendencia": mercado.get(
                "direccion_tendencia",
                "",
            ),

            "accion_precio": price_action.get(
                "accion_precio",
                "",
            ),
            "pa_tipo": price_action.get(
                "pa_tipo",
                "",
            ),
            "pa_direccion": price_action.get(
                "pa_direccion",
                "",
            ),
            "pa_fuerza": price_action.get(
                "pa_fuerza",
                0,
            ),

            "tipo_setup": setup.get(
                "tipo_setup",
                "",
            ),
            "calidad_setup": setup.get(
                "calidad_setup",
                "",
            ),

            # Compatibilidad legacy.
            "modo_entrada_setup": setup.get(
                "modo_entrada_setup",
                "",
            ),

            # Evidencias neutrales nuevas.
            "estado_operativo_setup": setup.get(
                "estado_operativo_setup",
                "",
            ),
            "riesgo_estructural_critico_setup": (
                setup.get(
                    "riesgo_estructural_critico_setup",
                    None,
                )
            ),
            "requiere_ruptura_setup": setup.get(
                "requiere_ruptura_setup",
                None,
            ),
            "requiere_confirmacion_setup": setup.get(
                "requiere_confirmacion_setup",
                None,
            ),

            "balance_setup": setup.get(
                "balance_setup",
                0,
            ),
            "subtipo_setup": setup.get(
                "subtipo_setup",
                "",
            ),
            "estado_setup": setup.get(
                "estado_setup",
                "",
            ),
            "nivel_setup": setup.get(
                "nivel_setup",
                "",
            ),
            "confianza_setup": setup.get(
                "confianza_setup",
                0,
            ),

            "nivel_consenso": consenso.get(
                "nivel_consenso",
                "",
            ),
            "base_estrategia": estrategia.get(
                "base_estrategia",
                "",
            ),
        }

        resultado = evaluar_riesgo_protocolo(
            senal_temp
        )

        if "riesgos" not in decision_bootiq:
            decision_bootiq["riesgos"] = {}

        if "protocolo" not in decision_bootiq:
            decision_bootiq["protocolo"] = {}

        # ====================================================
        # CONTRATO DE RIESGOS
        # ====================================================
        decision_bootiq["riesgos"][
            "riesgo_protocolo"
        ] = resultado.get(
            "riesgo",
            100,
        )

        decision_bootiq["riesgos"][
            "nivel_riesgo_protocolo"
        ] = resultado.get(
            "nivel",
            "ERROR",
        )

        decision_bootiq["riesgos"][
            "razon_riesgo_protocolo"
        ] = resultado.get(
            "razon",
            "",
        )

        decision_bootiq["riesgos"][
            "motivos_riesgo_protocolo"
        ] = resultado.get(
            "motivos",
            [],
        )

        decision_bootiq["riesgos"][
            "estado_operativo_setup"
        ] = resultado.get(
            "estado_operativo_setup",
            "",
        )

        decision_bootiq["riesgos"][
            "riesgo_estructural_critico_setup"
        ] = resultado.get(
            "riesgo_estructural_critico_setup",
            False,
        )

        decision_bootiq["riesgos"][
            "requiere_ruptura_setup"
        ] = resultado.get(
            "requiere_ruptura_setup",
            False,
        )

        decision_bootiq["riesgos"][
            "requiere_confirmacion_setup"
        ] = resultado.get(
            "requiere_confirmacion_setup",
            False,
        )

        decision_bootiq["riesgos"][
            "reevaluacion_calidad_activa"
        ] = resultado.get(
            "reevaluacion_calidad_activa",
            RIESGO_REEVALUACION_CALIDAD_ACTIVA,
        )

        # Diagnóstico conservado.
        decision_bootiq["riesgos"][
            "diagnostico_calidad_setup"
        ] = resultado.get(
            "diagnostico_calidad_setup",
            "",
        )

        decision_bootiq["riesgos"][
            "diagnostico_balance_setup"
        ] = resultado.get(
            "diagnostico_balance_setup",
            0,
        )

        decision_bootiq["riesgos"][
            "diagnostico_nivel_consenso"
        ] = resultado.get(
            "diagnostico_nivel_consenso",
            "",
        )

        decision_bootiq["riesgos"][
            "diagnostico_confianza_setup"
        ] = resultado.get(
            "diagnostico_confianza_setup",
            0,
        )

        decision_bootiq["riesgos"][
            "diagnostico_score_final"
        ] = resultado.get(
            "diagnostico_score_final",
            0,
        )

        # ====================================================
        # CONTRATO DE PROTOCOLO
        # ====================================================
        decision_bootiq["protocolo"][
            "riesgo_protocolo"
        ] = resultado.get(
            "riesgo",
            100,
        )

        decision_bootiq["protocolo"][
            "nivel_riesgo_protocolo"
        ] = resultado.get(
            "nivel",
            "ERROR",
        )

        decision_bootiq["protocolo"][
            "razon_riesgo_protocolo"
        ] = resultado.get(
            "razon",
            "",
        )

        decision_bootiq["protocolo"][
            "motivos_riesgo_protocolo"
        ] = resultado.get(
            "motivos",
            [],
        )

        decision_bootiq["protocolo"][
            "reevaluacion_calidad_activa"
        ] = resultado.get(
            "reevaluacion_calidad_activa",
            RIESGO_REEVALUACION_CALIDAD_ACTIVA,
        )

        return decision_bootiq

    except Exception as e:
        if "riesgos" not in decision_bootiq:
            decision_bootiq["riesgos"] = {}

        decision_bootiq["riesgos"][
            "riesgo_protocolo"
        ] = 100

        decision_bootiq["riesgos"][
            "nivel_riesgo_protocolo"
        ] = "ERROR"

        decision_bootiq["riesgos"][
            "razon_riesgo_protocolo"
        ] = (
            "error aplicando riesgo a DecisionBootIQ: "
            + str(e)
        )

        decision_bootiq["riesgos"][
            "motivos_riesgo_protocolo"
        ] = [
            "error aplicando riesgo a DecisionBootIQ"
        ]

        decision_bootiq["riesgos"][
            "reevaluacion_calidad_activa"
        ] = RIESGO_REEVALUACION_CALIDAD_ACTIVA

        return decision_bootiq