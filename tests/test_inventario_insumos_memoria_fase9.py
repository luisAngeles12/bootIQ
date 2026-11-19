"""Pruebas del inventario R9: solo lectura, sin conexión ni órdenes."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.inventario_insumos_memoria_fase9 import (
    diagnostico_insumos,
    inventariar_archivos,
)


class InventarioInsumosMemoriaFase9Tests(unittest.TestCase):
    def test_encuentra_historial_y_memoria_sin_reescribirlos(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            datos = raiz / "historial_bot.csv"
            with datos.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["order_id", "resultado"])
                writer.writeheader()
                writer.writerow({"order_id": "1", "resultado": "WIN"})
            antes = datos.read_bytes()
            encontrados = inventariar_archivos(raiz)
            self.assertEqual(len(encontrados), 1)
            self.assertEqual(encontrados[0]["archivo"], "historial_bot.csv")
            self.assertEqual(encontrados[0]["columnas"], ["order_id", "resultado"])
            self.assertEqual(datos.read_bytes(), antes)

    def test_omite_venv_y_no_fabrica_memoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "venv").mkdir()
            (raiz / "venv" / "aprendizaje_dummy.csv").write_text("clave,total\na,20\n")
            with patch.dict("os.environ", {"BOOTIQ_RUTA_APRENDIZAJE": "no_existe.csv"}):
                salida = diagnostico_insumos(raiz)
            self.assertFalse(salida["memoria_configurada_existe"])
            self.assertEqual(salida["inventario"], [])
            self.assertFalse((raiz / "no_existe.csv").exists())

    def test_memoria_configurada_fuera_de_raiz_no_es_modificada(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            memoria = raiz / "aprendizaje_historico_bootiq_F4_CC2.csv"
            memoria.write_text("clave,total\nFAMILIA|A,12\n", encoding="utf-8")
            original = memoria.read_bytes()
            with patch.dict("os.environ", {
                "BOOTIQ_RUTA_APRENDIZAJE": str(memoria),
            }):
                salida = diagnostico_insumos(raiz)
            self.assertTrue(salida["memoria_configurada_existe"])
            self.assertEqual(memoria.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
