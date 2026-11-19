"""Diagnostico aislado F11: no inventar datos de conciliacion."""
import csv
import tempfile
import unittest
from pathlib import Path
from diagnosticar_ledger_fases11_12_practice import diagnosticar

class CompatibilidadLedgerTest(unittest.TestCase):
    def escribir(self, carpeta, cols, filas):
        ruta = Path(carpeta) / "historial.csv"
        with ruta.open("w", encoding="utf-8", newline="") as a:
            w = csv.DictWriter(a, fieldnames=cols)
            w.writeheader()
            w.writerows(filas)
        return ruta

    def test_archivo_ausente_falla_cerrado(self):
        with tempfile.TemporaryDirectory() as d:
            r = diagnosticar(Path(d) / "falta.csv")
        self.assertFalse(r["apto_para_evaluar"])

    def test_historial_oficial_no_se_convierte_en_cierre_inventado(self):
        columnas = ["fecha", "estado", "order_id", "resultado",
                    "modo_cuenta_configurado", "patron", "familia_setup"]
        with tempfile.TemporaryDirectory() as d:
            p = self.escribir(d, columnas, [{
                "fecha": "2026-11-18T17:00:00+00:00",
                "estado": "CERRADA", "order_id": "001",
                "resultado": "20.75", "modo_cuenta_configurado": "PRACTICE",
                "patron": "CHOCH", "familia_setup": "REVERSAL",
            }])
            r = diagnosticar(p)
        self.assertEqual(r["cerradas_marcadas"], 1)
        self.assertFalse(r["apto_para_evaluar"])
        self.assertIn("fecha_cierre", r["faltantes"])
        self.assertIn("neto", r["faltantes"])
        self.assertIn("tipo_cuenta", r["faltantes"])

    def test_ledger_esquematicamente_completo_no_certifica_broker(self):
        cols = ["order_id", "fecha_cierre", "resultado",
                "neto", "familia", "tipo_cuenta"]
        with tempfile.TemporaryDirectory() as d:
            p = self.escribir(d, cols, [{
                "order_id": "abc", "fecha_cierre": "2026-11-18T17:00:00+00:00",
                "resultado": "WIN", "neto": "20.75",
                "familia": "resistencia", "tipo_cuenta": "PRACTICE",
            }])
            r = diagnosticar(p)
        self.assertTrue(r["apto_para_evaluar"])
        self.assertFalse(r["validacion_prospectiva_confirmada"])
        self.assertFalse(r["autoriza_real"])

    def test_csv_vacio_no_certifica(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.escribir(d, ["order_id", "fecha_cierre", "resultado",
                                   "neto", "familia", "tipo_cuenta"], [])
            r = diagnosticar(p)
        self.assertFalse(r["apto_para_evaluar"])

    def test_encabezado_duplicado_no_certifica(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "historial.csv"
            p.write_text("order_id,order_id,resultado\n1,1,WIN\n",
                         encoding="utf-8")
            r = diagnosticar(p)
        self.assertEqual(r["estado"], "ENCABEZADOS_DUPLICADOS")

if __name__ == "__main__":
    unittest.main()
