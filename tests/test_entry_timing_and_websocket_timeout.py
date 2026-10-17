import threading
import time
import unittest
from unittest.mock import Mock, patch

import estado
from iqoptionapi import global_value
from iqoptionapi.api import IQOptionAPI
from iqoptionapi.stable_api import IQ_Option
from operaciones import (
    abrir_operacion,
    revisar_operaciones_abiertas,
)


class EntryTimingTests(unittest.TestCase):
    def setUp(self):
        self.original_iq = estado.Iq
        self.original_cooldowns = estado.cooldown_activos
        self.original_open_operations = estado.operaciones_abiertas
        estado.cooldown_activos = {}

    def tearDown(self):
        estado.Iq = self.original_iq
        estado.cooldown_activos = self.original_cooldowns
        estado.operaciones_abiertas = self.original_open_operations

    def _signal(self, timestamp):
        current_candle = int(timestamp // 60) * 60
        iq = Mock()
        iq.get_server_timestamp.return_value = timestamp
        iq.buy.return_value = (False, "mock-rejected")
        estado.Iq = iq

        return iq, {
            "cerebro_unico_decision": "OPERAR",
            "protocolo_confirmado": False,
            "activo": "EURUSD",
            "direccion": "call",
            "tipo": "turbo",
            "vela_senal_from": current_candle - 60,
        }

    def test_entry_is_allowed_at_second_27(self):
        timestamp = (int(time.time() // 60) * 60) + 27
        iq, signal = self._signal(timestamp)

        self.assertFalse(abrir_operacion(signal))
        iq.buy.assert_called_once()

    def test_entry_is_rejected_at_send_margin(self):
        timestamp = (int(time.time() // 60) * 60) + 28
        iq, signal = self._signal(timestamp)

        self.assertFalse(abrir_operacion(signal))
        iq.buy.assert_not_called()

    def test_buy_does_not_clear_a_response_received_during_send(self):
        iq = IQ_Option.__new__(IQ_Option)
        iq.api = Mock()

        def complete_order(*args):
            request_id = args[-1]
            iq.api.buy_multi_option[request_id] = {"id": 12345}
            iq.api.result = True

        iq.api.buyv3.side_effect = complete_order

        result = iq.buy(1, "EURUSD", "call", 1)

        self.assertEqual(result, (True, 12345))

    def test_result_reconciliation_checks_at_most_one_order_per_pass(self):
        now = time.time()
        operations = [
            {
                "order_id": str(index),
                "activo": "EURUSD",
                "tipo": "turbo",
                "direccion": "call",
                "hora_apertura": now - 200,
                "resultado_pendiente_csv": None,
            }
            for index in range(2)
        ]
        estado.operaciones_abiertas = operations

        with patch(
            "operaciones.obtener_resultado_operacion",
            return_value=None,
        ) as check_result, patch(
            "operaciones.guardar_operaciones_pendientes",
        ):
            revisar_operaciones_abiertas()

        check_result.assert_called_once_with(operations[0])
        self.assertEqual(estado.operaciones_abiertas, operations)


class CandleRequestTimeoutTests(unittest.TestCase):
    def test_candle_request_does_not_wait_indefinitely_for_lock(self):
        iq = IQ_Option.__new__(IQ_Option)
        iq._candles_lock = threading.Lock()
        iq._candles_lock.acquire()

        try:
            inicio = time.monotonic()
            resultado = iq.get_candles(
                "EURUSD",
                60,
                1,
                time.time(),
                timeout=0.2,
            )
            demora = time.monotonic() - inicio
        finally:
            iq._candles_lock.release()

        self.assertIsNone(resultado)
        self.assertLess(demora, 1.0)

    def test_websocket_request_times_out_while_reader_holds_mutex(self):
        api = IQOptionAPI.__new__(IQOptionAPI)
        with patch.object(
            global_value,
            "ssl_Mutual_exclusion",
            True,
        ), patch.object(
            global_value,
            "ssl_Mutual_exclusion_write",
            False,
        ):
            inicio = time.monotonic()
            with self.assertRaises(TimeoutError):
                api.send_websocket_request(
                    "test",
                    {},
                )

        self.assertLess(time.monotonic() - inicio, 1.5)

    def test_websocket_close_uses_bounded_thread_join(self):
        api = IQOptionAPI.__new__(IQOptionAPI)
        api.websocket_client = Mock()
        api.websocket_thread = Mock()
        api.websocket_thread.is_alive.return_value = True

        result = api.close(timeout=0.25)

        self.assertFalse(result)
        api.websocket_client.wss.close.assert_called_once_with()
        api.websocket_thread.join.assert_called_once_with(timeout=0.25)

    def test_websocket_open_timeout_closes_socket_and_returns(self):
        class FakeThread:
            def __init__(self, *args, **kwargs):
                self.join_timeout = None

            def start(self):
                pass

            def join(self, timeout=None):
                self.join_timeout = timeout

        api = IQOptionAPI.__new__(IQOptionAPI)
        websocket_client = Mock()
        thread = FakeThread()

        with patch(
            "iqoptionapi.api.WebsocketClient",
            return_value=websocket_client,
        ), patch(
            "iqoptionapi.api.threading.Thread",
            return_value=thread,
        ), patch.object(
            global_value,
            "check_websocket_if_connect",
            None,
        ), patch.object(
            global_value,
            "check_websocket_if_error",
            False,
        ), patch.object(
            global_value,
            "websocket_error_reason",
            None,
        ):
            result = api.start_websocket(timeout=0.1)

        self.assertEqual(result, (False, "WEBSOCKET_OPEN_TIMEOUT"))
        websocket_client.wss.close.assert_called_once_with()
        self.assertEqual(thread.join_timeout, 1.0)

    def test_reconnect_stops_when_previous_websocket_cannot_be_closed(self):
        iq = IQ_Option.__new__(IQ_Option)
        iq.api = Mock()
        iq.api.close.return_value = False

        result = iq.connect()

        self.assertEqual(result, (False, "WEBSOCKET_CLOSE_TIMEOUT"))
        iq.api.close.assert_called_once_with(timeout=2.0)
