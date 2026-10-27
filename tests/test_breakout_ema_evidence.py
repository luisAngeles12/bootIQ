"""Breakout/retest: la EMA en la explicación debe ser la observada."""
import ast
from collections import defaultdict
from pathlib import Path
import unittest


class BreakoutEmaEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1].joinpath(
            "motor_estrategias.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.fn = next(n for n in cls.tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == "motor_estrategias_profesional")

    def test_no_cambia_activadores_breakout(self):
        self.assertIn('if ctx.get("br_call", 0) == 1:', self.source)
        self.assertIn('if ctx.get("br_put", 0) == -1:', self.source)

    def test_breakout_ema_en_cuatro_contextos(self):
        for clave, activa, sentido in (("br_call", 1, "call"), ("br_put", -1, "put")):
            bloque = next(n for n in ast.walk(self.fn) if isinstance(n, ast.If)
                          and ast.unparse(n.test) == f"ctx.get('{clave}', 0) == {activa}")
            for coincide in (False, True):
                with self.subTest(clave=clave, coincide=coincide):
                    ctx = defaultdict(int, {clave: activa, "rechazo": 0,
                                            "patron": 0, "ema_alcista": coincide,
                                            "ema_bajista": coincide})
                    senales = []
                    def capturar(activo, direccion, patron, puntaje, rsi, razones, contexto):
                        return {"direccion": direccion, "puntaje": puntaje,
                                "razones": razones}
                    env = {"ctx": ctx, "activo": "EURUSD-OTC", "rsi": 50,
                           "razon_presion": "neutral", "patron_call_ok": False,
                           "patron_put_ok": False, "senales": senales,
                           "crear_senal_profesional": capturar}
                    solo = ast.fix_missing_locations(ast.Module(
                        body=[bloque], type_ignores=[]))
                    exec(compile(solo, "<breakout_test>", "exec"), env)
                    self.assertEqual(len(senales), 1)
                    self.assertEqual(senales[0]["puntaje"], 20)
                    self.assertEqual(senales[0]["direccion"], sentido)
                    frase = senales[0]["razones"][2]
                    self.assertEqual("EMA favorece" in frase, coincide)
                    self.assertEqual("EMA no favorece" in frase, not coincide)

    def test_no_autoriza_entrada_en_ausencia_de_activador(self):
        for clave, activa in (("br_call", 1), ("br_put", -1)):
            bloque = next(n for n in ast.walk(self.fn) if isinstance(n, ast.If)
                          and ast.unparse(n.test) == f"ctx.get('{clave}', 0) == {activa}")
            env = {"ctx": defaultdict(int), "senales": []}
            exec(compile(ast.fix_missing_locations(ast.Module(
                body=[bloque], type_ignores=[])), "<breakout_test>", "exec"), env)
            self.assertEqual(env["senales"], [])


if __name__ == "__main__":
    unittest.main()
