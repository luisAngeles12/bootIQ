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
        self.assertEqual(r["superan_minimo_200"], 2)
        self.assertEqual(len(r["duplicados_identicos"]), 1)

    def test_encabezados_sin_velas_no_son_datasets_duplicados(self):
        with tempfile.TemporaryDirectory() as d:
            self.crear(d, "vacio_a.csv", n=0)
            self.crear(d, "vacio_b.csv", n=0)
            r = inventariar(d)
        self.assertEqual(r["total_csv"], 2)
        self.assertEqual(r["cargables_minimo"], 0)
        self.assertEqual(r["duplicados_velas"], [])
        self.assertEqual(len(r["duplicados_identicos"]), 1)
        self.assertTrue(all(f["sha256_velas"] is None for f in r["archivos"]))

    def test_detecta_duplicados_velas_con_distinto_formato_csv(self):
        with tempfile.TemporaryDirectory() as d:
            original = self.crear(d, "original.csv")
            with original.open(encoding="utf-8", newline="") as f:
                filas = list(csv.DictReader(f))
            segunda = Path(d) / "otro_formato.csv"
            with segunda.open("w", encoding="utf-8", newline="") as f:
                columnas = ["min", "max", "close", "open", "from"]
                w = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
                w.writeheader()
                for fila in filas:
                    fila["open"] = "1.00"
                    fila["close"] = "2.0"
                    w.writerow(fila)
            r = inventariar(d)
        self.assertEqual(r["total_csv"], 2)
        self.assertEqual(r["duplicados_identicos"], [])
        self.assertEqual(len(r["duplicados_velas"]), 1)
        self.assertEqual(r["cargables_minimo"], 2)

    def test_gap_detectado_sin_eliminar_archivo_cargable(self):
        with tempfile.TemporaryDirectory() as d:
            self.crear(d, "gaps.csv", paso=120)
            r = inventariar(d)
        self.assertEqual(r["cargables_minimo"], 1)
        self.assertEqual(r["con_continuidad_completa"], 0)
        self.assertEqual(r["archivos"][0]["saltos_temporales"], 199)

    def test_rechaza_precios_no_finitos_en_dataset(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.crear(d, "precio_invalido.csv")
            filas = p.read_text(encoding="utf-8").splitlines()
            filas[2] = filas[2].replace(",2,3,0", ",NaN,3,0")
            p.write_text("\n".join(filas) + "\n", encoding="utf-8")
            r = inventariar(d)
        self.assertEqual(r["cargables_minimo"], 0)
        self.assertEqual(r["superan_minimo_200"], 0)
        self.assertIn("PRECIO_NO_FINITO", r["archivos"][0]["error"])

    def test_rechaza_timestamp_no_finito(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.crear(d, "timestamp_invalido.csv")
            filas = p.read_text(encoding="utf-8").splitlines()
            filas[2] = "inf,1,2,3,0"
            p.write_text("\n".join(filas) + "\n", encoding="utf-8")
            r = inventariar(d)
        self.assertEqual(r["cargables_minimo"], 0)
        self.assertIn("TIMESTAMP_NO_FINITO", r["archivos"][0]["error"])

    def test_rechaza_ohlc_inconsistente(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.crear(d, "ohlc_invalido.csv")
            filas = p.read_text(encoding="utf-8").splitlines()
            # max=0.5 queda por debajo de apertura=1 y cierre=2.
            filas[2] = ",".join(filas[2].split(",")[:3] + ["0.5", "0"])
            p.write_text("\n".join(filas) + "\n", encoding="utf-8")
            r = inventariar(d)
        self.assertEqual(r["cargables_minimo"], 0)
        self.assertIn("OHLC_INCONSISTENTE", r["archivos"][0]["error"])

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
