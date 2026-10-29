"""Observacion de comisiones TURBO del WebSocket IQ, SOLO PRACTICE.

No solicita get_all_init ni get_all_profit (pueden bloquearse).
Un evento de cambio NO equivale a cotizacion inicial; sin uno reciente,
la informacion economica se declara desconocida.
"""
from math import isfinite


def leer_comision_turbo(datos, activo, ahora, edad_maxima=60):
    """Devuelve un diagnostico, no una autorizacion ni una orden."""
    salida = {
        "estado": "PAYOUT_NO_VERIFICADO",
        "activo": activo,
        "instrumento": "turbo-option",
        "payout_neto": None,
        "timestamp_fuente": None,
        "operable": False,
    }
    if not isinstance(datos, dict):
        salida["motivo"] = "SIN_EVENTO_COMISION"
        return salida
    por_activo = datos.get(activo)
    if not isinstance(por_activo, dict) or not por_activo:
        salida["motivo"] = "SIN_EVENTO_ACTIVO"
        return salida
    try:
        timestamp = max(int(t) for t in por_activo)
        comision = por_activo.get(timestamp, por_activo.get(str(timestamp)))
        comision = float(comision)
        if not isfinite(comision) or not 0 <= comision < 100:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        salida["motivo"] = "COMISION_INVALIDA"
        return salida
    if timestamp > ahora or ahora - timestamp > edad_maxima:
        salida["motivo"] = "COTIZACION_DESACTUALIZADA"
        return salida
    # El handler local convierte la comision recibida a int (trunca).
    # Descontar 1 punto porcentual adicional evita sobrestimar el payout.
    payout_conservador = (99.0 - comision) / 100.0
    if payout_conservador <= 0:
        salida["motivo"] = "PAYOUT_NO_POSITIVO"
        return salida
    salida.update({
        "estado": "COMISION_RECIENTE_ESTIMACION_CONSERVADORA",
        "timestamp_fuente": timestamp,
        "payout_neto": round(payout_conservador, 4),
        "motivo": "CAMBIO_WEBSOCKET_NO_ES_COTIZACION_EJECUTABLE",
    })
    return salida
