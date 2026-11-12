"""Pruebas del preflight de memoria, sin imports del broker ni escrituras."""
import csv
import tempfile
import unittest
from pathlib import Path

from auditar_memoria_fase5_practice import auditar_memoria


class AuditoriaMemoriaFase5Tests(unittest.TestCase):
    def preparar(self, raiz):
        (raiz / "backtest_bot_real.py").write_text(
            'MODO_EXPERIMENTO_OUT_OF_SAMPLE = "OUT_OF_SAMPLE"\n'
            'MODO_EXPERIMENTO = MODO_EXPERIMENTO_OUT_OF_SAMPLE\n'
            'ACTUALIZAR_APRENDIZAJE = False\n'
            'ACTUALIZAR_APRENDIZAJE_PROTOCOLO = False\n',
            encoding="utf-8",
        )

    def test_memoria_ausente_no_crea_archivos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.preparar(raiz)
            r = auditar_memoria(raiz)
            self.assertEqual(r["estado_memoria"], "MEMORIA_AUSENTE")
            self.assertEqual(r["config_backtest_estatica"]["modo_experimento"], "OUT_OF_SAMPLE")
            self.assertTrue(r["actualizacion_estatica_desactivada"])
            self.assertFalse((raiz / "aprendizaje_historico_bootiq_F4_CC2.csv").exists())
            self.assertFalse(r["cambios_operativos_autorizados"])

    def test_memoria_con_muestras_y_protocolo_separados(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.preparar(raiz)
            archivo = raiz / "aprendizaje_historico_bootiq_F4_CC2.csv"
            with archivo.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["nivel", "clave", "total"])
                w.writeheader()
                w.writerows([
                    {"nivel": "SETUP", "clave": "SETUP|CALL", "total": "12"},
                    {"nivel": "PROTOCOLO", "clave": "PROTOCOLO|PUT", "total": "5"},
                    {"nivel": "PA", "clave": "PA|CALL", "total": "2"},
                ])
            r = auditar_memoria(raiz)
            self.assertEqual(r["conteos"]["filas"], 3)
            self.assertEqual(r["conteos"]["muestras_ge_12"], 1)
            self.assertEqual(r["conteos"]["muestras_ge_5"], 2)
            self.assertEqual(r["conteos"]["filas_protocolo"], 1)
            self.assertFalse(r["compatibilidad_por_senal_verificada"])

    def test_esquema_incompatible_no_se_declara_utilizable(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.preparar(raiz)
            (raiz / "aprendizaje_historico_bootiq_F4_CC2.csv").write_text(
                "otro,total\nclave,100\n", encoding="utf-8"
            )
            r = auditar_memoria(raiz)
            self.assertEqual(r["estado_memoria"], "ESQUEMA_NO_COMPATIBLE")
            self.assertEqual(r["conteos"]["muestras_ge_5"], 0)

    def test_archivo_sin_muestras_no_es_fuente_utilizable(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            self.preparar(raiz)
            (raiz / "aprendizaje_historico_bootiq_F4_CC2.csv").write_text(
                "nivel,clave,total\nSETUP,X,4\n", encoding="utf-8"
            )
            r = auditar_memoria(raiz)
            self.assertEqual(r["estado_memoria"], "MEMORIA_SIN_FUENTES_CON_MUESTRA")
            self.assertFalse(r["memoria_generada"])


if __name__ == "__main__":
    unittest.main()
