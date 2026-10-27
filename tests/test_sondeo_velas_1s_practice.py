import tempfile
import unittest
from pathlib import Path

from sondear_velas_1s_practice import (
    exigir_config_practice,
    observar_instantanea,
    resumir,
)


def vela(t, apertura=100, cierre=101, minimo=99, maximo=102):
    return {"from": t, "open": apertura, "close": cierre,
            "min": minimo, "max": maximo}


class SondeoPracticaTests(unittest.TestCase):
    def test_rechaza_real_antes_de_importar_broker(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "config.py"
            ruta.write_text('MODO_CUENTA = "REAL"\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "BLOQUEADO"):
                exigir_config_practice(ruta)

    def test_rechaza_config_dinamica(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "config.py"
            ruta.write_text('MODO_CUENTA = modo\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "BLOQUEADO"):
                exigir_config_practice(ruta)

    def test_acepta_solo_practice_literal(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "config.py"
            ruta.write_text('MODO_CUENTA = "PRACTICE"\n', encoding="utf-8")
            exigir_config_practice(ruta)

    def test_excluye_historia_y_vela_abierta(self):
        vistos = {}
        instantanea = {99: vela(99), 100: vela(100), 101: vela(101)}
        self.assertEqual(observar_instantanea(instantanea, 101, 100, vistos), 1)
        self.assertEqual(sorted(vistos), [100])
        self.assertEqual(observar_instantanea(instantanea, 101, 100, vistos), 0)

    def test_rechaza_ohlc_corrupto_y_timestamps_discordantes(self):
        vistos = {}
        datos = {100: vela(100, cierre=104), 101: vela(105), 102: vela(102)}
        self.assertEqual(observar_instantanea(datos, 103, 100, vistos), 1)
        self.assertEqual(list(vistos), [102])

    def test_gap_y_retraso_se_reportan(self):
        datos = {100: vela(100), 102: vela(102)}
        resultado = resumir(datos, 100, 104)
        self.assertEqual(resultado["huecos_entre_velas"], 1)
        self.assertEqual(resultado["retraso_ultima_segundos"], 1)
        self.assertFalse(resultado["muestra_continua"])


if __name__ == "__main__":
    unittest.main()
