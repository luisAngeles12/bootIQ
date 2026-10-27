import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

from sondear_velas_1s_practice import (
    exigir_config_practice,
    conectar_sondeo_practice,
    iniciar_stream_sin_precarga,
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

    @patch("sondear_velas_1s_practice.time.sleep")
    def test_conexion_no_depende_de_opcode(self, _sleep):
        iq = Mock()
        iq.connect.return_value = (True, "ok")
        iq.check_connect.return_value = True
        iq.get_balance_mode.return_value = "PRACTICE"
        iq.get_balance.return_value = 9992
        estado = SimpleNamespace(Iq=None, balance_inicial=None)
        resultado = conectar_sondeo_practice(
            lambda *_: iq, "correo", "clave", estado
        )
        self.assertIs(resultado, iq)
        iq.change_balance.assert_called_once_with("PRACTICE")
        self.assertEqual(estado.balance_inicial, 9992.0)

    @patch("sondear_velas_1s_practice.time.sleep")
    def test_cuenta_real_bloqueada_antes_del_stream(self, _sleep):
        iq = Mock()
        iq.connect.return_value = (True, "ok")
        iq.check_connect.return_value = True
        iq.get_balance_mode.return_value = "REAL"
        with self.assertRaisesRegex(RuntimeError, "BLOQUEADO"):
            conectar_sondeo_practice(lambda *_: iq, "correo", "clave",
                                     SimpleNamespace())
        iq.get_balance.assert_not_called()

    def test_id_desconocido_no_suscribe(self):
        iq = Mock()
        with self.assertRaisesRegex(RuntimeError, "ID local"):
            iniciar_stream_sin_precarga(iq, "DESCONOCIDO", {"USDINR-OTC": 1383})
        iq.start_candles_one_stream.assert_not_called()

    def test_suscribe_un_segundo_sin_precarga_historica(self):
        iq = Mock()
        iq.start_candles_one_stream.return_value = True
        iniciar_stream_sin_precarga(iq, "USDINR-OTC", {"USDINR-OTC": 1383})
        self.assertEqual(iq.api.real_time_candles_maxdict_table[
            "USDINR-OTC"][1], 60)
        iq.start_candles_one_stream.assert_called_once_with("USDINR-OTC", 1)
        iq.start_candles_stream.assert_not_called()
        iq.get_candles.assert_not_called()

    def test_suscripcion_no_confirmada_aborta(self):
        iq = Mock()
        iq.start_candles_one_stream.return_value = False
        with self.assertRaisesRegex(RuntimeError, "no confirmada"):
            iniciar_stream_sin_precarga(iq, "USDINR-OTC",
                                        {"USDINR-OTC": 1383})


if __name__ == "__main__":
    unittest.main()
