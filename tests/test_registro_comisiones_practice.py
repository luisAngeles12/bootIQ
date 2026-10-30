"""Regresiones del registro economico de solo lectura PRACTICE."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from registro_comisiones_practice import guardar_eventos_comision


def evento(fuente=110, observado=111):
    return {
        "estado": "COMISION_RECIENTE_ESTIMACION_CONSERVADORA",
        "activo": "USDINR-OTC",
        "instrumento": "turbo-option",
        "payout_neto": .84,
        "timestamp_fuente": fuente,
        "timestamp_observacion_utc": observado,
        "operable": False,
    }


class RegistroComisionesTests(unittest.TestCase):
    def test_guarda_estimaciones_sin_presentarlas_como_payout_ejecutable(self):
        with TemporaryDirectory() as carpeta:
            ruta, n = guardar_eventos_comision(
                "USDINR-OTC", 100, 200, [evento()], carpeta)
            self.assertEqual(n, 1)
            with ruta.open(newline="", encoding="utf-8") as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertEqual(filas[0]["procedencia"], "WEBSOCKET_CAMBIO_NO_EJECUTABLE")
            self.assertNotIn("payout_fuente", filas[0])
            self.assertEqual(filas[0]["operable"], "False")
            with self.assertRaises(FileExistsError):
                guardar_eventos_comision(
                    "USDINR-OTC", 100, 200, [evento()], carpeta)

    def test_no_crea_archivo_si_no_hubo_cambios(self):
        with TemporaryDirectory() as carpeta:
            ruta, n = guardar_eventos_comision("USDINR-OTC", 100, 200, [], carpeta)
            self.assertIsNone(ruta)
            self.assertEqual(n, 0)
            self.assertEqual(list(Path(carpeta).iterdir()), [])

    def test_bloquea_eventos_futuros_duplicados_y_no_verificables(self):
        with TemporaryDirectory() as carpeta:
            malos = [
                {**evento(), "estado": "PAYOUT_NO_VERIFICADO"},
                {**evento(), "operable": True},
                evento(112, 111),
                evento(100, 170),
                evento(99, 110),  # Cambio previo a la sesion: cache, no evento nuevo
                {**evento(), "payout_neto": None},
                {**evento(), "activo": "EURUSD-OTC"},
            ]
            for malo in malos:
                with self.subTest(malo=malo):
                    with self.assertRaises(ValueError):
                        guardar_eventos_comision(
                            "USDINR-OTC", 100, 200, [malo], carpeta)
            with self.assertRaisesRegex(ValueError, "DUPLICADO"):
                guardar_eventos_comision(
                    "USDINR-OTC", 100, 200, [evento(), evento()], carpeta)


if __name__ == "__main__":
    unittest.main()
