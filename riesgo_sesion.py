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


def antiguedad_observacion_balance(ultima_observacion_monotonic, ahora_monotonic):
    """Segundos desde la última lectura correcta; None si no es medible.

    Métrica sombra: no decide entradas, umbrales ni llamadas al broker.
    Usa reloj monotónico, independiente de correcciones de hora de Windows.
    """
    try:
        ultima = float(ultima_observacion_monotonic)
        ahora = float(ahora_monotonic)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(ultima) or not math.isfinite(ahora):
        return None
    if ultima < 0 or ahora < ultima:
        return None
    return round(ahora - ultima, 3)
