"""
LEGACY BOOTIQ — VALIDADOR FASE 4 ANTIGUO.

Este módulo pertenece a la arquitectura anterior de BootIQ.

Ruta oficial activa:
    decision_bootiq.py
        -> motor_decision.evaluar_decision_cerebro_unico()

Este archivo:
    - no debe decidir;
    - no debe bloquear producción;
    - no debe invocar motor_decision.evaluar_decision();
    - no debe reconectarse con bot.py, backtest oficial ni operaciones.py.

Se conserva únicamente como adaptador de compatibilidad para consumidores
legacy que todavía esperen la función validar_operacion_fase4().
"""

from config_fase4 import (
    FASE4_ACTIVA,
    FASE4_BLOQUEAR_EN_REAL,
    MODO_FASE4,
    MODO_BACKTEST,
    MODO_REAL_ACTIVO,
)

from motor_decision import evaluar_decision_cerebro_unico


def _numero(valor, default=0.0):
    try:
        return float(valor if valor is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _lista_texto(valor):
    if isinstance(valor, list):
        return [str(x) for x in valor if str(x).strip()]

    if valor in (None, ""):
        return []

    return [str(valor)]


def _modo_legacy():
    """
    Devuelve el modo configurado sin convertir este adaptador
    en una segunda autoridad de ejecución.
    """

    if not FASE4_ACTIVA:
        return "FASE4_INACTIVA"

    if MODO_FASE4 == MODO_BACKTEST:
        return "BACKTEST"

    if MODO_FASE4 == MODO_REAL_ACTIVO:
        return "REAL_ACTIVO"

    return "OBSERVACION"


def validar_operacion_fase4(evidencia):
    """
    Adaptador legacy sobre el Cerebro Único.

    No crea una decisión independiente.
    No reinterpreta confianza.
    No aplica reglas propias de bloqueo.

    La autorización oficial siempre proviene de:
        evaluar_decision_cerebro_unico()
    """

    if not isinstance(evidencia, dict):
        evidencia = {}

    modo = _modo_legacy()

    if not FASE4_ACTIVA:
        return {
            "permitir_operacion": True,
            "modo": modo,
            "confianza": None,
            "decision_confianza": "NO_EVALUADA",
            "decision_final": "NO_EVALUADA",
            "decision_legacy": "NO_EVALUADA",
            "debe_bloquear": False,
            "requiere_protocolo": False,
            "modo_ejecucion": "NO_EVALUADO",
            "bloquear_por_riesgo": False,
            "motivo": "Fase 4 legacy desactivada.",
            "detalle_decision": {},
            "origen_decision": "SIN_EVALUAR",
            "legacy": True,
        }

    try:
        decision = evaluar_decision_cerebro_unico(evidencia)
    except Exception as exc:
        return {
            "permitir_operacion": False,
            "modo": modo,
            "confianza": 0.0,
            "decision_confianza": "ERROR",
            "decision_final": "NO_OPERAR",
            "decision_legacy": "NO_OPERAR",
            "debe_bloquear": True,
            "requiere_protocolo": False,
            "modo_ejecucion": "BLOQUEADA",
            "bloquear_por_riesgo": True,
            "motivo": f"Error en Cerebro Único: {exc}",
            "detalle_decision": {},
            "origen_decision": "CEREBRO_UNICO_ERROR",
            "legacy": True,
        }

    if not isinstance(decision, dict):
        decision = {}

    operar = bool(decision.get("operar", False))
    confianza = _numero(decision.get("confianza"), 0.0)

    decision_final = str(
        decision.get("decision", "NO_OPERAR") or "NO_OPERAR"
    ).upper().strip()

    decision_legacy = str(
        decision.get("decision_legacy", decision_final) or decision_final
    ).upper().strip()

    requiere_protocolo = bool(
        decision.get("requiere_protocolo", False)
    )

    modo_ejecucion = str(
        decision.get(
            "modo_ejecucion",
            "DIRECTA" if operar else "BLOQUEADA",
        )
        or ("DIRECTA" if operar else "BLOQUEADA")
    ).upper().strip()

    bloquear_por_riesgo = bool(
        decision.get("bloquear_por_riesgo", False)
    )

    motivos = _lista_texto(decision.get("motivos"))
    bloqueos = _lista_texto(decision.get("bloqueos"))

    # Este adaptador no puede otorgar permiso si el Cerebro Único dijo no.
    # Tampoco puede bloquear una operación que el Cerebro Único autorizó.
    permitir = operar
    debe_bloquear = not operar

    if debe_bloquear:
        motivo = " | ".join(
            bloqueos or motivos or ["Operación no autorizada por Cerebro Único."]
        )
    elif requiere_protocolo:
        motivo = (
            "Operación autorizada por Cerebro Único con ejecución mediante "
            "protocolo."
        )
    else:
        motivo = "Operación autorizada por Cerebro Único."

    return {
        "permitir_operacion": permitir,
        "modo": modo,
        "confianza": confianza,
        "decision_confianza": decision_final,
        "decision_final": decision_final,
        "decision_legacy": decision_legacy,
        "debe_bloquear": debe_bloquear,
        "requiere_protocolo": requiere_protocolo,
        "modo_ejecucion": modo_ejecucion,
        "bloquear_por_riesgo": bloquear_por_riesgo,
        "motivo": motivo,
        "detalle_decision": decision,
        "origen_decision": "CEREBRO_UNICO",
        "legacy": True,

        # Solo informativo. Ya no altera la autorización.
        "config_fase4_bloquear_en_real": bool(
            FASE4_BLOQUEAR_EN_REAL
        ),
    }


def probar_validador():
    """
    Prueba rápida del contrato legacy.
    """

    ejemplos = [
        {
            "patron": "CHOCH bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
            "pa_direccion": "PUT",
            "calidad_mercado": "NORMAL",
            "activo": "BIDU-OTC",
        },
        {
            "patron": "liquidity sweep bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
            "calidad_mercado": "NORMAL",
            "activo": "COCOA-OTC",
        },
    ]

    resultados = []

    for evidencia in ejemplos:
        resultado = validar_operacion_fase4(evidencia)

        assert "permitir_operacion" in resultado
        assert "decision_final" in resultado
        assert "modo_ejecucion" in resultado
        assert resultado.get("origen_decision") in {
            "SIN_EVALUAR",
            "CEREBRO_UNICO",
            "CEREBRO_UNICO_ERROR",
        }

        resultados.append(resultado)

    return resultados


if __name__ == "__main__":
    print("\n===== PRUEBA VALIDADOR FASE 4 LEGACY =====")

    for indice, resultado in enumerate(
        probar_validador(),
        start=1,
    ):
        print(f"\n--- EJEMPLO {indice} ---")
        print("Confianza:", resultado["confianza"])
        print("Decisión final:", resultado["decision_final"])
        print("Permitir operación:", resultado["permitir_operacion"])
        print("Modo:", resultado["modo"])
        print("Debe bloquear:", resultado["debe_bloquear"])
        print("Modo ejecución:", resultado["modo_ejecucion"])
        print("Motivo:", resultado["motivo"])