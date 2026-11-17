"""Regresiones fase 9: sin balance inicial valido no arranca el scanner.

No hay conexion real, orden ni consulta de red.
"""
import unittest
import math
from unittest.mock import Mock, patch

import conexion
import estado


class BalanceInicialFase9Tests(unittest.TestCase):
    def setUp(self):
        self.iq_previo = estado.Iq
        self.balance_previo = estado.balance_inicial

    def tearDown(self):
        estado.Iq = self.iq_previo
        estado.balance_inicial = self.balance_previo

    def _ejecutar(self, balance):
        iq = Mock()
        iq.connect.return_value = (True, None)
        iq.get_balance_mode.return_value = "PRACTICE"
        if isinstance(balance, Exception):
            iq.get_balance.side_effect = balance
        else:
            iq.get_balance.return_value = balance
        with patch.object(conexion, "IQ_Option", return_value=iq), patch.object(
            conexion.time, "sleep"
        ), patch.object(
            conexion, "actualizar_activos_opcode", return_value=True
        ) as opcode:
            if isinstance(balance, Exception) or balance is None or not math.isfinite(float(balance)) or balance < 0:
                with self.assertRaisesRegex(RuntimeError, "ARRANQUE BLOQUEADO: balance inicial"):
                    conexion.conectar()
                opcode.assert_not_called()
            else:
                self.assertTrue(conexion.conectar())
                opcode.assert_called_once()
        return iq

    def test_error_de_balance_bloquea_arranque_antes_del_scanner(self):
        self._ejecutar(TimeoutError("IQ sin respuesta"))
        self.assertIsNone(estado.balance_inicial)

    def test_balance_none_y_nan_no_se_interpretan_como_cero(self):
        for balance in (None, float("nan"), float("inf"), float("-inf"), -1):
            with self.subTest(balance=balance):
                self._ejecutar(balance)
                self.assertIsNone(estado.balance_inicial)

    def test_balance_practice_valido_conserva_arranque(self):
        iq = self._ejecutar(1000.0)
        self.assertEqual(estado.balance_inicial, 1000.0)
        iq.get_balance.assert_called_once()


if __name__ == "__main__":
    unittest.main()
