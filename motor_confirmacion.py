# motor_confirmacion.py


def _txt(v):
    return str(v or "").lower().strip()


def _num(v, default=0):
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
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


def _resultado(indice, nivel, accion, razon):
    """
    Construye una respuesta uniforme para el motor de protocolos.
    """

    return {
        "indice": round(_num(indice, 0), 2),
        "nivel": nivel,
        "accion": accion,
        "razones": [razon],
        "razon": razon,
    }


def decidir_confirmacion(senal):
    """
    Traduce la decisión previa del Cerebro Único en una instrucción
    de confirmación para motor_protocolos.

    Este motor:

    - No decide la calidad general de la operación.
    - No recalcula estrategia, setup, contexto ni consenso.
    - No reemplaza la decisión del Cerebro Único.
    - Solo determina cuán estricta debe ser la confirmación técnica.

    Jerarquía:

    1. Riesgo estructural crítico del setup.
    2. Riesgo crítico propio del protocolo.
    3. Decisión final del Cerebro Único.
    4. Requisitos técnicos neutrales del setup.
    5. Fase 4 como evidencia secundaria.
    """

    fase4_decision = _txt(
        senal.get("fase4_decision")
    )

    fase4_confianza = _num(
        senal.get("fase4_confianza"),
        50,
    )

    cerebro_decision = _txt(
        senal.get("cerebro_unico_decision")
    )

    cerebro_confianza = _num(
        senal.get("cerebro_unico_confianza"),
        0,
    )

    modo_setup = _txt(
        senal.get("modo_entrada_setup")
    )

    riesgo_critico_setup = _bool(
        senal.get("riesgo_estructural_critico_setup"),
        default=(
            "no_operar" in modo_setup
            or "cancelar" in modo_setup
        ),
    )

    requiere_ruptura_setup = _bool(
        senal.get("requiere_ruptura_setup"),
        default=("esperar_ruptura" in modo_setup),
    )

    requiere_confirmacion_setup = _bool(
        senal.get("requiere_confirmacion_setup"),
        default=("esperar_confirmacion" in modo_setup),
    )

    estado_operativo_setup = _txt(
        senal.get("estado_operativo_setup")
    )

    calidad_setup = _txt(
        senal.get("calidad_setup")
    )

    riesgo_protocolo = _num(
        senal.get("riesgo_protocolo"),
        50,
    )

    # ========================================================
    # 1. CANCELACIONES TÉCNICAS DURAS
    # ========================================================

    # Esta no es una decisión general de calidad.
    # Es una incompatibilidad estructural directa del setup.
    if riesgo_critico_setup:
        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="BAJO",
            accion="CANCELAR",
            razon=(
                "Setup presenta riesgo estructural crítico; "
                "no existe entrada técnica segura."
            ),
        )

    # El umbral debe coincidir con motor_protocolos.py.
    if riesgo_protocolo >= 85:
        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="BAJO",
            accion="CANCELAR",
            razon=(
                "Riesgo de protocolo crítico igual o superior a 85."
            ),
        )

    # ========================================================
    # 2. RESPETAR DECISIÓN FINAL DEL CEREBRO
    # ========================================================

    if cerebro_decision == "no_operar":
        return _resultado(
            indice=cerebro_confianza,
            nivel="BAJO",
            accion="CANCELAR",
            razon=(
                "Cerebro Único mantiene decisión final NO_OPERAR."
            ),
        )

    # ========================================================
    # 3. RIESGO ALTO NO CRÍTICO
    # ========================================================

    # Entre 75 y 84 no se cancela automáticamente.
    # Se exige la confirmación más estricta.
    if riesgo_protocolo >= 75:
        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "Riesgo de protocolo alto, pero no crítico; "
                "requiere confirmación técnica estricta."
            ),
        )

    # ========================================================
    # 4. REQUISITOS EXPLÍCITOS DEL SETUP
    # ========================================================

    if requiere_ruptura_setup:
        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "El setup exige ruptura técnica antes de entrar."
            ),
        )

    if requiere_confirmacion_setup:
        if cerebro_confianza >= 58:
            return _resultado(
                indice=cerebro_confianza,
                nivel="ALTO",
                accion="ESPERAR_2",
                razon=(
                    "Cerebro Único autoriza y el setup exige "
                    "confirmación técnica."
                ),
            )

        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "El setup exige confirmación y la confianza "
                "requiere validación estricta."
            ),
        )

    # ========================================================
    # 5. DECISIÓN OPERATIVA DEL CEREBRO
    # ========================================================

    if (
        cerebro_decision == "operar"
        and cerebro_confianza >= 58
    ):
        return _resultado(
            indice=cerebro_confianza,
            nivel="ALTO",
            accion="ESPERAR_2",
            razon=(
                "Cerebro Único autoriza la operación; "
                "se solicita confirmación técnica normal."
            ),
        )

    if (
        cerebro_decision == "operar_con_protocolo"
        and cerebro_confianza >= 55
    ):
        return _resultado(
            indice=cerebro_confianza,
            nivel="ALTO",
            accion="ESPERAR_2",
            razon=(
                "Cerebro Único autoriza con protocolo de entrada."
            ),
        )

    # ========================================================
    # 6. ESTADO OPERATIVO DEL SETUP
    # ========================================================

    if estado_operativo_setup in [
        "esperar_ruptura",
        "ruptura_pendiente",
    ]:
        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "Estado operativo del setup requiere ruptura."
            ),
        )

    if estado_operativo_setup in [
        "esperar_confirmacion",
        "confirmacion_pendiente",
    ]:
        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "Estado operativo del setup requiere confirmación."
            ),
        )

    # ========================================================
    # 7. FASE 4 COMO EVIDENCIA SECUNDARIA
    # ========================================================

    # Fase 4 ya no cancela por sí sola si el Cerebro autorizó.
    if fase4_decision == "no_operar":
        return _resultado(
            indice=max(cerebro_confianza, fase4_confianza),
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "Fase 4 fue desfavorable, pero el Cerebro Único "
                "autorizó; se exige confirmación estricta."
            ),
        )

    if (
        fase4_confianza >= 70
        and calidad_setup in [
            "premium",
            "buena",
            "alta",
        ]
    ):
        return _resultado(
            indice=fase4_confianza,
            nivel="ALTO",
            accion="ESPERAR_2",
            razon=(
                "Fase 4 presenta confianza alta y setup fuerte."
            ),
        )

    if fase4_confianza >= 55:
        return _resultado(
            indice=fase4_confianza,
            nivel="ALTO",
            accion="ESPERAR_2",
            razon=(
                "Confianza Fase 4 aceptable; "
                "requiere confirmación técnica normal."
            ),
        )

    if fase4_confianza >= 42:
        return _resultado(
            indice=fase4_confianza,
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "Confianza Fase 4 media-baja; "
                "requiere protocolo estricto."
            ),
        )

    return _resultado(
        indice=max(cerebro_confianza, fase4_confianza),
        nivel="BAJO",
        accion="ESPERAR_3",
        razon=(
            "Evidencia limitada; únicamente se permite "
            "confirmación técnica estricta."
        ),
    )


def aplicar_confirmacion_decision(decision_bootiq):
    """
    Aplica evidencia de confirmación al contrato DecisionBootIQ.

    BootIQ V2:

    - No decide la operación final.
    - No modifica la señal plana.
    - Solo escribe evidencia dentro de protocolo.
    """

    try:
        setup = decision_bootiq.get("setup", {})
        protocolo = decision_bootiq.get("protocolo", {})
        fase4 = decision_bootiq.get("fase4", {})

        senal_temp = {
            "fase4_decision": fase4.get(
                "fase4_decision",
                "",
            ),
            "fase4_confianza": fase4.get(
                "fase4_confianza",
                50,
            ),

            # Compatibilidad legacy.
            "modo_entrada_setup": setup.get(
                "modo_entrada_setup",
                "",
            ),

            # Evidencias neutrales del setup.
            "estado_operativo_setup": setup.get(
                "estado_operativo_setup",
                "",
            ),
            "riesgo_estructural_critico_setup": setup.get(
                "riesgo_estructural_critico_setup",
                None,
            ),
            "requiere_ruptura_setup": setup.get(
                "requiere_ruptura_setup",
                None,
            ),
            "requiere_confirmacion_setup": setup.get(
                "requiere_confirmacion_setup",
                None,
            ),

            "calidad_setup": setup.get(
                "calidad_setup",
                "",
            ),
            "protocolo_sugerido": protocolo.get(
                "protocolo_sugerido",
                "",
            ),
            "riesgo_protocolo": protocolo.get(
                "riesgo_protocolo",
                50,
            ),

            # Se mantienen aquí por compatibilidad con el contrato actual.
            "cerebro_unico_decision": fase4.get(
                "cerebro_unico_decision",
                "",
            ),
            "cerebro_unico_confianza": fase4.get(
                "cerebro_unico_confianza",
                0,
            ),
        }

        resultado = decidir_confirmacion(senal_temp)

        decision_bootiq.setdefault(
            "protocolo",
            {},
        )

        decision_bootiq["protocolo"][
            "indice_confirmacion_ia"
        ] = resultado.get("indice", 0)

        decision_bootiq["protocolo"][
            "nivel_confirmacion_ia"
        ] = resultado.get("nivel", "")

        decision_bootiq["protocolo"][
            "accion_confirmacion_ia"
        ] = resultado.get("accion", "")

        decision_bootiq["protocolo"][
            "razon_confirmacion_ia"
        ] = resultado.get("razon", "")

        return decision_bootiq

    except Exception as e:
        decision_bootiq.setdefault(
            "protocolo",
            {},
        )

        decision_bootiq["protocolo"][
            "indice_confirmacion_ia"
        ] = 0

        decision_bootiq["protocolo"][
            "nivel_confirmacion_ia"
        ] = "ERROR"

        decision_bootiq["protocolo"][
            "accion_confirmacion_ia"
        ] = "CANCELAR"

        decision_bootiq["protocolo"][
            "razon_confirmacion_ia"
        ] = (
            "Error aplicando confirmación a DecisionBootIQ: "
            + str(e)
        )

        return decision_bootiq