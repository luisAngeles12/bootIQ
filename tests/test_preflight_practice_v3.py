"""Preflight offline sin credenciales, broker ni alteracion de operaciones."""
import ast
import tempfile
import unittest
from pathlib import Path
from preflight_practice_v3 import evaluar_preflight


CONFIG_SEGURO = {
    "MODO_CUENTA": "PRACTICE",
    "CONTROL_BLOQUES_20_PRACTICE": True,
    "PERMITIR_BOOTSTRAP_SIN_MEMORIA": False,
}


class PreflightPracticeV3Tests(unittest.TestCase):
    def test_memoria_ausente_no_autoriza(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluar_preflight(tmp, config=CONFIG_SEGURO)
            self.assertTrue(r["auditoria_sombra_posible"])
            self.assertIn("MEMORIA_OFICIAL_AUSENTE", r["motivos"])
            self.assertFalse(r["operativa_autorizada"])

    def test_rechaza_real_aunque_haya_memoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "memoria.csv"
            p.write_text("clave,total\nA,20\n", encoding="utf-8")
            config = dict(CONFIG_SEGURO, MODO_CUENTA="REAL")
            r = evaluar_preflight(tmp, ruta_memoria=p, config=config)
            self.assertIn("MODO_CUENTA_NO_PRACTICE", r["motivos"])
            self.assertFalse(r["auditoria_sombra_posible"])

    def test_rechaza_bootstrap_no_validado(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = dict(CONFIG_SEGURO, PERMITIR_BOOTSTRAP_SIN_MEMORIA=True)
            r = evaluar_preflight(tmp, config=config)
            self.assertIn("BOOTSTRAP_SIN_MEMORIA_ACTIVO", r["motivos"])
            self.assertFalse(r["auditoria_sombra_posible"])

    def test_no_promueve_memoria_train(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "experimentos_fase5" / "memoria_ejecutadas_train_candidata.csv"
            p.parent.mkdir()
            p.write_text("clave,total\nA,20\n", encoding="utf-8")
            r = evaluar_preflight(tmp, ruta_memoria=p, config=CONFIG_SEGURO)
            self.assertIn("MEMORIA_EXPERIMENTAL_COMO_OFICIAL", r["motivos"])
            self.assertTrue(r["memoria_experimental_promovida"])
        self.assertFalse(r["seguridad_practice"])
        self.assertFalse(r["auditoria_sombra_posible"])
            self.assertFalse(r["operativa_autorizada"])

    def test_preflight_memoria_ausente_permite_solo_sombra(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluar_preflight(tmp, config=CONFIG_SEGURO)
            self.assertTrue(r["seguridad_practice"])
            self.assertTrue(r["auditoria_sombra_posible"])
            self.assertFalse(r["memoria_oficial_presente"])
            self.assertFalse(r["operativa_autorizada"])

    def test_memoria_presente_no_certifica_rentabilidad(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "oficial.csv"
            p.write_text("clave,total\nA,20\n", encoding="utf-8")
            r = evaluar_preflight(tmp, ruta_memoria=p, config=CONFIG_SEGURO)
            self.assertTrue(r["memoria_oficial_presente"])
            self.assertFalse(r["rentabilidad_validada"])
            self.assertFalse(r["operativa_autorizada"])

    def test_bot_verifica_preflight_antes_de_conectar(self):
        raiz = Path(__file__).resolve().parents[1]
        arbol = ast.parse((raiz / "bot.py").read_text(encoding="utf-8"))
        main = next(n for n in arbol.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        llamadas = [
            (n.func.id, n.lineno)
            for n in ast.walk(main)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in ("evaluar_preflight", "conectar")
        ]
        self.assertEqual(len([x for x in llamadas if x[0] == "evaluar_preflight"]), 1)
        self.assertEqual(len([x for x in llamadas if x[0] == "conectar"]), 1)
        pre = next(l for f, l in llamadas if f == "evaluar_preflight")
        conexion = next(l for f, l in llamadas if f == "conectar")
        self.assertLess(pre, conexion)

    def test_bloques_20_deben_estar_activos(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = dict(CONFIG_SEGURO, CONTROL_BLOQUES_20_PRACTICE=False)
            r = evaluar_preflight(tmp, config=cfg)
            self.assertIn("CONTROL_BLOQUES_20_INACTIVO", r["motivos"])
            self.assertFalse(r["auditoria_sombra_posible"])


if __name__ == "__main__":
    unittest.main()
