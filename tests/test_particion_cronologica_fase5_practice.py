"""Pruebas de particion cronologica sin entrenar memoria productiva."""
import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from preparar_particion_cronologica_fase5_practice import preparar_particion


def filas(dias=4, cantidad=25):
    base = 1700000000
    salida = []
    for d in range(dias):
        for i in range(cantidad):
            salida.append({
                "fecha": str(base + d * 86400 + i * 60),
                "activo": "EURUSD",
                "direccion": "CALL",
                "resultado_hipotetico": "WIN" if i % 2 else "LOSS",
                "patron": "CHOCH",
            })
    return salida


class ParticionCronologicaFase5Tests(unittest.TestCase):
    def test_crea_archivos_aislados_sin_memoria_oficial(self):
        with tempfile.TemporaryDirectory() as raiz:
            resultado = preparar_particion(filas(), raiz)
            self.assertTrue(resultado["integridad"]["separacion_cronologica_estricta"])
            self.assertFalse(resultado["memoria_productiva_modificada"])
            self.assertFalse(resultado["operaciones_autorizadas"])
            for clave in ("train", "validacion"):
                self.assertTrue(Path(resultado[clave]).is_file())
            self.assertFalse((Path(raiz) / "aprendizaje_historico_bootiq_F4_CC2.csv").exists())
            with self.assertRaises(FileExistsError):
                preparar_particion(filas(), raiz)

    def test_menos_de_tres_dias_no_finge_validacion(self):
        with tempfile.TemporaryDirectory() as raiz:
            with self.assertRaisesRegex(ValueError, "DIAS_INSUFICIENTES"):
                preparar_particion(filas(dias=2), raiz)
            self.assertFalse((Path(raiz) / "experimentos_fase5").exists())

    def test_descarta_solapamiento_eventos_identicos(self):
        registros = filas()
        registros[1] = registros[0].copy()
        with tempfile.TemporaryDirectory() as raiz:
            with self.assertRaisesRegex(ValueError, "INTEGRIDAD"):
                preparar_particion(registros, raiz)
            self.assertFalse((Path(raiz) / "experimentos_fase5").exists())

    def test_prohibe_train_con_etiqueta_invalida(self):
        registros = filas()
        registros[0]["resultado_hipotetico"] = "NO_DETERMINADO"
        with tempfile.TemporaryDirectory() as raiz:
            with self.assertRaisesRegex(ValueError, "ETIQUETAS_HIPOTETICAS"):
                preparar_particion(registros, raiz)
            self.assertFalse((Path(raiz) / "experimentos_fase5").exists())

    def test_muestra_insuficiente_por_grupo(self):
        with tempfile.TemporaryDirectory() as raiz:
            with self.assertRaisesRegex(ValueError, "MUESTRA_INSUFICIENTE"):
                preparar_particion(filas(cantidad=4), raiz)

    def test_split_usa_dias_utc_completos(self):
        with tempfile.TemporaryDirectory() as raiz:
            r = preparar_particion(filas(), raiz)
            self.assertFalse(set(r["dias_train"]) & set(r["dias_validacion"]))
            self.assertLess(max(r["dias_train"]), min(r["dias_validacion"]))
            with Path(r["train"]).open(encoding="utf-8", newline="") as f:
                train = list(csv.DictReader(f))
            with Path(r["validacion"]).open(encoding="utf-8", newline="") as f:
                valid = list(csv.DictReader(f))
            self.assertEqual(len(train), r["registros_train"])
            self.assertEqual(len(valid), r["registros_validacion"])


if __name__ == "__main__":
    unittest.main()
