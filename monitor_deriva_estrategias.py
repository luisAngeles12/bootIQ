"""Monitor cronologico de deterioro por patron; solo telemetria PRACTICE.

No cambia decisiones, cooldowns operativos, umbrales ni frecuencia.
Recibe exclusivamente cierres ya persistidos; no consulta el historial
en cada orden ni presume que una ventana corta demuestre ventaja.
"""
from collections import defaultdict, deque
import csv
import math
from pathlib import Path

VENTANA_DIAGNOSTICA = 8


class MonitorDerivaSombra:
    def __init__(self):
        self._resultados = defaultdict(
            lambda: deque(maxlen=2 * VENTANA_DIAGNOSTICA)
        )
        self._ids = set()

    def registrar_cierre(self, patron, resultado, order_id):
        patron = str(patron or "").strip()
        oid = str(order_id or "").strip()
        if not patron or not oid or oid in self._ids:
            return None
        try:
            valor = float(resultado)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(valor):
            return None

        self._ids.add(oid)
        resultados = self._resultados[patron]
        resultados.append(valor)

        datos = {
            "patron": patron,
            "observaciones_recientes": len(resultados),
            "ventana": VENTANA_DIAGNOSTICA,
            "modo": "SHADOW_SIN_AUTORIDAD",
            "estado": "MUESTRA_INSUFICIENTE",
            "cooldown_activado": False,
        }

        if len(resultados) < 2 * VENTANA_DIAGNOSTICA:
            return datos

        ventana = list(resultados)
        anterior = ventana[:VENTANA_DIAGNOSTICA]
        reciente = ventana[VENTANA_DIAGNOSTICA:]
        media_anterior = sum(anterior) / VENTANA_DIAGNOSTICA
        media_reciente = sum(reciente) / VENTANA_DIAGNOSTICA
        deterioro = media_anterior > 0 and media_reciente < 0

        datos.update({
            "estado": (
                "DETERIORO_CANDIDATO"
                if deterioro else "SIN_DETERIORO_DETECTADO"
            ),
            "expectativa_anterior": round(media_anterior, 4),
            "expectativa_reciente": round(media_reciente, 4),
            "wins_recientes": sum(x > 0 for x in reciente),
            "losses_recientes": sum(x < 0 for x in reciente),
        })
        return datos


_MONITOR = MonitorDerivaSombra()


def observar_cierre_sombra(patron, resultado, order_id):
    """Actualiza memoria diagnostica tras persistir el cierre oficial."""
    return _MONITOR.registrar_cierre(patron, resultado, order_id)

def reconstruir_monitor_desde_historial(ruta):
    """Reconstruye una sola vez, fuera de la ventana operativa.

    La fuente de verdad son cierres ya persistidos en historial_bot.csv.
    Un replay nunca escribe ni cambia autorizaciones. Se sustituye el
    monitor global solo despues de leer todo el archivo exitosamente.
    """
    global _MONITOR
    candidato = MonitorDerivaSombra()
    cantidad = 0
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            if str(fila.get("estado", "")).strip().upper() != "CERRADA":
                continue
            if candidato.registrar_cierre(
                fila.get("patron"), fila.get("resultado"), fila.get("order_id")
            ) is not None:
                cantidad += 1
    _MONITOR = candidato
    return cantidad
