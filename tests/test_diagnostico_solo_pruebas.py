"""Contrato de seguridad del diagnostico sin operaciones."""
import csv
import tempfile
import unittest
from pathlib import Path

from auditoria_candidatas_sombra_practice import COLUMNAS
from diagnostico_solo_pruebas import diagnosticar


class DiagnosticoSoloPruebasTest(unittest.TestCase):
    def test_instalacion_limpia_no_autoriza_operaciones(self):
        with tempfile.TemporaryDirectory() as raiz:
            resultado = diagnosticar(raiz)
            self.assertEqual(resultado["modo"], "SOLO_PRUEBAS_OFFLINE")
            self.assertFalse(resultado["operaciones_autorizadas"])
            self.assertFalse(resultado["broker_conectado"])
            self.assertFalse(resultado["modifica_memoria"])
            self.assertEqual(resultado["memoria_cc2"]["estado"], "AUSENTE")
            self.assertIsNone(resultado["historial_operaciones"]["filas"])
            self.assertEqual(list(Path(raiz).iterdir()), [])

    def test_historial_vacio_y_sombra_hipotetica_no_generan_memoria(self):
        with tempfile.TemporaryDirectory() as raiz:
            base = Path(raiz)
            with (base / "historial_bot.csv").open("w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=["resultado"]).writeheader()
            with (base / "auditoria_candidatas_sombra_practice.csv").open(
                "w", newline="", encoding="utf-8"
            ) as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNAS)
                writer.writeheader()
                fila = dict.fromkeys(COLUMNAS, "")
                fila.update({
                    "id": "prueba-1", "activo": "EURUSD-OTC",
                    "direccion": "call", "patron": "CHOCH alcista",
                    "vela_senal_from": "1793922000",
                    "decision": "NO_OPERAR", "calidad_mercado": "NORMAL",
                    "resultado_hipotetico": "WIN",
                    "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
                })
                writer.writerow(fila)
            resultado = diagnosticar(raiz)
            self.assertEqual(resultado["historial_operaciones"]["filas"], 0)
            self.assertEqual(resultado["sombra"]["resultados_hipoteticos"]["WIN"], 1)
            self.assertEqual(resultado["memoria_cc2"]["estado"], "AUSENTE")
            self.assertFalse(resultado["operaciones_autorizadas"])
            self.assertFalse((base / "aprendizaje_historico_bootiq_F4_CC2.csv").exists())

    def test_duplicados_se_reportan_sin_alterarlos(self):
        with tempfile.TemporaryDirectory() as raiz:
            ruta = Path(raiz) / "auditoria_candidatas_sombra_practice.csv"
            with ruta.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNAS)
                writer.writeheader()
                for _ in range(2):
                    fila = dict.fromkeys(COLUMNAS, "")
                    fila.update({"id": "mismo-id", "activo": "EURUSD-OTC",
                                 "direccion": "put", "vela_senal_from": "1793922000",
                                 "decision": "NO_OPERAR", "calidad_mercado": "NORMAL",
                                 "resultado_hipotetico": "LOSS",
                                 "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL"})
                    writer.writerow(fila)
            antes = ruta.read_bytes()
            resultado = diagnosticar(raiz)
            self.assertEqual(resultado["sombra"]["ids_duplicados"], 1)
            self.assertIn("IDS_SOMBRA_DUPLICADOS",
                          resultado["razones_sin_autorizacion"])
            self.assertEqual(ruta.read_bytes(), antes)
            self.assertFalse(resultado["operaciones_autorizadas"])


if __name__ == "__main__":
    unittest.main()
