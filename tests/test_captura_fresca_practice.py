import csv
import tempfile
import unittest
from pathlib import Path

from captura_fresca_practice import guardar_captura_fresca, preparar_filas


def vela(t, c=101):
    return {"from": t, "open": 100, "close": c, "min": 99, "max": 102}


class CapturaFrescaPracticeTests(unittest.TestCase):
    def test_solo_velas_cerradas_posteriores_al_inicio(self):
        with self.assertRaisesRegex(ValueError, "VELA_FUERA_DE_SESION"):
            preparar_filas("USDINR-OTC", {99: vela(99)}, 100, 105)
        with self.assertRaisesRegex(ValueError, "VELA_FUERA_DE_SESION"):
            preparar_filas("USDINR-OTC", {105: vela(105)}, 100, 105)

    def test_rechaza_huecos_y_precios_invalidos(self):
        with self.assertRaisesRegex(ValueError, "HUECO_TEMPORAL"):
            preparar_filas("USDINR-OTC", {100: vela(100), 102: vela(102)}, 100, 104)
        with self.assertRaisesRegex(ValueError, "OHLC_INVALIDO"):
            preparar_filas("USDINR-OTC", {100: vela(100, c=103)}, 100, 102)
        con_nan = vela(100)
        con_nan["close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "PRECIO_NO_FINITO"):
            preparar_filas("USDINR-OTC", {100: con_nan}, 100, 102)

    def test_no_reutiliza_historia_ni_sobrescribe_captura(self):
        with tempfile.TemporaryDirectory() as temporal:
            destino = Path(temporal)
            ruta, total = guardar_captura_fresca(
                "USDINR-OTC", {100: vela(100), 101: vela(101)}, 100, 103, destino
            )
            self.assertEqual(total, 2)
            with ruta.open(encoding="utf-8", newline="") as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertEqual([int(f["timestamp_utc"]) for f in filas], [100, 101])
            self.assertTrue(all(f["activo"] == "USDINR-OTC" for f in filas))
            self.assertTrue(all("+00:00" in f["capturado_en_utc"] for f in filas))
            with self.assertRaises(FileExistsError):
                guardar_captura_fresca("USDINR-OTC", {100: vela(100), 101: vela(101)}, 100, 103, destino)
            self.assertEqual(len(list(destino.glob("*.csv"))), 1)

    def test_no_acepta_traversal_en_nombre_activo(self):
        with self.assertRaisesRegex(ValueError, "ACTIVO_INVALIDO"):
            preparar_filas("../otro", {100: vela(100)}, 100, 102)


if __name__ == "__main__":
    unittest.main()
