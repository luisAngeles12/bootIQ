"""Evaluación en sombra para futuras pausas por estrategia y mercado.

Nunca escribe cooldowns, no consulta al bróker y no veta operaciones.
Solo considera operaciones efectivamente cerradas con resultado monetario.
"""

from collections import defaultdict, deque
from datetime import datetime, timezone
from math import isfinite


def _fecha(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        pass
    if not isinstance(valor, str):
        return None
    try:
        fecha = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.timestamp()
    except (ValueError, OverflowError, OSError):
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


def registrar_cierre_sombra(registro, operacion, resultado, *, max_por_contexto=100):
    """Actualiza telemetría acotada tras un cierre persistido.

    No consulta disco, no crea bloqueos y no modifica la operación original.
    El llamador es responsable de invocarla una sola vez por cierre confirmado.
    """
    if not isinstance(registro, dict) or not isinstance(operacion, dict):
        return False
    if not isinstance(max_por_contexto, int) or max_por_contexto < 1:
        return False
    clave = tuple(str(operacion.get(k) or "").strip().upper() for k in ("patron", "tipo_mercado", "direccion"))
    if not all(clave):
        return False
    try:
        pnl = float(resultado)
    except (TypeError, ValueError):
        return False
    if not isfinite(pnl) or pnl == 0:
        return False
    serie = registro.get(clave)
    if not isinstance(serie, deque) or serie.maxlen != max_por_contexto:
        serie = deque(serie or (), maxlen=max_por_contexto)
        registro[clave] = serie
    serie.append(pnl)
    return True


def resumen_cierre_sombra(registro, operacion):
    """Devuelve un resumen descriptivo; jamás una autorización o veto."""
    if not isinstance(registro, dict) or not isinstance(operacion, dict):
        return None
    clave = tuple(str(operacion.get(k) or "").strip().upper() for k in ("patron", "tipo_mercado", "direccion"))
    serie = registro.get(clave)
    if not isinstance(serie, deque) or not serie:
        return None
    n = len(serie)
    wins = sum(valor > 0 for valor in serie)
    return {
        "estrategia": clave[0], "mercado": clave[1], "direccion": clave[2],
        "n": n, "wins": wins, "losses": n - wins,
        "neto": round(sum(serie), 2), "wr": round(100 * wins / n, 2),
        "solo_observacion": True,
    }
