"""Regresion offline: observar PRACTICE no equivale a autorizar ordenes."""
import tempfile
import unittest
from pathlib import Path

from preflight_practice_v3 import evaluar_preflight


class PreparacionPracticeTests(unittest.TestCase):
    def cfg(self):
        return {
            "MODO_CUENTA": "PRACTICE",
            "CONTROL_BLOQUES_20_PRACTICE": True,
            "PERMITIR_BOOTSTRAP_SIN_MEMORIA": False,
        }

    def test_memoria_ausente_solo_permite_observar(self):
        with tempfile.TemporaryDirectory() as d:
            r = evaluar_preflight(d, config=self.cfg())
            self.assertTrue(r["preparado_para_observacion_practice"])
            self.assertFalse(r["preparado_para_aperturas_practice"])
            self.assertIn("MEMORIA_ESTADISTICA_OFICIAL_NO_UTILIZABLE",
                          r["bloqueos_practica_operativa"])
            self.assertIn("VALIDACION_OOS_Y_PNL_NO_CERTIFICADA",
                          r["bloqueos_practica_operativa"])

    def test_memoria_presente_no_certifica_rentabilidad(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "memoria.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")
            r = evaluar_preflight(d, ruta_memoria=path, config=self.cfg())
            self.assertTrue(r["memoria_oficial_presente"])
            self.assertFalse(r["preparado_para_aperturas_practice"])
            self.assertFalse(r["rentabilidad_validada"])

    def test_real_bloquea_incluso_observacion_practice(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self.cfg()
            cfg["MODO_CUENTA"] = "REAL"
            r = evaluar_preflight(d, config=cfg)
            self.assertFalse(r["preparado_para_observacion_practice"])
            self.assertIn("CONFIGURACION_PRACTICE_INSEGURA",
                          r["bloqueos_practica_operativa"])


if __name__ == "__main__":
    unittest.main()
