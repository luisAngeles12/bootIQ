from config_fase4 import (
    FASE4_ACTIVA,
    FASE4_BLOQUEAR_EN_REAL,
    MODO_FASE4,
    MODO_BACKTEST,
    MODO_REAL_ACTIVO
)

from motor_decision import evaluar_decision


def validar_operacion_fase4(evidencia):
    if not FASE4_ACTIVA:
        return {
            "permitir_operacion": True,
            "modo": "FASE4_INACTIVA",
            "confianza": None,
            "decision_confianza": "NO_EVALUADA",
            "debe_bloquear": False,
            "motivo": "Fase 4 está desactivada."
        }

    decision = evaluar_decision(evidencia)

    operar = decision.get("operar", True)
    confianza = decision.get("confianza", 50.0)
    decision_confianza = decision.get("decision_confianza", "NEUTRA")

    debe_bloquear = not operar

    if MODO_FASE4 == MODO_BACKTEST:
        permitir = operar
        modo = "BACKTEST"

    elif MODO_FASE4 == MODO_REAL_ACTIVO and FASE4_BLOQUEAR_EN_REAL:
        permitir = operar
        modo = "REAL_ACTIVO"

    else:
        permitir = True
        modo = "OBSERVACION"

    return {
        "permitir_operacion": permitir,
        "modo": modo,
        "confianza": confianza,
        "decision_confianza": decision_confianza,
        "decision_final": decision.get("decision", "SIN_DECISION"),
        "debe_bloquear": debe_bloquear,
        "motivo": (
            "Operación bloqueada por motor de decisión Fase 4."
            if not permitir
            else "Operación permitida por configuración actual."
        ),
        "detalle_decision": decision
    }


def probar_validador():
    ejemplos = [
        {
            "patron": "CHOCH bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
            "pa_direccion": "PUT",
            "calidad_mercado": "NORMAL",
            "activo": "BIDU-OTC"
        },
        {
            "patron": "liquidity sweep bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
            "calidad_mercado": "NORMAL",
            "activo": "COCOA-OTC"
        }
    ]

    print("\n===== PRUEBA VALIDADOR FASE 4 =====")

    for i, evidencia in enumerate(ejemplos, start=1):
        resultado = validar_operacion_fase4(evidencia)

        print(f"\n--- EJEMPLO {i} ---")
        print("Patrón:", evidencia["patron"])
        print("Confianza:", resultado["confianza"])
        print("Decisión final:", resultado["decision_final"])
        print("Permitir operación:", resultado["permitir_operacion"])
        print("Modo:", resultado["modo"])
        print("Debe bloquear:", resultado["debe_bloquear"])
        print("Motivo:", resultado["motivo"])


if __name__ == "__main__":
    probar_validador()