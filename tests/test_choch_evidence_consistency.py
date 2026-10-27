"""El texto de evidencia CHOCH debe reflejar EMA realmente observada."""
import ast
from collections import defaultdict
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

    def test_ejecucion_cuatro_escenarios_no_modifica_puntaje(self):
        fn=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef)
                and n.name=="motor_estrategias_profesional")
        for lado in (-1,1):
            bloque=next(n for n in ast.walk(fn) if isinstance(n,ast.If)
                        and n.lineno>400
                        and ast.unparse(n.test)=="ctx['choch'] == "+str(lado))
            for ema in (False,True):
                with self.subTest(lado=lado, ema=ema):
                    ctx=defaultdict(int,{
                        "choch":lado,"nombre_choch":"CHOCH detectado",
                        "rechazo_hist_razon":"diagnostico",
                        "puntos_patron_vela":2,"pa_direccion":"NEUTRA",
                        "ema_alcista":ema,"ema_bajista":ema,
                    })
                    senales=[]
                    def capturar(activo,direccion,patron,puntaje,rsi,razones,ctx):
                        return {"direccion":direccion,"puntaje":puntaje,
                                "razones":razones}
                    env={"ctx":ctx,"senales":senales,"activo":"EURUSD-OTC",
                         "rsi":50,"razon_presion":"estable",
                         "razon_patron_call":"patron neutro",
                         "razon_patron_put":"patron neutro",
                         "crear_senal_profesional":capturar}
                    solo=ast.fix_missing_locations(ast.Module(
                        body=[bloque],type_ignores=[]))
                    exec(compile(solo,"<choch_test>","exec"),env)
                    self.assertEqual(len(senales),1)
                    self.assertEqual(senales[0]["puntaje"],16)
                    self.assertEqual(senales[0]["direccion"],
                                     "call" if lado==1 else "put")
                    self.assertEqual(
                        "EMA favorece" in senales[0]["razones"][2],ema)

    def test_mantiene_activadores_originales(self):
        self.assertIn('if ctx["choch"] == 1:',self.source)
        self.assertIn('if ctx["choch"] == -1:',self.source)


if __name__=="__main__":
    unittest.main()
