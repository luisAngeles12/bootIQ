"""Regresiones de memoria OOS: no se promociona ni altera la productiva."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluar_memoria_candidata_oos_practice import evaluar_candidata_oos


def fila(i, ts, resultado):
    return {"activo": "EURUSD", "direccion": "CALL", "fecha": str(ts),
            "resultado_hipotetico": resultado, "patron": "CHOCH"}


class MemoriaOosTests(unittest.TestCase):
    def setUp(self):
        self.train = [fila(i, 1700000000 + i * 60, "WIN" if i % 2 else "LOSS")
                      for i in range(20)]
        self.valid = [fila(i, 1700100000 + i * 60, "WIN" if i % 2 else "LOSS")
                      for i in range(20)]

    def test_candidato_reproducible_evalua_sin_autorizar(self):
        with tempfile.TemporaryDirectory() as d:
            from motor_aprendizaje_historico import generar_aprendizaje_desde_resultados
            candidata = Path(d) / "memoria.csv"
            generar_aprendizaje_desde_resultados(
                self.train, ruta=str(candidata), incluir_hipoteticos=True
            )
            r = evaluar_candidata_oos(self.train, self.valid, candidata)
            self.assertEqual(r["validacion_registros"], 20)
            self.assertTrue(r["huella_memoria_coincide_con_train"])
            self.assertFalse(r["cambios_operativos_autorizados"])
            self.assertFalse(r["memoria_productiva_modificada"])
            self.assertEqual(r["senales_con_fuente"] + r["senales_sin_fuente"], 20)

    def test_candidata_adulterada_se_rechaza(self):
        with tempfile.TemporaryDirectory() as d:
            candidata = Path(d) / "memoria.csv"
            candidata.write_text("nivel,clave,total\nFAMILIA,FAKE,999\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CANDIDATA_NO_COINCIDE"):
                evaluar_candidata_oos(self.train, self.valid, candidata)

    def test_validacion_invertida_rechazada(self):
        with tempfile.TemporaryDirectory() as d:
            candidata = Path(d) / "memoria.csv"
            candidata.write_text("dummy", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PARTICION_TEMPORAL_NO_APTA"):
                evaluar_candidata_oos(self.valid, self.train, candidata)

    def test_etiqueta_oos_invalida_no_se_silencia(self):
        with tempfile.TemporaryDirectory() as d:
            candidata = Path(d) / "memoria.csv"
            candidata.write_text("dummy", encoding="utf-8")
            valid = [dict(x) for x in self.valid]
            valid[1]["resultado_hipotetico"] = ""
            with self.assertRaisesRegex(ValueError, "ETIQUETA_HIPOTETICA"):
                evaluar_candidata_oos(self.train, valid, candidata)


if __name__ == "__main__":
    unittest.main()
