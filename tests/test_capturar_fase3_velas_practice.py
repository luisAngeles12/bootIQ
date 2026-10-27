import csv
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from capturar_fase3_velas_practice import (
    CORTE_F3_UTC,
    capturar,
    validar_top_oficial,
)


def mod(nombre, **datos):
    objeto = types.ModuleType(nombre)
    for clave, valor in datos.items():
        setattr(objeto, clave, valor)
    return objeto


class CapturaFase3PracticeTests(unittest.TestCase):
    def test_top_1_a_20_sin_duplicaciones(self):
        top = [{"activo": "A", "tipo": "turbo"}]
        self.assertEqual(validar_top_oficial(top), top)
        with self.assertRaises(ValueError):
            validar_top_oficial([])
        with self.assertRaises(ValueError):
            validar_top_oficial(top * 21)
        with self.assertRaises(ValueError):
            validar_top_oficial(top * 2)
        with self.assertRaises(ValueError):
            validar_top_oficial([{"activo": "A", "tipo": "binary"}])

    def test_bloquea_real_antes_de_conectar(self):
        modulos = {"config": mod("config", MODO_CUENTA="REAL")}
        with patch.dict(sys.modules, modulos):
            with self.assertRaisesRegex(RuntimeError, "PRACTICE"):
                capturar()

    def test_captura_aislada_sin_borrar_archivos_previos(self):
        class Balance:
            def get_balance_mode(self):
                return "PRACTICE"

        def descarga(tipo, activo):
            ruta = Path(backtest.CARPETA_DATA) / (tipo + "_" + activo + ".csv")
            with ruta.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["tipo", "activo", "from", "open", "close", "max", "min", "volume"])
                for n in range(2):
                    writer.writerow([tipo, activo, int(CORTE_F3_UTC) + 86400 + n*60,
                                     1, 1, 2, 0, 0])
            return True

        backtest = mod("backtest_data", descargar_velas_activo=descarga)
        modulos = {
            "config": mod("config", MODO_CUENTA="PRACTICE"),
            "conexion": mod("conexion", conectar=lambda: None),
            "mercado": mod("mercado", obtener_activos=lambda: [
                {"activo": "ACTIVO", "tipo": "turbo"}
            ]),
            "backtest_data": backtest,
            "estado": mod("estado", Iq=Balance()),
        }
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            previo = raiz / "previo.csv"
            previo.write_text("dato anterior", encoding="utf-8")
            with patch.dict(sys.modules, modulos):
                ruta, r = capturar(raiz)
            self.assertTrue(previo.exists())
            self.assertEqual(previo.read_text(encoding="utf-8"), "dato anterior")
            self.assertEqual(r["modo"], "PRACTICE")
            self.assertFalse(r["autoriza_operaciones"])
            self.assertEqual(r["total_activos"], 1)
            self.assertEqual(len(r["datasets"][0]["sha256"]), 64)
            self.assertEqual(json.loads((ruta/"manifest.json").read_text())["total_activos"], 1)


if __name__ == "__main__":
    unittest.main()
