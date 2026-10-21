import threading
import time
import unittest
import socket
import json
from collections import Counter
from unittest.mock import Mock, patch

import estado
from iqoptionapi import global_value
from iqoptionapi.api import IQOptionAPI
from iqoptionapi.stable_api import IQ_Option
from iqoptionapi.ws.client import WebsocketClient
from iqoptionapi.ws.chanels.heartbeat import Heartbeat
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
    def test_first_connect_initializes_api_without_existing_session(self):
        iq = IQ_Option("test@example.com", "not-a-real-password")
        api = Mock()
        api.connect.return_value = (False, "mock-connect-failure")
        original_balance_id = global_value.balance_id

        try:
            with patch(
                "iqoptionapi.stable_api.IQOptionAPI",
                return_value=api,
            ) as api_factory:
                result = iq.connect()
        finally:
            global_value.balance_id = original_balance_id

        self.assertEqual(result, (False, "mock-connect-failure"))
        api_factory.assert_called_once_with(
            "iqoption.com",
            "test@example.com",
            "not-a-real-password",
        )
        api.set_session.assert_called_once_with(
            headers=iq.SESSION_HEADER,
            cookies=iq.SESSION_COOKIE,
        )
        api.connect.assert_called_once_with()

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


    def test_heartbeat_forwards_no_force_send(self):
        api = Mock()
        api.timesync.server_timestamp = 1234567890

        Heartbeat(api)(1234567890)

        api.send_websocket_request.assert_called_once_with(
            "heartbeat",
            {"msg": {
                "heartbeatTime": 1234567890,
                "userTime": 1234567890000,
            }},
            unittest.mock.ANY,
            no_force_send=False,
        )

    def test_candle_mailbox_is_isolated_across_reconnections(self):
        # An old websocket reader may still deliver a late candles frame.
        # Its response must not appear in the newly connected API.
        from iqoptionapi.ws.received.candles import candles as receive_candles

        previous_api = IQOptionAPI(
            "iqoption.com", "test-user", "test-password"
        )
        current_api = IQOptionAPI(
            "iqoption.com", "test-user", "test-password"
        )
        self.assertIsNot(previous_api.candles, current_api.candles)

        receive_candles(previous_api, {
            "name": "candles", "msg": {"candles": [{"from": 123}]}
        })

        self.assertEqual(
            previous_api.candles.candles_data, [{"from": 123}]
        )
        self.assertIsNone(current_api.candles.candles_data)

    def test_websocket_send_serializes_concurrent_callers(self):
        api = IQOptionAPI.__new__(IQOptionAPI)
        api._websocket_send_lock = threading.Lock()
        api.websocket_client = Mock()
        active = 0
        peak = 0
        observations_lock = threading.Lock()
        errors = []
        start = threading.Barrier(3)

        def send(_data):
            nonlocal active, peak
            with observations_lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with observations_lock:
                active -= 1

        api.websocket_client.wss.send.side_effect = send

        def worker():
            try:
                start.wait(timeout=2)
                api.send_websocket_request(
                    "concurrency-test", {}, no_force_send=False
                )
            except Exception as exc:
                errors.append(exc)

        with patch.object(
            global_value, "ssl_Mutual_exclusion", False
        ), patch.object(
            global_value, "ssl_Mutual_exclusion_write", False
        ):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            start.wait(timeout=2)
            for thread in threads:
                thread.join(timeout=2)

        self.assertFalse(errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(peak, 1)
        self.assertEqual(api.websocket_client.wss.send.call_count, 2)

    def test_websocket_close_uses_bounded_thread_join(self):
        api = IQOptionAPI.__new__(IQOptionAPI)
        api.websocket_client = Mock()
        api.websocket_thread = Mock()
        api.websocket_thread.is_alive.return_value = True

        result = api.close(timeout=0.25)

        self.assertFalse(result)
        api.websocket_client.wss.close.assert_called_once_with(timeout=0)
        api.websocket_thread.join.assert_called_once_with(timeout=0.25)

    def test_websocket_close_force_closes_transport_during_handshake(self):
        api = IQOptionAPI.__new__(IQOptionAPI)
        transport = Mock()
        core_socket = Mock()
        core_socket.connected = False
        core_socket.sock = transport
        websocket_app = Mock()
        websocket_app.sock = core_socket
        api.websocket_client = Mock(wss=websocket_app)
        api.websocket_thread = Mock()
        api.websocket_thread.is_alive.return_value = False

        self.assertTrue(api.close(timeout=0.25))

        websocket_app.close.assert_called_once_with(timeout=0)
        transport.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        transport.close.assert_called_once_with()

    def test_websocket_message_diagnostics_store_channel_name_only(self):
        api = Mock()
        api.websocket_message_counts = Counter()
        client = WebsocketClient.__new__(WebsocketClient)
        client.api = api

        client.on_message(json.dumps({"name": "diagnostic-channel"}))

        self.assertEqual(api.websocket_message_counts, {
            "diagnostic-channel": 1,
        })

    def test_websocket_open_timeout_closes_socket_and_returns(self):
        class FakeThread:
            def __init__(self, *args, **kwargs):
                self.join_timeout = None

            def start(self):
                pass

            def join(self, timeout=None):
                self.join_timeout = timeout

            def is_alive(self):
                return False

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
        websocket_client.wss.close.assert_called_once_with(timeout=0)
        self.assertEqual(thread.join_timeout, 1.0)

    def test_reconnect_stops_when_previous_websocket_cannot_be_closed(self):
        iq = IQ_Option.__new__(IQ_Option)
        iq.api = Mock()
        iq.api.close.return_value = False

        result = iq.connect()

        self.assertEqual(result, (False, "WEBSOCKET_CLOSE_TIMEOUT"))
        iq.api.close.assert_called_once_with(timeout=2.0)
