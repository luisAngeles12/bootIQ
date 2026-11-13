"""Pruebas de persistencia observacional del regimen maestro (PRACTICE).

No importa bot.py, no abre conexiones ni opera.
"""
import csv
import os
import tempfile
import unittest
from unittest.mock import patch

import historial


class AuditoriaRegimenMercadoTest(unittest.TestCase):
    def test_columnas_de_regimen_presentes(self):
        self.assertIn("regimen_mercado", historial.COLUMNAS_HISTORIAL)
        self.assertIn("razon_regimen", historial.COLUMNAS_HISTORIAL)

    def test_almacena_regimen_sin_modificar_otros_datos(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "historial.csv")
            with patch.object(historial, "HISTORIAL_CSV", ruta):
                historial.asegurar_historial_csv()
                historial.guardar_historial({
                    "fecha": "2026-11-13 13:00:00",
                    "estado": "CERRADA",
                    "order_id": "auditoria-1",
                    "resultado": -25.0,
                    "calidad_mercado": "NORMAL",
                    "regimen_mercado": "TENDENCIA_SUCIA",
                    "razon_regimen": "ruido o fuerza debil",
                })
                with open(ruta, encoding="utf-8-sig", newline="") as f:
                    filas = list(csv.DictReader(f))
                self.assertEqual(len(filas), 1)
                self.assertEqual(filas[0]["regimen_mercado"], "TENDENCIA_SUCIA")
                self.assertEqual(filas[0]["razon_regimen"], "ruido o fuerza debil")
                self.assertEqual(filas[0]["calidad_mercado"], "NORMAL")
                self.assertEqual(float(filas[0]["resultado"]), -25.0)

    def test_migracion_conserva_historial_anterior(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "historial.csv")
            with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["fecha", "estado", "order_id", "resultado", "calidad_mercado"])
                writer.writeheader()
                writer.writerow({
                    "fecha": "2026-11-12 22:00:00",
                    "estado": "CERRADA",
                    "order_id": "antigua-1",
                    "resultado": "-25.0",
                    "calidad_mercado": "NORMAL",
                })
            with patch.object(historial, "HISTORIAL_CSV", ruta):
                historial.asegurar_historial_csv()
                with open(ruta, encoding="utf-8-sig", newline="") as f:
                    filas = list(csv.DictReader(f))
                self.assertEqual(len(filas), 1)
                self.assertEqual(filas[0]["order_id"], "antigua-1")
                self.assertEqual(float(filas[0]["resultado"]), -25.0)
                self.assertIn(filas[0]["regimen_mercado"], ("", None))
                self.assertIn(filas[0]["razon_regimen"], ("", None))


if __name__ == "__main__":
    unittest.main()
