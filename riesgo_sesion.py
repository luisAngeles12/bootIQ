"""Evaluación no bloqueante de stops con el último balance observado.

No consulta al broker, no modifica umbrales ni autoriza operaciones.
"""
import math


def motivo_bloqueo_sesion(balance_inicial, balance_actual, stop_loss, stop_win):
    """Devuelve el motivo para impedir nuevas entradas, o None si no hay stop.

    Rechaza valores ausentes/no finitos; no equipara el balance
    desconocido con una ganancia neta igual a cero.
    """
    try:
        inicial = float(balance_inicial)
        actual = float(balance_actual)
        limite_perdida = float(stop_loss)
        limite_ganancia = float(stop_win)
    except (TypeError, ValueError, OverflowError):
        return "BALANCE_NO_DISPONIBLE"

    if not all(math.isfinite(x) for x in (
        inicial, actual, limite_perdida, limite_ganancia
    )) or inicial < 0 or actual < 0:
        return "BALANCE_NO_VALIDO"

    neto = actual - inicial
    if neto <= limite_perdida:
        return "STOP_LOSS"
    if neto >= limite_ganancia:
        return "STOP_WIN"
    return None
