"""Integracion de extremo a extremo del sondeo con broker simulado.

No se conecta a IQ Option. Nunca crea ordenes ni archivos historicos.
"""
import io
import unittest
from collections import defaultdict
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from sondear_velas_1s_practice import sondear


def vela(t):
    return {"from": t, "open": 100.0, "close": 100.0,
            "min": 100.0, "max": 100.0}


def broker_falso(modo="PRACTICE"):
    iq = Mock()
    iq.connect.return_value = (True, "ok")
    iq.check_connect.return_value = True
    iq.get_balance_mode.return_value = modo
    iq.get_balance.return_value = 10000.0
    iq.start_candles_one_stream.return_value = True
    iq.api.real_time_candles_maxdict_table = defaultdict(dict)
    iq.get_commission_change.return_value = {}
    iq.get_server_timestamp.side_effect = [100, 101, 102, 103, 104]
    iq.get_realtime_candles.side_effect = [
        {100: vela(100)}, {100: vela(100), 101: vela(101)},
        {100: vela(100), 101: vela(101), 102: vela(102)},
    ]
    return iq


class IntegracionSondeoSeguroTests(unittest.TestCase):
    @patch("sondear_velas_1s_practice.time.sleep")
    @patch("sondear_velas_1s_practice.time.monotonic",
           side_effect=[0, 1, 2, 3, 4])
    def test_pipeline_completo_no_envia_ordenes(self, _reloj, _espera):
        iq = broker_falso()
        with patch("iqoptionapi.stable_api.IQ_Option", return_value=iq), \
             redirect_stdout(io.StringIO()) as salida:
            sondear("USDINR-OTC", 3)
        texto = salida.getvalue()
        self.assertIn("SONDEO SOLO LECTURA", texto)
        self.assertIn("AUDITORIA_CEREBRO_SOMBRA", texto)
        self.assertIn("'operaciones': 0", texto)
        iq.change_balance.assert_called_once_with("PRACTICE")
        iq.start_candles_one_stream.assert_called_once_with("USDINR-OTC", 1)
        iq.subscribe_commission_changed.assert_called_once_with("turbo-option")
        iq.unsubscribe_commission_changed.assert_called_once_with("turbo-option")
        iq.get_all_profit.assert_not_called()
        iq.get_all_init.assert_not_called()
        iq.buy.assert_not_called()
        iq.buyv2.assert_not_called()
        iq.buy_digital_spot.assert_not_called()
        iq.buy_digital_spot_v2.assert_not_called()

    @patch("sondear_velas_1s_practice.time.sleep")
    def test_modo_real_corta_antes_de_abrir_stream(self, _espera):
        iq = broker_falso("REAL")
        with patch("iqoptionapi.stable_api.IQ_Option", return_value=iq), \
             redirect_stdout(io.StringIO()), \
             self.assertRaisesRegex(RuntimeError, "BLOQUEADO"):
            sondear("USDINR-OTC", 3)
        iq.start_candles_one_stream.assert_not_called()
        iq.subscribe_commission_changed.assert_not_called()
        iq.buy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
