"""Regresion del generador: patrones sin zona no suman puntos.

Se ejecuta la funcion real desde AST sin importar el bot ni conectar IQ.
"""
import ast
import io
import unittest
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path

from price_action import validar_patron_con_contexto


def cargar_motor_aislado():
    ruta = Path(__file__).resolve().parents[1] / "motor_estrategias.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    funcion = next(n for n in arbol.body if isinstance(n, ast.FunctionDef)
                   and n.name == "motor_estrategias_profesional")
    modulo = ast.fix_missing_locations(ast.Module(body=[funcion], type_ignores=[]))
    ambito = {
        "validar_patron_con_contexto": validar_patron_con_contexto,
        "activos_bloqueables": lambda: set(),
        "crear_senal_profesional": lambda activo, direccion, estrategia, puntaje,
                                       rsi, razones, ctx: {
            "activo": activo, "direccion": direccion, "patron": estrategia,
            "puntaje": puntaje, "prioridad": 3, "razon": "; ".join(razones),
        },
        "aplicar_consenso_senal": lambda senal, ctx: senal,
        "score_final_senal_profesional": lambda senal: senal["puntaje"],
    }
    exec(compile(modulo, str(ruta), "exec"), ambito)
    return ambito["motor_estrategias_profesional"], funcion


def contexto(direccion, con_soporte):
    ctx = defaultdict(int)
    precio = 100.0
    ctx.update({
        "activo": "TEST-OTC", "rsi": 50,
        "direccion_presion": "NEUTRA", "razon_presion": "",
        "opens": [100.0]*25, "closes": [precio]*25,
        "highs": [100.4]*25, "lows": [99.6]*25,
        "soporte": precio if con_soporte else 90.0,
        "resistencia": 110.0 if con_soporte else 100.0,
        "vol": 1.0, "nombre_patron": "martillo alcista" if direccion == "call"
                       else "shooting star bajista",
        "patron": 1 if direccion == "call" else -1,
        "puntos_patron_vela": 5,
        "nombre_liquidity_sweep": "sweep sintetico",
        "nombre_rechazo": "sin rechazo", "nombre_choch": "sin choch",
        "liquidity_sweep": 1 if direccion == "call" else -1,
        "cerca_soporte": False, "cerca_resistencia": False,
    })
    return ctx


class PatronContextoPuntajeTests(unittest.TestCase):
    def test_todas_las_bonificaciones_de_patron_exigen_contexto(self):
        _, fn = cargar_motor_aislado()
        for nodo in ast.walk(fn):
            if isinstance(nodo, ast.AugAssign) and isinstance(nodo.value, ast.Subscript):
                sub = nodo.value
                if (isinstance(sub.value, ast.Name) and sub.value.id == "ctx"
                        and isinstance(sub.slice, ast.Constant)
                        and sub.slice.value == "puntos_patron_vela"):
                    self.assertTrue(any(
                        isinstance(p, ast.If)
                        and any(isinstance(n, ast.Name)
                                and n.id in ("patron_call_ok", "patron_put_ok")
                                for n in ast.walk(p.test))
                        and nodo in list(ast.walk(p))
                        for p in ast.walk(fn) if isinstance(p, ast.If)
                    ), f"linea {nodo.lineno}: patron sin contexto")

    def test_punto_de_martillo_no_se_suma_fuera_de_soporte(self):
        motor, _ = cargar_motor_aislado()
        with redirect_stdout(io.StringIO()):
            fuera = motor(contexto("call", False), activos_malos=set())
            dentro = motor(contexto("call", True), activos_malos=set())
        self.assertTrue(fuera)
        self.assertTrue(dentro)
        s_fuera = next(s for s in fuera if s["patron"] == "liquidity sweep alcista")
        s_dentro = next(s for s in dentro if s["patron"] == "liquidity sweep alcista")
        self.assertEqual(s_fuera["puntaje"], 20)
        self.assertGreater(s_dentro["puntaje"], s_fuera["puntaje"])

    def test_shooting_star_fuera_de_resistencia_no_suma(self):
        motor, _ = cargar_motor_aislado()
        con_resistencia = contexto("put", False)
        sin_resistencia = contexto("put", True)
        # put: con_resistencia tiene resistencia en 100, soporte en 90.
        with redirect_stdout(io.StringIO()):
            dentro = motor(con_resistencia, activos_malos=set())
            fuera = motor(sin_resistencia, activos_malos=set())
        s_fuera = next(s for s in fuera if s["patron"] == "liquidity sweep bajista")
        s_dentro = next(s for s in dentro if s["patron"] == "liquidity sweep bajista")
        self.assertEqual(s_fuera["puntaje"], 20)
        self.assertGreater(s_dentro["puntaje"], s_fuera["puntaje"])


if __name__ == "__main__":
    unittest.main()
