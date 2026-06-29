from constructor_evidencia import construir_evidencia_operacion
from validador_fase4 import validar_operacion_fase4


def evaluar_senal_fase4(senal, ctx=None):
    """
    Evalúa una señal con Fase 4 sin eliminarla del backtest.

    Este módulo NO ejecuta operaciones.
    Este módulo NO bloquea directamente.
    Solo registra qué habría decidido Fase 4.
    """

    try:
        evidencia = construir_evidencia_operacion(senal, ctx)
        evaluacion = validar_operacion_fase4(evidencia)

        return {
            "fase4_evaluada": True,
            "fase4_permitir_operacion": evaluacion.get("permitir_operacion", True),
            "fase4_modo": evaluacion.get("modo", ""),
            "fase4_confianza": evaluacion.get("confianza", 50.0),
            "fase4_decision": evaluacion.get("decision_confianza", "NEUTRA"),
            "fase4_debe_bloquear": evaluacion.get("debe_bloquear", False),
            "fase4_motivo": evaluacion.get("motivo", ""),
        }

    except Exception as e:
        return {
            "fase4_evaluada": False,
            "fase4_permitir_operacion": True,
            "fase4_modo": "ERROR",
            "fase4_confianza": 50.0,
            "fase4_decision": "ERROR",
            "fase4_debe_bloquear": False,
            "fase4_motivo": f"Error evaluando Fase 4: {e}",
        }