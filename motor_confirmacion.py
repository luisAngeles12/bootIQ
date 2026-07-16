# motor_confirmacion.py

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

def decidir_confirmacion(senal):
    """
    Motor de confirmación simplificado.

    No decide si la operación es buena o mala.
    No recalcula IA.
    No recalcula contexto, PA, setup, consenso ni score.

    Solo convierte la decisión previa en una instrucción para el protocolo.
    """

    fase4_decision = _txt(senal.get("fase4_decision"))
    fase4_confianza = _num(senal.get("fase4_confianza"), 50)
    cerebro_decision = _txt(senal.get("cerebro_unico_decision"))
    cerebro_confianza = _num(senal.get("cerebro_unico_confianza"), 0)
    # Campo legacy: respaldo temporal.
    modo_setup = _txt(senal.get("modo_entrada_setup"))
    
    # Evidencias neutrales del setup.
    riesgo_critico_setup = _bool(
        senal.get("riesgo_estructural_critico_setup"),
        default=("no_operar" in modo_setup or "cancelar" in modo_setup)
    )
    
    requiere_ruptura_setup = _bool(
        senal.get("requiere_ruptura_setup"),
        default=("esperar_ruptura" in modo_setup)
    )
    
    requiere_confirmacion_setup = _bool(
        senal.get("requiere_confirmacion_setup"),
        default=("esperar_confirmacion" in modo_setup)
    )
    
    estado_operativo_setup = _txt(
        senal.get("estado_operativo_setup")
    )
    
    calidad_setup = _txt(senal.get("calidad_setup"))
    riesgo_protocolo = _num(senal.get("riesgo_protocolo"), 50)

    razones = []

    if fase4_decision in ["no_operar"]:
        return {
            "indice": fase4_confianza,
            "nivel": "BAJO",
            "accion": "CANCELAR",
            "razones": ["Fase 4 indicó NO_OPERAR."],
            "razon": "Fase 4 indicó NO_OPERAR."
        }

    if riesgo_critico_setup:
        return {
            "indice": fase4_confianza,
            "nivel": "BAJO",
            "accion": "CANCELAR",
            "razones": ["Setup presenta riesgo estructural crítico."],
            "razon": "Setup presenta riesgo estructural crítico."
        }

    if riesgo_protocolo >= 75:
        return {
            "indice": fase4_confianza,
            "nivel": "BAJO",
            "accion": "CANCELAR",
            "razones": ["Riesgo protocolo alto."],
            "razon": "Riesgo protocolo alto."
        }
    if cerebro_decision == "operar" and cerebro_confianza >= 58:
        razones.append("Cerebro único autoriza, pero requiere confirmación técnica.")
        return {
            "indice": cerebro_confianza,
            "nivel": "ALTO",
            "accion": "ESPERAR_2",
            "razones": razones,
            "razon": " | ".join(razones)
        }
    if cerebro_decision == "operar_con_protocolo" and cerebro_confianza >= 55:
        razones.append("Cerebro único permite operación con protocolo.")
        return {
            "indice": cerebro_confianza,
            "nivel": "ALTO",
            "accion": "ESPERAR_2",
            "razones": razones,
            "razon": " | ".join(razones)
        }

    if cerebro_decision == "no_operar" and cerebro_confianza < 38:
        return {
            "indice": cerebro_confianza,
            "nivel": "BAJO",
            "accion": "CANCELAR",
            "razones": ["Cerebro único descarta operación."],
            "razon": "Cerebro único descarta operación."
        }
    if fase4_confianza >= 70 and calidad_setup in ["premium", "buena", "alta"]:
        razones.append("Confianza Fase 4 alta y setup fuerte; requiere confirmación técnica.")
        return {
            "indice": fase4_confianza,
            "nivel": "ALTO",
            "accion": "ESPERAR_2",
            "razones": razones,
            "razon": " | ".join(razones)
        }

    if fase4_confianza >= 55:
        razones.append("Confianza Fase 4 aceptable; requiere confirmación técnica.")
        return {
            "indice": fase4_confianza,
            "nivel": "ALTO",
            "accion": "ESPERAR_2",
            "razones": razones,
            "razon": " | ".join(razones)
        }

    if fase4_confianza >= 42:
        razones.append("Confianza media-baja; protocolo estricto.")
        return {
            "indice": fase4_confianza,
            "nivel": "MEDIO",
            "accion": "ESPERAR_3",
            "razones": razones,
            "razon": " | ".join(razones)
        }

    return {
        "indice": fase4_confianza,
        "nivel": "BAJO",
        "accion": "ESPERAR_3",
        "razones": ["Confianza baja; permitir solo protocolo estricto."],
        "razon": "Confianza baja; permitir solo protocolo estricto."
    }

def aplicar_confirmacion_decision(decision_bootiq):
    """
    Aplica confirmación IA/protocolo al contrato central DecisionBootIQ.

    BootIQ V2:
    - No decide operación final.
    - No modifica señal plana.
    - Solo escribe evidencia en decision_bootiq["protocolo"].
    """

    try:
        setup = decision_bootiq.get("setup", {})
        protocolo = decision_bootiq.get("protocolo", {})
        fase4 = decision_bootiq.get("fase4", {})

        senal_temp = {
            "fase4_decision": fase4.get("fase4_decision", ""),
            "fase4_confianza": fase4.get("fase4_confianza", 50),
            # Compatibilidad legacy.
            "modo_entrada_setup": setup.get("modo_entrada_setup", ""),
            
            # Evidencias neutrales nuevas.
            "estado_operativo_setup": setup.get(
                "estado_operativo_setup",
                ""
            ),
            "riesgo_estructural_critico_setup": setup.get(
                "riesgo_estructural_critico_setup",
                None
            ),
            "requiere_ruptura_setup": setup.get(
                "requiere_ruptura_setup",
                None
            ),
            "requiere_confirmacion_setup": setup.get(
                "requiere_confirmacion_setup",
                None
            ),
            
            "calidad_setup": setup.get("calidad_setup", ""),
            "protocolo_sugerido": protocolo.get("protocolo_sugerido", ""),
            "riesgo_protocolo": protocolo.get("riesgo_protocolo", 50),
            "cerebro_unico_decision": fase4.get("cerebro_unico_decision", ""),
            "cerebro_unico_confianza": fase4.get("cerebro_unico_confianza", 0),
        }

        resultado = decidir_confirmacion(senal_temp)

        decision_bootiq["protocolo"]["indice_confirmacion_ia"] = resultado.get("indice", 0)
        decision_bootiq["protocolo"]["nivel_confirmacion_ia"] = resultado.get("nivel", "")
        decision_bootiq["protocolo"]["accion_confirmacion_ia"] = resultado.get("accion", "")
        decision_bootiq["protocolo"]["razon_confirmacion_ia"] = resultado.get("razon", "")

        return decision_bootiq

    except Exception as e:
        if "protocolo" not in decision_bootiq:
            decision_bootiq["protocolo"] = {}

        decision_bootiq["protocolo"]["indice_confirmacion_ia"] = 0
        decision_bootiq["protocolo"]["nivel_confirmacion_ia"] = "ERROR"
        decision_bootiq["protocolo"]["accion_confirmacion_ia"] = "CANCELAR"
        decision_bootiq["protocolo"]["razon_confirmacion_ia"] = (
            "error aplicando confirmación a DecisionBootIQ: " + str(e)
        )

        return decision_bootiq