"""Regresiones del diagnóstico de solo lectura fase 9."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.diagnostico_fuentes_fase9 import analizar_memoria, analizar_reporte


class DiagnosticoFuentesFase9Tests(unittest.TestCase):
    def test_conteo_bootstrap_y_otras_autoridades(self):
        reporte = {
            "resumen": {"total": 3},
            "detalle": {
                "operaciones": [
                    {"order_id": "1", "origen_autoridad":
                        "BOOTSTRAP_PRACTICE_SIN_HISTORIAL", "resultado": "WIN"},
                    {"order_id": "2", "origen_autoridad":
                        "BOOTSTRAP_PRACTICE_SIN_HISTORIAL", "resultado": "LOSS"},
                    {"order_id": "3", "origen_autoridad": "PROBABILIDAD_HISTORICA_V3",
                     "resultado": "LOSS"},
                ],
            },
        }
        salida = analizar_reporte(reporte)
        self.assertEqual(salida["cantidad_registros"], 3)
        self.assertEqual(
            salida["autoridades_presentes"]["BOOTSTRAP_PRACTICE_SIN_HISTORIAL"], 2
        )
        self.assertEqual(salida["resultados_presentes"], {"LOSS": 2, "WIN": 1})
        self.assertEqual(salida["sin_campo_autoridad"], 0)

    def test_esquema_desconocido_no_inventa_autoridad(self):
        salida = analizar_reporte({"resumen": {"total": 20, "wins": 10}})
        self.assertIsNone(salida["cantidad_registros"])
        self.assertIn("advertencia", salida)

    def test_registro_sin_autoridad_se_declara_incompleto(self):
        salida = analizar_reporte({"operaciones": [
            {"order_id": "x", "resultado": "WIN"},
        ]})
        self.assertEqual(salida["sin_campo_autoridad"], 1)
        self.assertTrue(salida["sin_desglose_autoridad"])

    def test_lectura_memoria_no_modifica_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "memoria.csv"
            with ruta.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["clave", "total", "wins", "losses"])
                w.writeheader()
                w.writerow({"clave": "A", "total": "4", "wins": 2, "losses": 2})
                w.writerow({"clave": "B", "total": "12", "wins": 7, "losses": 5})
                w.writerow({"clave": "C", "total": "20", "wins": 11, "losses": 9})
            antes = ruta.read_bytes()
            r = analizar_memoria(ruta)
            self.assertEqual((r["muestra_ge_5"], r["muestra_ge_12"],
                              r["muestra_ge_20"]), (2, 2, 1))
            self.assertEqual(r["filas"], 3)
            self.assertEqual(ruta.read_bytes(), antes)

    def test_memoria_ausente_no_se_interpreta_como_vacia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            r = analizar_memoria(Path(carpeta) / "inexistente.csv")
            self.assertFalse(r["existe"])
            self.assertNotIn("filas", r)


if __name__ == "__main__":
    unittest.main()
