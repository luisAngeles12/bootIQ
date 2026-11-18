"""Price Action nunca debe autorizar una diagnostico tecnico fallido.

Reproduce rutas de error con velas artificiales, sin broker ni trading.
"""
import unittest
from unittest.mock import patch

import price_action as pa


def velas(n=6, rango=1.0):
    opens = [100.0]*n
    closes = [100.0]*n
    highs = [100.0+rango]*n
    lows = [100.0-rango]*n
    return opens, closes, highs, lows


class FailClosedPriceActionTest(unittest.TestCase):
    def diagnosticar(self, direccion, datos):
        return pa.diagnostico_accion_precio_zona(
            direccion, *datos, soporte=95.0, resistencia=105.0, vol=1.0
        )

    def test_velas_insuficientes_no_permiten_entrada(self):
        x = self.diagnosticar("call", velas(4))
        self.assertEqual(x["accion"], "SIN_DATOS")
        self.assertIs(x["permite"], False)

    def test_rango_invalido_no_permite_entrada(self):
        x = self.diagnosticar("put", velas(6, rango=0))
        self.assertEqual(x["accion"], "RANGO_INVALIDO")
        self.assertIs(x["permite"], False)

    def test_direccion_invalida_no_permite_entrada(self):
        with patch.object(pa, "lectura_avanzada_price_action",
                          return_value={"tipo": "MERCADO_MIXTO", "direccion": "NEUTRA"}):
            x = self.diagnosticar("sideways", velas())
        self.assertEqual(x["accion"], "DIRECCION_INVALIDA")
        self.assertIs(x["permite"], False)

    def test_excepcion_no_se_traduce_en_permiso(self):
        with patch.object(pa, "lectura_avanzada_price_action",
                          side_effect=RuntimeError("lectura corrupta")):
            x = self.diagnosticar("put", velas())
        self.assertEqual(x["accion"], "ERROR")
        self.assertIs(x["permite"], False)

    def test_contexto_valido_sigue_funcionando(self):
        with patch.object(pa, "lectura_avanzada_price_action",
                          return_value={"tipo": "MERCADO_MIXTO", "direccion": "NEUTRA"}):
            x = self.diagnosticar("call", velas())
        self.assertEqual(x["accion"], "CALL_ZONA_NEUTRA")
        self.assertIs(x["permite"], True)


if __name__ == "__main__":
    unittest.main()
