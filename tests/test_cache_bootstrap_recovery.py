import unittest
from unittest.mock import patch

import conexion
import estado
import mercado
import iqoptionapi.constants as OP_code
from iqoptionapi.stable_api import IQ_Option


class FakeIQ:
    def __init__(self, open_time):
        self.open_time = open_time

    def check_connect(self):
        return True

    def get_all_open_time(self, timeout):
        self.timeout = timeout
        return self.open_time


class CacheBootstrapRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.original_state = {
            name: getattr(estado, name)
            for name in (
                "Iq",
                "velas_cache",
                "ultima_actualizacion_activos",
                "activos_cache",
                "activos_invalidos",
                "cooldown_activos",
                "metricas_ronda",
                "refresh_activos_en_progreso",
                "refresh_activos_universo",
                "refresh_activos_indice",
                "refresh_activos_candidatos",
                "refresh_activos_vistos",
                "refresh_activos_inicio",
                "refresh_activos_top_pendiente",
                "fallos_open_time",
            )
        }
        estado.Iq = FakeIQ({})
        estado.activos_cache = []
        estado.activos_invalidos = set()
        estado.cooldown_activos = {}
        estado.metricas_ronda = {
            "uso_cache_activos": 0,
            "compatibles_antes_top": 0,
        }
        estado.refresh_activos_en_progreso = False
        estado.refresh_activos_universo = []
        estado.refresh_activos_indice = 0
        estado.refresh_activos_candidatos = []
        estado.refresh_activos_vistos = set()
        estado.refresh_activos_inicio = 0.0
        estado.refresh_activos_top_pendiente = []
        estado.fallos_open_time = 0

    def tearDown(self):
        for name, value in self.original_state.items():
            setattr(estado, name, value)

    def test_reconnects_after_two_consecutive_missing_open_time_responses(self):
        with patch.object(mercado, "reconectar_iq", return_value=True) as reconnect:
            mercado.refrescar_activos_incremental()
            self.assertEqual(estado.fallos_open_time, 1)
            reconnect.assert_not_called()

            mercado.refrescar_activos_incremental()

        reconnect.assert_called_once_with(forzar=True)
        self.assertEqual(estado.fallos_open_time, 0)

    def test_valid_open_time_response_resets_missing_response_count(self):
        with patch.object(mercado, "reconectar_iq") as reconnect:
            estado.fallos_open_time = 1
            estado.Iq = FakeIQ({
                "turbo": {
                    "closed-asset": {"open": False},
                },
            })

            mercado.refrescar_activos_incremental()

        self.assertEqual(estado.fallos_open_time, 0)
        reconnect.assert_not_called()

    def test_forced_reconnect_rebuilds_an_open_but_unresponsive_session(self):
        class ConnectedIQ:
            _bootiq_init_v2_bootstrap = {"stale": True}

            def __init__(self):
                self.connect_calls = 0

            def check_connect(self):
                return True

            def connect(self):
                self.connect_calls += 1
                return True, None

            def change_balance(self, mode):
                self.balance_mode = mode

            def get_balance_mode(self):
                return "PRACTICE"

        iq = ConnectedIQ()
        estado.Iq = iq
        estado.velas_cache = {"old": [1]}
        estado.ultima_actualizacion_activos = 123

        with patch.object(conexion.time, "sleep"):
            self.assertTrue(conexion.reconectar_iq(forzar=True))

        self.assertEqual(iq.connect_calls, 1)
        self.assertEqual(estado.velas_cache, {})
        self.assertEqual(estado.ultima_actualizacion_activos, 0)
        self.assertEqual(estado.fallos_open_time, 0)
        self.assertIsNone(iq._bootiq_init_v2_bootstrap)

    def test_opcode_uses_bounded_legacy_initialization_after_v2_failure(self):
        legacy_response = {
            "isSuccessful": True,
            "result": {
                "binary": {
                    "actives": {
                        "101": {
                            "name": "binary.EURUSD",
                            "enabled": True,
                            "is_suspended": False,
                        },
                    },
                },
                "turbo": {
                    "actives": {
                        "102": {
                            "name": "turbo.USDJPY",
                            "enabled": True,
                            "is_suspended": False,
                        },
                    },
                },
            },
        }

        class FakeAPI:
            api_option_init_all_result = None

            def get_api_option_init_all(self):
                self.api_option_init_all_result = legacy_response

        iq = IQ_Option.__new__(IQ_Option)
        iq.api = FakeAPI()
        iq.check_connect = lambda: True
        iq._bootiq_init_v2_bootstrap = None
        original_actives = dict(OP_code.ACTIVES)

        try:
            with patch.object(
                iq,
                "get_all_init_v2",
                return_value=None,
            ):
                iq.get_ALL_Binary_ACTIVES_OPCODE(timeout=0.2)

            self.assertEqual(OP_code.ACTIVES["EURUSD"], 101)
            self.assertEqual(OP_code.ACTIVES["USDJPY"], 102)
            self.assertEqual(
                iq._bootiq_init_v2_bootstrap,
                legacy_response["result"],
            )

            open_time = iq.get_all_open_time(timeout=0.2)
            self.assertTrue(open_time["binary"]["EURUSD"]["open"])
            self.assertTrue(open_time["turbo"]["USDJPY"]["open"])
            self.assertIsNone(iq._bootiq_init_v2_bootstrap)
        finally:
            OP_code.ACTIVES.clear()
            OP_code.ACTIVES.update(original_actives)


if __name__ == "__main__":
    unittest.main()
