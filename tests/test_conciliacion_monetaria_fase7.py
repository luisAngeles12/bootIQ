"""Contrato actual de conciliación TURBO: resultado neto y fallback IQ.

Documenta límites de normalización SIN cambiar el comportamiento operativo.
No conecta al broker ni modifica archivos.
"""
import time
import unittest
from unittest.mock import patch, Mock

import operaciones
import estado


class ConciliacionMonetariaFase7Tests(unittest.TestCase):
    def _op(self):
        return {
            "order_id": "123456",
            "activo": "EURUSD",
            "tipo": "turbo",
            "hora_apertura": time.time() - 300,
        }

    def test_resultado_directo_documenta_transformacion_actual(self):
        casos = (
            ("WIN_NORMAL", 20.75, 20.75),
            ("WIN_SUPERIOR_LIMITE", 35.0, 21.75),
            ("LOSS_NORMAL", -25.0, -25.0),
            ("LOSS_INFERIOR_LIMITE", -30.0, -25.0),
            ("EMPATE", 0.0, 0.0),
        )
        for nombre, bruto, esperado in casos:
            with self.subTest(caso=nombre), patch.object(
                operaciones, "check_win_v3_con_timeout", return_value=bruto
            ), patch.object(
                operaciones, "obtener_resultado_historial_turbo_con_timeout",
                side_effect=AssertionError("No consultar fallback si hay resultado")
            ):
                obtenido = operaciones.obtener_resultado_operacion(self._op())
                self.assertEqual(obtenido, esperado)

    def test_fallback_usa_solo_posicion_cerrada_con_id_coincidente(self):
        iq = Mock()
        iq.get_position_history_v2.return_value = (True, {
            "positions": [
                {"external_id": "999", "status": "closed", "pnl_realized": 70},
                {"external_id": "123456", "status": "open", "pnl_realized": 70},
                {"external_id": "123456", "status": "closed", "pnl_realized": 20.75},
            ]
        })
        with patch.object(estado, "Iq", iq):
            resultado = operaciones.obtener_resultado_historial_turbo_con_timeout(
                "123456", timeout=2
            )
        self.assertEqual(resultado, 20.75)
        iq.get_position_history_v2.assert_called_once()

    def test_fallback_no_inventa_resultado_sin_cierre_correspondiente(self):
        iq = Mock()
        iq.get_position_history_v2.return_value = (True, {
            "positions": [
                {"external_id": "123456", "status": "open", "pnl_realized": 20.75},
                {"external_id": "999", "status": "closed", "pnl_realized": 20.75},
            ]
        })
        with patch.object(estado, "Iq", iq):
            resultado = operaciones.obtener_resultado_historial_turbo_con_timeout(
                "123456", timeout=2
            )
        self.assertIsNone(resultado)

    def test_fallback_se_usa_solo_si_socket_no_devuelve_resultado(self):
        with patch.object(
            operaciones, "check_win_v3_con_timeout", return_value=None
        ) as socket, patch.object(
            operaciones, "obtener_resultado_historial_turbo_con_timeout",
            return_value=20.75
        ) as historial:
            resultado = operaciones.obtener_resultado_operacion(self._op())
        self.assertEqual(resultado, 20.75)
        socket.assert_called_once()
        historial.assert_called_once()


if __name__ == "__main__":
    unittest.main()
