"""Pruebas de generacion aislada, sin memoria REAL ni acceso a broker."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from construir_memoria_train_candidata_practice import construir_memoria_candidata


def fila(i, fecha, resultado="WIN"):
    return {
        "activo": "EURUSD",
        "direccion": "CALL",
        "fecha": str(fecha),
        "resultado_hipotetico": resultado,
        "patron": "CHOCH",
    }


class MemoriaCandidataPracticeTests(unittest.TestCase):
    def train(self):
        return [fila(i, 1700000000 + 60 * i) for i in range(20)]

    def valid(self):
        return [fila(100, 1700010000, "LOSS")]

    def test_split_invertido_rechaza_sin_importar_generador(self):
        with tempfile.TemporaryDirectory() as raiz:
            with patch("motor_aprendizaje_historico.generar_aprendizaje_desde_resultados") as motor:
                with self.assertRaisesRegex(ValueError, "PARTICION_CRONOLOGICA_NO_APTA"):
                    construir_memoria_candidata(self.valid(), self.train(), raiz)
                motor.assert_not_called()
            self.assertFalse((Path(raiz) / "experimentos_fase5").exists())

    def test_missing_hypothetical_refuses_fallback_to_real(self):
        with tempfile.TemporaryDirectory() as raiz:
            train = self.train()
            train[0]["resultado_hipotetico"] = ""
            train[0]["resultado"] = "WIN"
            with self.assertRaisesRegex(ValueError, "ETIQUETA_HIPOTETICA"):
                construir_memoria_candidata(train, self.valid(), raiz)
            self.assertFalse((Path(raiz) / "experimentos_fase5").exists())

    def test_candidate_created_only_in_isolated_folder(self):
        with tempfile.TemporaryDirectory() as raiz:
            def generar(data, ruta, incluir_hipoteticos=False):
                self.assertTrue(incluir_hipoteticos)
                self.assertEqual(len(data), 20)
                Path(ruta).write_text("nivel,clave,total\nFAMILIA,A,20\n", encoding="utf-8")
                return [{"clave": "A", "total": 20}]
            with patch("motor_aprendizaje_historico.generar_aprendizaje_desde_resultados", side_effect=generar):
                r = construir_memoria_candidata(self.train(), self.valid(), raiz)
            destino = Path(raiz) / "experimentos_fase5" / "memoria_train_candidata.csv"
            self.assertTrue(destino.exists())
            self.assertTrue(r["requiere_validacion_independiente"])
            self.assertFalse(r["memoria_productiva_modificada"])
            self.assertFalse(r["operaciones_autorizadas"])
            self.assertFalse((Path(raiz) / "aprendizaje_historico_bootiq_F4_CC2.csv").exists())
            with self.assertRaises(FileExistsError):
                construir_memoria_candidata(self.train(), self.valid(), raiz)

    def test_reject_renaming_prod_path_to_candidate(self):
        with tempfile.TemporaryDirectory() as raiz:
            ruta = Path(raiz) / "experimentos_fase5" / "memoria_train_candidata.csv"
            with patch.dict("os.environ", {"BOOTIQ_RUTA_APRENDIZAJE": str(ruta)}):
                with self.assertRaisesRegex(ValueError, "MEMORIA_PRODUCTIVA"):
                    construir_memoria_candidata(self.train(), self.valid(), raiz)
            self.assertFalse(ruta.exists())

    def test_reject_insufficient_training(self):
        with tempfile.TemporaryDirectory() as raiz:
            with self.assertRaisesRegex(ValueError, "MUESTRA_TRAIN_INSUFICIENTE"):
                construir_memoria_candidata(self.train()[:19], self.valid(), raiz)


if __name__ == "__main__":
    unittest.main()
