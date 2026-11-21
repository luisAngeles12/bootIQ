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
        self.assertEqual(len(lineas(r)), 3)

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

    def test_errores_de_datos_no_habilitan_ordenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)/"historial.csv"
            h.write_text("fecha,resultado\nINVALIDO,PERDIDA\n", encoding="utf-8")
            r = evaluar_fuentes(h, Path(tmp)/"sin_sombra.csv")
        self.assertFalse(r["autorizacion"])
        self.assertFalse(r["memoria_productiva_modificada"])


if __name__ == "__main__":
    unittest.main()
