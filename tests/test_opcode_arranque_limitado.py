import unittest
from unittest.mock import Mock, patch

import conexion
import estado


class OpcodeArranqueLimitadoTests(unittest.TestCase):
    @patch("conexion.time.sleep")
    @patch("conexion.actualizar_activos_opcode", return_value=False)
    @patch("conexion.IQ_Option")
    def test_arranque_aborta_tras_tres_intentos(self, fabrica, opcode, _sleep):
        previo = estado.Iq
        previo_balance = getattr(estado, "balance_inicial", None)
        iq = Mock()
        iq.connect.return_value = (True, "ok")
        iq.get_balance_mode.return_value = "PRACTICE"
        iq.get_balance.return_value = 9992
        fabrica.return_value = iq
        try:
            with self.assertRaisesRegex(RuntimeError, "ARRANQUE BLOQUEADO"):
                conexion.conectar()
        finally:
            estado.Iq = previo
            estado.balance_inicial = previo_balance
        opcode.assert_called_once_with(max_intentos=3)
        iq.change_balance.assert_called_once_with("PRACTICE")

    @patch("conexion.time.sleep")
    @patch("conexion.actualizar_activos_opcode")
    @patch("conexion.IQ_Option")
    def test_modo_real_aborta_antes_de_opcode(self, fabrica, opcode, _sleep):
        previo = estado.Iq
        iq = Mock()
        iq.connect.return_value = (True, "ok")
        iq.get_balance_mode.return_value = "REAL"
        fabrica.return_value = iq
        try:
            with self.assertRaisesRegex(RuntimeError, "ARRANQUE BLOQUEADO"):
                conexion.conectar()
        finally:
            estado.Iq = previo
        opcode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
