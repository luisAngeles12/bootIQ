"""Pruebas sintéticas para inventario F5.9, sin broker ni históricos reales."""
import csv
import tempfile
import unittest
from pathlib import Path

from auditar_datasets_fase59_practice import inventariar


class InventarioDatasetTest(unittest.TestCase):
    def crear(self, carpeta, nombre, n=200, paso=60):
        ruta = Path(carpeta) / nombre
        with ruta.open("w", encoding="utf-8", newline="") as archivo:
            writer = csv.DictWriter(archivo, fieldnames=["from", "open", "close", "max", "min"])
            writer.writeheader()
            for i in range(n):
                writer.writerow({"from": 1760000000 + i * paso, "open": 1,
                                 "close": 2, "max": 3, "min": 0})
        return ruta

    def test_directorio_inexistente_no_inventa_datasets(self):
        with tempfile.TemporaryDirectory() as d:
            r = inventariar(Path(d) / "ausente")
        self.assertEqual(r["estado"], "SIN_DATOS_ACTUALES")
        self.assertEqual(r["total_csv"], 0)

    def test_minimo_200_y_duplicados_identicos(self):
        with tempfile.TemporaryDirectory() as d:
            self.crear(d, "valido.csv")
            self.crear(d, "copia.csv")
            self.crear(d, "corto.csv", 199)
            r = inventariar(d)
        self.assertEqual(r["total_csv"], 3)
        self.assertEqual(r["cargables_minimo"], 2)
        self.assertEqual(len(r["duplicados_identicos"]), 1)

    def test_gap_detectado_sin_eliminar_archivo_cargable(self):
        with tempfile.TemporaryDirectory() as d:
            self.crear(d, "gaps.csv", paso=120)
            r = inventariar(d)
        self.assertEqual(r["cargables_minimo"], 1)
        self.assertEqual(r["con_continuidad_completa"], 0)
        self.assertEqual(r["archivos"][0]["saltos_temporales"], 199)

    def test_fila_truncada_se_rechaza(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.crear(d, "incompleto.csv")
            with p.open("a", encoding="utf-8") as f:
                f.write("1760020000,1\n")
            r = inventariar(d)
        self.assertEqual(r["cargables_minimo"], 0)
        self.assertIn("FILA_INCOMPLETA", r["archivos"][0]["error"])


if __name__ == "__main__":
    unittest.main()
