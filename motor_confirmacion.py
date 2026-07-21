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
    Define únicamente el nivel de confirmación técnica.

    No decide si la operación es buena.
    No reevalúa al Cerebro Único.
    No utiliza Fase 4 para autorizar o rechazar.
    """

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

    riesgo_protocolo = _num(
        senal.get("riesgo_protocolo"),
        50,
    )

    if riesgo_critico_setup:
        return _resultado(
            indice=0,
            nivel="BAJO",
            accion="CANCELAR",
            razon=(
                "El protocolo detectó incompatibilidad "
                "estructural crítica para la entrada."
            ),
        )

    if riesgo_protocolo >= 85:
        return _resultado(
            indice=0,
            nivel="BAJO",
            accion="CANCELAR",
            razon=(
                "Riesgo técnico del protocolo igual "
                "o superior a 85."
            ),
        )

    if riesgo_protocolo >= 75:
        return _resultado(
            indice=40,
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "Riesgo técnico alto; requiere "
                "confirmación estricta."
            ),
        )

    if requiere_ruptura_setup:
        return _resultado(
            indice=50,
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "El setup requiere una ruptura técnica."
            ),
        )

    if estado_operativo_setup in [
        "esperar_ruptura",
        "ruptura_pendiente",
    ]:
        return _resultado(
            indice=50,
            nivel="MEDIO",
            accion="ESPERAR_3",
            razon=(
                "El estado técnico requiere ruptura."
            ),
        )

    if requiere_confirmacion_setup:
        return _resultado(
            indice=60,
            nivel="ALTO",
            accion="ESPERAR_2",
            razon=(
                "El setup requiere confirmación técnica normal."
            ),
        )

    if estado_operativo_setup in [
        "esperar_confirmacion",
        "confirmacion_pendiente",
    ]:
        return _resultado(
            indice=60,
            nivel="ALTO",
            accion="ESPERAR_2",
            razon=(
                "El estado técnico requiere confirmación."
            ),
        )

    return _resultado(
        indice=65,
        nivel="ALTO",
        accion="ESPERAR_2",
        razon=(
            "Se aplica confirmación técnica normal."
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

        senal_temp = {
            "modo_entrada_setup": setup.get(
                "modo_entrada_setup",
                "",
            ),
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
            "riesgo_protocolo": protocolo.get(
                "riesgo_protocolo",
                50,
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