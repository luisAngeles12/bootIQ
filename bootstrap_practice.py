"""Permiso experimental acotado para arrancar PRACTICE sin memoria CC2.

No declara evidencia estadistica, no cambia umbrales y nunca autoriza REAL.
La conexion se verifica otra vez inmediatamente antes de enviar la orden.
"""
from config import MODO_CUENTA, MIN_PRIORIDAD_OPERAR

def habilitable_sin_memoria(evidencia, decision):
    if MODO_CUENTA != "PRACTICE" or not isinstance(evidencia, dict):
        return False
    if decision.get("decision") != "NO_OPERAR":
        return False
    if decision.get("bloquear_por_riesgo"):
        return False
    # El V3 estadistico puede devolver bloquear_por_riesgo=False aunque
    # el detector estructural haya calculado un bloqueo independiente.
    # El permiso experimental no debe saltarse ese veto ya existente.
    riesgo_compuesto = decision.get("riesgo_compuesto") or {}
    if not isinstance(riesgo_compuesto, dict):
        return False
    if riesgo_compuesto.get("bloquear_por_riesgo") is True:
        return False
    detalle = decision.get("resultado_decision_oficial") or {}
    estadistica = decision.get("resultado_decision_estadistica_sombra") or {}
    if estadistica.get("decision") != "SIN_DATOS_ESTADISTICOS":
        return False
    if "Sin fuente histórica principal utilizable" not in str(detalle.get("motivo", "")):
        return False
    if str(evidencia.get("calidad_mercado", "")).upper() not in {"NORMAL", "LIMPIO"}:
        return False
    if evidencia.get("validacion_mercado_ok") is not True:
        return False
    # Respetar el rechazo explicito del diagnostico de Price Action.
    # No imponer un veto nuevo si el diagnostico no rechazo la entrada.
    if evidencia.get("validacion_accion_precio_ok") is False:
        return False
    if evidencia.get("riesgo_estructural_critico_setup"):
        return False
    if evidencia.get("requiere_confirmacion_setup"):
        return False
    if evidencia.get("requiere_ruptura_setup"):
        return False
    if str(evidencia.get("modo_entrada_setup", "")).upper() != "DIRECTA":
        return False
    try:
        prioridad = int(evidencia.get("prioridad", 0))
    except (TypeError, ValueError):
        return False
    return prioridad >= MIN_PRIORIDAD_OPERAR


def cuenta_practice_verificada(iq):
    try:
        return MODO_CUENTA == "PRACTICE" and iq is not None and iq.get_balance_mode() == "PRACTICE"
    except Exception:
        return False
