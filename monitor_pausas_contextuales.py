"""Evaluación en sombra para futuras pausas por estrategia y mercado.

Nunca escribe cooldowns, no consulta al bróker y no veta operaciones.
Solo considera operaciones efectivamente cerradas con resultado monetario.
"""

from collections import defaultdict
from math import isfinite


def _fecha(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def evaluar_contextos_cerrados(filas, *, ventana, muestra_minima):
    """Informa contextos con pérdidas netas recientes sin suspenderlos.

    ventana y muestra_minima son parámetros explícitos, sujetos a calibración
    posterior con datos independientes. Nunca cuentan resultados hipotéticos.
    """
    if not isinstance(ventana, int) or not isinstance(muestra_minima, int):
        raise ValueError("ventana y muestra_minima deben ser enteros")
    if ventana < 1 or muestra_minima < 1 or muestra_minima > ventana:
        raise ValueError("ventana y muestra_minima invalidas")

    grupos = defaultdict(list)
    descartes = defaultdict(int)
    for indice, fila in enumerate(filas):
        if not isinstance(fila, dict) or str(fila.get("estado") or "").upper().strip() != "CERRADA":
            descartes["no_cerrada"] += 1
            continue
        estrategia = str(fila.get("patron") or "").upper().strip()
        mercado = str(fila.get("tipo_mercado") or "").upper().strip()
        direccion = str(fila.get("direccion") or "").upper().strip()
        if not estrategia or not mercado or not direccion:
            descartes["contexto_incompleto"] += 1
            continue
        try:
            pnl = float(fila["resultado"])
        except (KeyError, TypeError, ValueError):
            descartes["resultado_invalido"] += 1
            continue
        if not isfinite(pnl) or pnl == 0:
            descartes["resultado_invalido"] += 1
            continue
        # El orden original desempata marcas de tiempo idénticas.
        tiempo = _fecha(fila.get("fecha_cierre"))
        if tiempo is None:
            tiempo = _fecha(fila.get("fecha"))
        if tiempo is None or not isfinite(tiempo):
            descartes["fecha_invalida"] += 1
            continue
        grupos[(estrategia, mercado, direccion)].append((tiempo, indice, pnl))

    reporte = []
    for (estrategia, mercado, direccion), operaciones in grupos.items():
        ultimas = sorted(operaciones)[-ventana:]
        n = len(ultimas)
        wins = sum(pnl > 0 for _, _, pnl in ultimas)
        neto = round(sum(pnl for _, _, pnl in ultimas), 2)
        reporte.append({
            "estrategia": estrategia, "mercado": mercado, "direccion": direccion,
            "muestra": n, "wins": wins, "losses": n - wins, "neto": neto,
            "estado_observacion": (
                "MUESTRA_INSUFICIENTE" if n < muestra_minima
                else "REVISAR_PERDIDAS_CONTEXTUALES" if neto < 0
                else "SIN_PERDIDA_NETA_EN_VENTANA"
            ),
            "pausa_aplicada": False,
        })
    return sorted(reporte, key=lambda x: (x["neto"], -x["muestra"])), dict(descartes)
