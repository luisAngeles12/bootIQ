"""Contrato de medicion de envio: pruebas estaticas, sin broker.

Garantiza que la medicion no vuelva a incluir el preflight PRACTICE y
que no se traslade la apertura del cupo antes del acuse del broker.
"""
import ast
import unittest
from pathlib import Path


class LatenciaPracticeTests(unittest.TestCase):
    def test_cronometro_despues_de_preflight_y_antes_de_buy(self):
        codigo = Path(__file__).with_name("operaciones.py").read_text(encoding="utf-8")
        inicio = codigo.index("    # Medir desde el inicio del envío al broker")
        cuenta = codigo.index("if not cuenta_practice_verificada(")
        cupo = codigo.index("if not admite_apertura():")
        paridad = codigo.index("if not _paridad_causal_sigue_vigente(")
        antes = codigo.index("    tiempo_antes = time.time()", inicio)
        compra = codigo.index("estado.Iq.buy(", antes)
        registro = codigo.index("registrar_apertura(order_id)", compra)
        despues = codigo.index("    tiempo_despues = time.time()", registro)
        self.assertLess(cuenta, cupo)
        self.assertLess(cupo, paridad)
        self.assertLess(paridad, inicio)
        self.assertLess(inicio, antes)
        self.assertLess(antes, compra)
        self.assertLess(compra, registro)
        self.assertLess(registro, despues)
        ast.parse(codigo)


if __name__ == "__main__":
    unittest.main()
