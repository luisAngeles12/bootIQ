"""Observador de decisiones del cerebro por cierres 1m en PRACTICE.

Solo lectura; no contiene rutas a brokers, credenciales ni envio de ordenes.
"""
from contexto_mercado_fresco import consolidar_minutos
from paridad_sombra_practice import diagnosticar_cierre, _segmento_actual


class ObservadorMinutoSombra:
    def __init__(self):
        self._vistos = {}
        self._cerrados = set()
        self._ultimo_reloj = None

    def registrar(self, vela, recibido):
        """Inserta una vela cerrada conocida por primera vez."""
        recibido = int(recibido)
        t = int(vela["from"])
        if recibido < t + 1:
            raise ValueError("VELA_AUN_ABIERTA")
        if self._ultimo_reloj is not None and recibido < self._ultimo_reloj:
            raise ValueError("RELOJ_RETROCEDIO")
        fin = (t // 60 + 1) * 60
        if recibido <= fin and fin not in self._cerrados and t not in self._vistos:
            self._vistos[t] = dict(vela)
        return self.avanzar(recibido)

    def avanzar(self, ahora):
        """Cierra como maximo una vez cada minuto alcanzado por reloj IQ."""
        ahora = int(ahora)
        if self._ultimo_reloj is not None and ahora < self._ultimo_reloj:
            raise ValueError("RELOJ_RETROCEDIO")
        self._ultimo_reloj = ahora
        salidas = []
        pendientes = sorted({t // 60 * 60 + 60 for t in self._vistos
                             if t // 60 * 60 + 60 <= ahora
                             and t // 60 * 60 + 60 not in self._cerrados})
        for fin in pendientes:
            self._cerrados.add(fin)
            minutos = consolidar_minutos(
                {t: v for t, v in self._vistos.items() if t < fin})
            if minutos and minutos[-1]["end"] == fin:
                decision = diagnosticar_cierre(_segmento_actual(minutos))
                if decision["arbitraje"]["operable"] is not False:
                    raise RuntimeError("AUTORIZACION_SOMBRA_INESPERADA")
                salidas.append((fin, decision))
        return salidas
