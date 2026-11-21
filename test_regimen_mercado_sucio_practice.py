"""Regresion F12.21: regimen SUCIO no debe pasar por calidad NORMAL.

Prueba la funcion real con AST aislado; no conecta a IQ Option.
"""
import ast
import unittest
from pathlib import Path


def _funcion_validar_contexto():
    ruta = Path(__file__).with_name("estrategia.py")
    codigo = ruta.read_text(encoding="utf-8")
    modulo = ast.parse(codigo, filename=str(ruta))
    fn = next(
        node for node in modulo.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "validar_contexto_base"
    )
    aislado = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    env = {}
    exec(compile(aislado, str(ruta), "exec"), env)
    return env[fn.name]


validar = _funcion_validar_contexto()


class RegimenSucioTests(unittest.TestCase):
    def ctx(self, regimen, calidad="NORMAL"):
        return {
            "calidad_mercado": calidad,
            "regimen_mercado": regimen,
            "score_mercado": 85,
            "estado_tendencia": "ALCISTA_NORMAL",
            "mercado_evidencias": [],
        }

    def test_tendencia_sucia_no_pasa_con_calidad_normal(self):
        ctx = self.ctx("TENDENCIA_SUCIA")
        self.assertFalse(validar("EURUSD-OTC", ctx))
        self.assertIn("REGIMEN_SUCIO", ctx["riesgos_contexto_base"])
        self.assertTrue(any(
            x["tipo"] == "regimen_sucio" for x in ctx["mercado_evidencias"]
        ))

    def test_rango_sucio_no_pasa_con_calidad_limpia(self):
        ctx = self.ctx("RANGO_SUCIO", "LIMPIO")
        self.assertFalse(validar("EURUSD-OTC", ctx))

    def test_normal_y_tendencia_limpia_conservan_elegibilidad(self):
        for reg in ("TENDENCIA_LIMPIA", "RANGO_LIMPIO"):
            with self.subTest(regimen=reg):
                self.assertTrue(validar("EURUSD-OTC", self.ctx(reg)))

    def test_calidad_sucia_sigue_bloqueada(self):
        self.assertFalse(validar("EURUSD-OTC", self.ctx("TENDENCIA_LIMPIA", "SUCIO")))

    def test_sin_dato_regimen_no_abre_calidad_no_operable(self):
        self.assertFalse(validar("EURUSD-OTC", self.ctx("SIN_DATOS", "CAOTICO")))


if __name__ == "__main__":
    unittest.main()
