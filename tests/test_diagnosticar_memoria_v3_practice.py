"""Pruebas aisladas del diagnostico de memoria oficial (sin broker)."""
import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from diagnosticar_memoria_v3_practice import diagnosticar_memoria


class DiagnosticoMemoriaV3Tests(unittest.TestCase):
    def test_archivo_ausente_no_crea_ninguna_memoria(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "no_existe.csv"
            resultado = diagnosticar_memoria(str(destino))
            self.assertEqual(resultado["estado"], "ARCHIVO_OFICIAL_AUSENTE")
            self.assertFalse(destino.exists())
            self.assertFalse(resultado["operaciones_autorizadas"])
            self.assertFalse(resultado["memoria_modificada"])

    def test_memoria_valida_contabiliza_claves_distintas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "aprendizaje.csv"
            with destino.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["clave", "wins"])
                writer.writeheader()
                writer.writerow({"clave": "PATRON|CHOCH", "wins": 3})
                writer.writerow({"clave": "PATRON|CHOCH", "wins": 2})
                writer.writerow({"clave": "", "wins": 0})
            resultado = diagnosticar_memoria(str(destino))
            self.assertEqual(resultado["estado"], "MEMORIA_CON_CLAVES")
            self.assertEqual(resultado["filas_csv"], 3)
            self.assertEqual(resultado["claves_no_vacias"], 2)
            self.assertEqual(resultado["claves_distintas"], 1)
            self.assertFalse(resultado["operaciones_autorizadas"])

    def test_csv_sin_clave_no_equivale_a_memoria_usable(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "incompatible.csv"
            destino.write_text("patron,wins\nCHOCH,10\n", encoding="utf-8")
            resultado = diagnosticar_memoria(str(destino))
            self.assertEqual(resultado["estado"], "CABECERA_INCOMPATIBLE_SIN_CLAVE")

    def test_ruta_custom_por_entorno_tiene_precedencia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "custom.csv"
            destino.write_text("clave,wins\nX,3\n", encoding="utf-8")
            with patch.dict(os.environ, {"BOOTIQ_RUTA_APRENDIZAJE": str(destino)}):
                resultado = diagnosticar_memoria()
            self.assertTrue(resultado["variable_entorno_personalizada"])
            self.assertEqual(resultado["ruta_configurada"], str(destino))


if __name__ == "__main__":
    unittest.main()
