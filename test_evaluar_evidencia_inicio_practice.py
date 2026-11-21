"""Sin IQ: el análisis de inicio no promueve TRAIN ni autoriza operaciones."""
import csv
import tempfile
import unittest
from pathlib import Path

from evaluar_evidencia_inicio_practice import evaluar_fuentes, lineas


class EvidenciaInicioPracticeTests(unittest.TestCase):
    def test_ausencia_de_archivos_no_autoriza(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluar_fuentes(Path(tmp)/"no_history.csv",
                                Path(tmp)/"no_shadow.csv")
        self.assertFalse(r["autorizacion"])
        self.assertFalse(r["memoria_productiva_modificada"])
        self.assertFalse(r["bootstrap_modificado"])
        self.assertEqual(r["cierres"]["estado"], "SIN_ARCHIVO")
        self.assertEqual(r["rechazadas"]["estado"], "SIN_ARCHIVO")
        self.assertEqual(len(lineas(r)), 4)

    def test_archivos_vacios_no_inventan_evidencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)/"historial.csv"
            sh = Path(tmp)/"rechazadas.csv"
            h.write_text("fecha,resultado,order_id\n", encoding="utf-8")
            sh.write_text("id,decision,resultado_hipotetico\n", encoding="utf-8")
            r = evaluar_fuentes(h, sh)
        self.assertFalse(r["autorizacion"])
        self.assertFalse(r["memoria_productiva_modificada"])
        self.assertFalse(r["bootstrap_modificado"])
        self.assertFalse(r["cierres"].get("cumple_oos", False))
        self.assertFalse(r["rechazadas"].get("constancia_hipotetica", False))

    def test_top_train_sin_promocion_test_en_arranque(self):
        resumen = {
            "cierres": {"estado": "SIN_ARCHIVO"},
            "rechazadas": {
                "estado": "HIPOTESIS_EVALUADA",
                "tabla_candidatos_train_con_test": [{
                    "campo": "patron", "valor": "RECHAZO_VENDEDOR",
                    "train": {"winrate_por_minuto_pct": 66.0, "minutos_distintos": 100},
                    "test": {"winrate_por_minuto_pct": 42.0, "minutos_distintos": 50},
                    "diferencia_wr_test_vs_baseline_pct": -8.5,
                }],
            },
        }
        texto = lineas(resumen)[2]
        self.assertIn("RECHAZO_VENDEDOR", texto)
        self.assertIn("TEST 42.0%/50min", texto)
        self.assertIn("no escoger mejor TEST", texto)

    def test_muestra_dias_perdedores_en_arranque(self):
        informe = {
            "cierres": {
                "estado": "ANALISIS_NO_OPERABLE",
                "operaciones_validas": 120,
                "candidatos_train": 1,
                "candidato_train": ["patron", "A"],
                "test_n": 40,
                "test_wr": 65.0,
                "test_neto": 5.0,
                "dias_oos": 3,
                "jornadas_oos_estables": False,
                "dias_oos_fallidos": ["2026-11-19"],
                "cumple_oos": False,
            },
            "rechazadas": {"estado": "SIN_ARCHIVO"},
        }
        texto = lineas(informe)[0]
        self.assertIn("constantes=False", texto)
        self.assertIn("2026-11-19", texto)
        self.assertIn("cumple OOS: False", texto)

    def test_errores_de_datos_no_habilitan_ordenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)/"historial.csv"
            h.write_text("fecha,resultado\nINVALIDO,PERDIDA\n", encoding="utf-8")
            r = evaluar_fuentes(h, Path(tmp)/"sin_sombra.csv")
        self.assertFalse(r["autorizacion"])
        self.assertFalse(r["memoria_productiva_modificada"])


if __name__ == "__main__":
    unittest.main()
