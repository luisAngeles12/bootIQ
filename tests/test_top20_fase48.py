"""Regresiones sin broker del contrato TOP20 completo."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]

def _extraer_funcion(nombre):
    source = (ROOT / "mercado.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == nombre)
    return compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "mercado.py"), "exec")

def _buffer(n=181):
    return [{"from": i * 60} for i in range(n)]

class TopCompletoFase48Tests(unittest.TestCase):
    def setUp(self):
        self.estado = SimpleNamespace(
            velas_cache={str(i): _buffer() for i in range(20)},
            activos_cache=[],
            ultima_actualizacion_activos=0,
            refresh_activos_top_pendiente=[],
            refresh_activos_buffer_indice=0,
            refresh_activos_gap_descartados=set(),
        )
        self.ctx = {"MAX_ACTIVOS_ANALIZAR": 20, "estado": self.estado,
                    "time": SimpleNamespace(time=lambda: 123),
                    "_buffer_velas_integro": lambda x: len(x) == 181}
        for name in ("_seleccionar_top_con_buffers", "_publicar_top_con_buffers"):
            exec(_extraer_funcion(name), self.ctx)

    def test_19_candidatos_no_forman_top_completo(self):
        items = [{"activo": str(i)} for i in range(19)]
        objetivo, top, listos = self.ctx["_seleccionar_top_con_buffers"](items)
        self.assertEqual(objetivo, 20)
        self.assertEqual(len(top), 19)
        self.assertEqual(listos, 19)
        with self.assertRaisesRegex(ValueError, "TOP_INCOMPLETO"):
            self.ctx["_publicar_top_con_buffers"](top)
        self.assertEqual(self.estado.activos_cache, [])

    def test_20_candidatos_con_un_buffer_invalido_no_publican(self):
        items = [{"activo": str(i)} for i in range(20)]
        self.estado.velas_cache["19"] = _buffer(180)
        objetivo, top, listos = self.ctx["_seleccionar_top_con_buffers"](items)
        self.assertEqual(objetivo, 20)
        self.assertEqual(len(top), 19)
        self.assertEqual(listos, 19)
        with self.assertRaises(ValueError):
            self.ctx["_publicar_top_con_buffers"](top)

    def test_20_validos_publican_atomicamente(self):
        items = [{"activo": str(i)} for i in range(20)]
        objetivo, top, listos = self.ctx["_seleccionar_top_con_buffers"](items)
        self.assertEqual((objetivo, len(top), listos), (20, 20, 20))
        result = self.ctx["_publicar_top_con_buffers"](top)
        self.assertEqual(len(result), 20)
        self.assertEqual(len(self.estado.activos_cache), 20)

    def test_bot_no_analiza_top_parcial(self):
        tree = ast.parse((ROOT / "bot.py").read_text(encoding="utf-8"))
        guards = [
            ast.unparse(node.test)
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
        ]
        self.assertGreaterEqual(
            guards.count("len(activos) != MAX_ACTIVOS_ANALIZAR"), 2
        )

if __name__ == "__main__":
    unittest.main()
