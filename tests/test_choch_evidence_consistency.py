"""El texto de evidencia CHOCH debe reflejar EMA realmente observada."""
import ast
import pathlib
import unittest


class ChochEvidenceConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = pathlib.Path(__file__).resolve().parents[1].joinpath(
            "motor_estrategias.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_explica_ema_condicional_para_call_y_put(self):
        expressions=[n for n in ast.walk(self.tree) if isinstance(n, ast.IfExp)]
        cases={(getattr(n.body,"value",None),getattr(n.orelse,"value",None))
               for n in expressions if isinstance(n.body,ast.Constant)
               and isinstance(n.orelse,ast.Constant)}
        self.assertIn(("EMA favorece compra","EMA no favorece compra"),cases)
        self.assertIn(("EMA favorece venta","EMA no favorece venta"),cases)

    def test_choch_no_afirma_confirmacion_sin_validar(self):
        self.assertNotIn('"CHOCH con contexto confirmado"',self.source)
        self.assertEqual(self.source.count(
            '"CHOCH detectado; contexto pendiente de validación"'),2)

    def test_mantiene_activadores_originales(self):
        self.assertIn('if ctx["choch"] == 1:',self.source)
        self.assertIn('if ctx["choch"] == -1:',self.source)


if __name__=="__main__":
    unittest.main()
