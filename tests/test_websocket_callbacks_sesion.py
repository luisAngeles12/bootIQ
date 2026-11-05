"""Aislamiento de callbacks tardios entre sesiones websocket."""
import unittest
from types import SimpleNamespace

from iqoptionapi.ws.client import WebsocketClient
import iqoptionapi.global_value as global_value


class TestCallbacksWebsocketPorSesion(unittest.TestCase):
    def setUp(self):
        self.anterior = (
            global_value.check_websocket_if_connect,
            global_value.check_websocket_if_error,
            global_value.websocket_error_reason,
        )
        self.api = SimpleNamespace(websocket_client=None)
        self.vieja = WebsocketClient.__new__(WebsocketClient)
        self.nueva = WebsocketClient.__new__(WebsocketClient)
        self.vieja.api = self.api
        self.nueva.api = self.api
        self.vieja.wss = object()
        self.nueva.wss = object()
        self.api.websocket_client = self.nueva
        global_value.check_websocket_if_connect = 1
        global_value.check_websocket_if_error = False
        global_value.websocket_error_reason = None

    def tearDown(self):
        (global_value.check_websocket_if_connect,
         global_value.check_websocket_if_error,
         global_value.websocket_error_reason) = self.anterior

    def test_close_tardio_no_desconecta_sesion_nueva(self):
        self.vieja.on_close(self.vieja.wss, 1006, "late")
        self.assertEqual(global_value.check_websocket_if_connect, 1)

    def test_error_tardio_no_invalida_sesion_nueva(self):
        self.vieja.on_error(self.vieja.wss, RuntimeError("late"))
        self.assertFalse(global_value.check_websocket_if_error)
        self.assertIsNone(global_value.websocket_error_reason)

    def test_open_tardio_no_confirma_sesion_nueva(self):
        global_value.check_websocket_if_connect = None
        self.vieja.on_open(self.vieja.wss)
        self.assertIsNone(global_value.check_websocket_if_connect)

    def test_callback_con_socket_equivocado_es_ignorado(self):
        self.nueva.on_close(object())
        self.assertEqual(global_value.check_websocket_if_connect, 1)

    def test_close_sin_argumentos_funciona_en_sesion_actual(self):
        # Reproduce el callback real reportado por websocket-client.
        self.nueva.on_close()
        self.assertEqual(global_value.check_websocket_if_connect, 0)

    def test_close_sin_argumentos_de_sesion_vieja_se_ignora(self):
        self.vieja.on_close()
        self.assertEqual(global_value.check_websocket_if_connect, 1)

    def test_callbacks_actuales_siguen_funcionando(self):
        self.nueva.on_close(self.nueva.wss)
        self.assertEqual(global_value.check_websocket_if_connect, 0)
        self.nueva.on_open(self.nueva.wss)
        self.assertEqual(global_value.check_websocket_if_connect, 1)
        self.nueva.on_error(self.nueva.wss, RuntimeError("real"))
        self.assertTrue(global_value.check_websocket_if_error)
        self.assertEqual(global_value.websocket_error_reason, "real")


if __name__ == "__main__":
    unittest.main()
