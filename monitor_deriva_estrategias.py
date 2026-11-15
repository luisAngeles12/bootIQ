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
        # Separa el comportamiento del patron por regimen de mercado.
        # La memoria general original permanece intacta.
        self._resultados_regimen = defaultdict(
            lambda: deque(maxlen=2 * VENTANA_DIAGNOSTICA)
        )
        self._ids = set()

    @staticmethod
    def _resumir_ventanas(resultados):
        if len(resultados) < 2 * VENTANA_DIAGNOSTICA:
            return {"estado": "MUESTRA_INSUFICIENTE"}
        ventana = list(resultados)
        anterior = ventana[:VENTANA_DIAGNOSTICA]
        reciente = ventana[VENTANA_DIAGNOSTICA:]
        media_anterior = sum(anterior) / VENTANA_DIAGNOSTICA
        media_reciente = sum(reciente) / VENTANA_DIAGNOSTICA
        deterioro = media_anterior > 0 and media_reciente < 0
        return {
            "estado": (
                "DETERIORO_CANDIDATO" if deterioro
                else "SIN_DETERIORO_DETECTADO"
            ),
            "expectativa_anterior": round(media_anterior, 4),
            "expectativa_reciente": round(media_reciente, 4),
            "wins_recientes": sum(x > 0 for x in reciente),
            "losses_recientes": sum(x < 0 for x in reciente),
        }

    def registrar_cierre(self, patron, resultado, order_id, regimen_mercado=None):
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
        # SIN_DATOS no se agrupa en un regimen ficticio: evita
        # comparar mercados desconocidos como si fueran equivalentes.
        regimen = str(regimen_mercado or "").strip().upper()
        resultados_regimen = None
        if regimen:
            resultados_regimen = self._resultados_regimen[(patron, regimen)]
            resultados_regimen.append(valor)

        datos = {
            "patron": patron,
            "observaciones_recientes": len(resultados),
            "ventana": VENTANA_DIAGNOSTICA,
            "modo": "SHADOW_SIN_AUTORIDAD",
            "estado": "MUESTRA_INSUFICIENTE",
            "cooldown_activado": False,
        }

        datos.update(self._resumir_ventanas(resultados))
        datos["regimen_mercado"] = regimen or "SIN_DATOS"
        datos["observaciones_regimen"] = (
            len(resultados_regimen) if resultados_regimen is not None else 0
        )
        diagnostico_regimen = (
            self._resumir_ventanas(resultados_regimen)
            if resultados_regimen is not None else {"estado": "SIN_DATOS_REGIMEN"}
        )
        datos["estado_regimen"] = diagnostico_regimen["estado"]
        for clave, valor_regimen in diagnostico_regimen.items():
            if clave != "estado":
                datos["regimen_" + clave] = valor_regimen
        return datos


_MONITOR = MonitorDerivaSombra()


def observar_cierre_sombra(patron, resultado, order_id, regimen_mercado=None):
    """Actualiza memoria diagnostica tras persistir el cierre oficial."""
    return _MONITOR.registrar_cierre(
        patron, resultado, order_id, regimen_mercado=regimen_mercado
    )

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
                fila.get("patron"), fila.get("resultado"), fila.get("order_id"),
                regimen_mercado=fila.get("regimen_mercado"),
            ) is not None:
                cantidad += 1
    _MONITOR = candidato
    return cantidad
