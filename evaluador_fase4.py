"""
LEGACY BOOTIQ — EVALUADOR FASE 4 ANTIGUO.

Este módulo ya no forma parte de la decisión oficial.

Ruta activa:
    decision_bootiq.py
        -> motor_decision.evaluar_decision_cerebro_unico()

Responsabilidad actual:
    - construir evidencia;
    - consultar el adaptador legacy validador_fase4.py;
    - devolver campos de observación compatibles;
    - no autorizar;
    - no bloquear;
    - no ejecutar operaciones.

Debe eliminarse cuando no existan consumidores legacy.
"""

from constructor_evidencia import construir_evidencia_operacion
from validador_fase4 import validar_operacion_fase4


def _numero(valor, default=0.0):
    try:
        return float(valor if valor is not None else default)
    except (TypeError, ValueError):
        return float(default)


def evaluar_senal_fase4(senal, ctx=None):
    """
    Ejecuta una evaluación legacy exclusivamente informativa.

    IMPORTANTE:
    - fase4_permitir_operacion refleja lo decidido por Cerebro Único;
    - este módulo no debe usarse para ejecutar ni bloquear operaciones;
    - cualquier consumidor activo debe migrar a decision_bootiq.py.
    """

    if not isinstance(senal, dict):
        senal = {}

    if not isinstance(ctx, dict):
        ctx = {}

    try:
        evidencia = construir_evidencia_operacion(senal, ctx)

        if not isinstance(evidencia, dict):
            evidencia = {}

        evaluacion = validar_operacion_fase4(evidencia)

        if not isinstance(evaluacion, dict):
            evaluacion = {}

        permitir = bool(
            evaluacion.get("permitir_operacion", False)
        )

        debe_bloquear = bool(
            evaluacion.get("debe_bloquear", not permitir)
        )

        decision_final = str(
            evaluacion.get(
                "decision_final",
                evaluacion.get("decision_confianza", "NO_OPERAR"),
            )
            or "NO_OPERAR"
        ).upper().strip()

        decision_legacy = str(
            evaluacion.get("decision_legacy", decision_final)
            or decision_final
        ).upper().strip()

        return {
            "fase4_evaluada": True,
            "fase4_permitir_operacion": permitir,
            "fase4_modo": str(
                evaluacion.get("modo", "LEGACY")
                or "LEGACY"
            ),
            "fase4_confianza": _numero(
                evaluacion.get("confianza"),
                0.0,
            ),
            "fase4_decision": decision_legacy,
            "fase4_decision_oficial": decision_final,
            "fase4_debe_bloquear": debe_bloquear,
            "fase4_motivo": str(
                evaluacion.get("motivo", "")
                or ""
            ),
            "fase4_requiere_protocolo": bool(
                evaluacion.get("requiere_protocolo", False)
            ),
            "fase4_modo_ejecucion": str(
                evaluacion.get("modo_ejecucion", "BLOQUEADA")
                or "BLOQUEADA"
            ),
            "fase4_bloquear_por_riesgo": bool(
                evaluacion.get("bloquear_por_riesgo", False)
            ),
            "fase4_origen_decision": str(
                evaluacion.get("origen_decision", "CEREBRO_UNICO")
                or "CEREBRO_UNICO"
            ),
            "fase4_legacy": True,

            # Auditoría completa.
            "fase4_detalle": evaluacion,
        }

    except Exception as exc:
        # Cierre seguro. Un error legacy nunca debe autorizar una operación.
        return {
            "fase4_evaluada": False,
            "fase4_permitir_operacion": False,
            "fase4_modo": "ERROR",
            "fase4_confianza": 0.0,
            "fase4_decision": "NO_OPERAR",
            "fase4_decision_oficial": "NO_OPERAR",
            "fase4_debe_bloquear": True,
            "fase4_motivo": f"Error evaluando Fase 4 legacy: {exc}",
            "fase4_requiere_protocolo": False,
            "fase4_modo_ejecucion": "BLOQUEADA",
            "fase4_bloquear_por_riesgo": True,
            "fase4_origen_decision": "ERROR_LEGACY",
            "fase4_legacy": True,
            "fase4_detalle": {},
        }


def probar_evaluador_fase4():
    """
    Prueba rápida del contrato legacy.
    """

    ejemplo = {
        "activo": "BIDU-OTC",
        "direccion": "PUT",
        "patron": "CHOCH bajista",
        "tipo_mercado": "TENDENCIA_BAJISTA",
        "estado_tendencia": "BAJISTA_NORMAL",
        "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
        "pa_direccion": "PUT",
        "calidad_mercado": "NORMAL",
    }

    resultado = evaluar_senal_fase4(ejemplo)

    assert "fase4_permitir_operacion" in resultado
    assert "fase4_decision_oficial" in resultado
    assert "fase4_modo_ejecucion" in resultado
    assert resultado["fase4_legacy"] is True

    return resultado


if __name__ == "__main__":
    resultado = probar_evaluador_fase4()

    print("\n===== EVALUADOR FASE 4 LEGACY =====")
    print("Evaluada:", resultado["fase4_evaluada"])
    print("Decisión oficial:", resultado["fase4_decision_oficial"])
    print("Decisión legacy:", resultado["fase4_decision"])
    print("Permitir operación:", resultado["fase4_permitir_operacion"])
    print("Debe bloquear:", resultado["fase4_debe_bloquear"])
    print("Modo ejecución:", resultado["fase4_modo_ejecucion"])
    print("Motivo:", resultado["fase4_motivo"])