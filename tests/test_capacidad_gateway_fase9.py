"""Fase 9: límite de exposición en la puerta común de envío.

Solo mocks, nunca conecta con IQ Option ni abre compras reales.
"""
import unittest
from unittest.mock import Mock, patch

import estado
from operaciones import abrir_operacion


class CapacidadGatewayFase9Tests(unittest.TestCase):
    def setUp(self):
        self.iq_anterior = estado.Iq
        self.operaciones_anteriores = estado.operaciones_abiertas
        self.cooldown_anterior = estado.cooldown_activos
        self.timestamp = 1794950427.0
        iq = Mock()
        iq.get_server_timestamp.return_value = self.timestamp
        iq.buy.return_value = (False, "rechazada_mock")
        estado.Iq = iq
        estado.operaciones_abiertas = []
        estado.cooldown_activos = {}
        self.iq = iq

    def tearDown(self):
        estado.Iq = self.iq_anterior
        estado.operaciones_abiertas = self.operaciones_anteriores
        estado.cooldown_activos = self.cooldown_anterior

    def _senal(self, activo="EURUSD", decision="OPERAR"):
        return {
            "cerebro_unico_decision": decision,
            "protocolo_confirmado": decision == "OPERAR_CON_PROTOCOLO",
            "activo": activo,
            "direccion": "call",
            "tipo": "turbo",
            "vela_senal_from": int(self.timestamp // 60 - 1) * 60,
        }

    def _ocupada(self, activo):
        return {"activo": activo, "expiracion_iq": self.timestamp + 60}

    def test_cinco_posiciones_vivas_bloquean_envio_directo(self):
        estado.operaciones_abiertas = [
            self._ocupada("ASSET_" + str(i)) for i in range(5)
        ]
        self.assertFalse(abrir_operacion(self._senal()))
        self.iq.buy.assert_not_called()

    def test_mismo_activo_bloquea_duplicado(self):
        estado.operaciones_abiertas = [self._ocupada("EURUSD")]
        self.assertFalse(abrir_operacion(self._senal()))
        self.iq.buy.assert_not_called()

    def test_cinco_posiciones_vivas_bloquean_protocolo(self):
        estado.operaciones_abiertas = [
            self._ocupada("ASSET_" + str(i)) for i in range(5)
        ]
        senal = self._senal(decision="OPERAR_CON_PROTOCOLO")
        senal["protocolo_live_vela_entrada_from"] = senal["vela_senal_from"]
        self.assertFalse(abrir_operacion(senal))
        self.iq.buy.assert_not_called()

    def test_posiciones_expiradas_no_consumen_cupo(self):
        estado.operaciones_abiertas = [
            {"activo": "EURUSD", "expiracion_iq": self.timestamp - 60},
        ]
        self.assertFalse(abrir_operacion(self._senal()))
        self.iq.buy.assert_called_once()

    def test_cuatro_posiciones_permiten_quinta(self):
        estado.operaciones_abiertas = [
            self._ocupada("ASSET_" + str(i)) for i in range(4)
        ]
        self.assertFalse(abrir_operacion(self._senal()))
        self.iq.buy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
