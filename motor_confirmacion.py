# motor_confirmacion.py

def _txt(v):
    return str(v or "").lower().strip()


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
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

    modo_setup = _txt(senal.get("modo_entrada_setup"))
    calidad_setup = _txt(senal.get("calidad_setup"))
    protocolo = _txt(senal.get("protocolo_sugerido"))
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

    if "no_operar" in modo_setup or "cancelar" in modo_setup:
        return {
            "indice": fase4_confianza,
            "nivel": "BAJO",
            "accion": "CANCELAR",
            "razones": ["Setup indicó NO_OPERAR."],
            "razon": "Setup indicó NO_OPERAR."
        }

    if riesgo_protocolo >= 75:
        return {
            "indice": fase4_confianza,
            "nivel": "BAJO",
            "accion": "CANCELAR",
            "razones": ["Riesgo protocolo alto."],
            "razon": "Riesgo protocolo alto."
        }

    if fase4_confianza >= 70 and calidad_setup in ["premium", "buena", "alta"]:
        razones.append("Confianza Fase 4 alta y setup fuerte.")
        return {
            "indice": fase4_confianza,
            "nivel": "PREMIUM",
            "accion": "ENTRAR",
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
        "accion": "CANCELAR",
        "razones": ["Confianza insuficiente para protocolo."],
        "razon": "Confianza insuficiente para protocolo."
    }