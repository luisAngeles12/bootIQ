"""Defensa final de tiempo entre comprobacion de vela y envio de IQ.

Pruebas aisladas: no importan broker, config ni credenciales, ni conectan.
"""
import ast
import math
import unittest
from pathlib import Path


def cargar_funcion():
    ruta = Path(__file__).resolve().parents[1] / "operaciones.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    helper = next(
        n for n in arbol.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "_paridad_causal_sigue_vigente"
    )
    env = {
        "math": math,
        "CANDLE_TIME": 60,
        "VENTANA_ENTRADA_INICIO": 0,
        "VENTANA_ENTRADA_FIN": 30,
        "MARGEN_ENVIO_IQ_SEGUNDOS": 2,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[helper], type_ignores=[]
    )), str(ruta), "exec"), env)
    return env["_paridad_causal_sigue_vigente"], arbol


class ParidadAntesDeBuyTest(unittest.TestCase):
    def setUp(self):
        self.check, self.ast = cargar_funcion()
        self.timestamp = 1800000007.0
        self.vela = (int(self.timestamp // 60) - 1) * 60

    def test_envio_a_tiempo_sin_nueva_consulta_broker(self):
        self.assertTrue(self.check(self.timestamp, 100., 100.4, self.vela))
        self.assertTrue(self.check(self.timestamp, 100., 110., self.vela))

    def test_llegada_tardia_antes_del_buy_no_cruza_margen(self):
        self.assertTrue(self.check(self.timestamp, 100., 120.9, self.vela))
        self.assertFalse(self.check(self.timestamp, 100., 121., self.vela))
        self.assertFalse(self.check(self.timestamp, 100., 129., self.vela))

    def test_no_acepta_nueva_vela_con_senal_antigua(self):
        self.assertFalse(self.check(self.timestamp, 100., 161., self.vela))
        self.assertFalse(self.check(self.timestamp, 100., 220., self.vela))

    def test_fallo_temporal_se_cierra_seguro(self):
        for server, inicio, final in (
            (float("nan"), 100, 101),
            (float("inf"), 100, 101),
            (self.timestamp, 100, float("nan")),
            (self.timestamp, 102, 101),
            (None, 100, 101),
            (0, 100, 101),
        ):
            with self.subTest(server=server, inicio=inicio, final=final):
                self.assertFalse(self.check(server, inicio, final, self.vela))

    def test_guardia_practice_no_depende_de_origen_bootstrap(self):
        fn = next(
            n for n in self.ast.body
            if isinstance(n, ast.FunctionDef) and n.name == "abrir_operacion"
        )
        guardias = [
            n for n in ast.walk(fn) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "cuenta_practice_verificada"
        ]
        self.assertEqual(len(guardias), 1)
        guardia = guardias[0]
        # Ninguna ruta condicional basada en bootstrap debe rodear la
        # comprobacion de cuenta: aplica a directa y protocolo.
        for nodo in ast.walk(fn):
            if isinstance(nodo, ast.If) and guardia in ast.walk(nodo):
                self.assertNotIn(
                    "bootstrap_practice_sin_historial",
                    ast.unparse(nodo.test)
                )
        buy_lines = [
            n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call)
            and ast.unparse(n.func) in (
                "estado.Iq.buy", "estado.Iq.buy_digital_spot_v2"
            )
        ]
        self.assertTrue(all(guardia.lineno < ln for ln in buy_lines))

    def test_integracion_revalida_despues_de_cuenta_y_antes_de_buy(self):
        fn = next(
            n for n in self.ast.body
            if isinstance(n, ast.FunctionDef) and n.name == "abrir_operacion"
        )
        llamadas = [
            (n.lineno, ast.unparse(n.func))
            for n in ast.walk(fn) if isinstance(n, ast.Call)
        ]
        cuenta = [lin for lin, f in llamadas if f == "cuenta_practice_verificada"]
        paridad = [lin for lin, f in llamadas
                   if f == "_paridad_causal_sigue_vigente"]
        buys = [lin for lin, f in llamadas
                if f in ("estado.Iq.buy", "estado.Iq.buy_digital_spot_v2")]
        self.assertEqual(len(paridad), 1)
        self.assertEqual(len(cuenta), 1)
        self.assertEqual(len(buys), 2)
        self.assertLess(cuenta[0], paridad[0])
        self.assertTrue(all(paridad[0] < lin for lin in buys))


if __name__ == "__main__":
    unittest.main()
