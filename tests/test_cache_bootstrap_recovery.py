import time
import unittest
from unittest.mock import patch

import conexion
import estado
import mercado
import iqoptionapi.constants as OP_code
from iqoptionapi.stable_api import IQ_Option
from iqoptionapi.ws.received.initialization_data import initialization_data


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
                "refresh_activos_buffer_indice",
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
        estado.refresh_activos_buffer_indice = 0
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

    def test_pending_top_uses_buffered_candidates_to_fill_ranked_top(self):
        candidates = [
            {
                "activo": f"asset-{index:02}",
                "score_filtro": 100 - index,
            }
            for index in range(21)
        ]
        start = (
            int(time.time() // mercado.CANDLE_TIME)
            * mercado.CANDLE_TIME
            - 130 * mercado.CANDLE_TIME
        )
        complete_buffer = [
            {
                "from": start + index * mercado.CANDLE_TIME,
                "open": 1,
                "close": 1,
                "max": 1,
                "min": 1,
            }
            for index in range(130)
        ]
        estado.Iq = FakeIQ({})
        estado.refresh_activos_top_pendiente = candidates
        estado.velas_cache = {
            item["activo"]: list(complete_buffer)
            for item in candidates[1:]
        }

        with patch.object(
            mercado,
            "precargar_velas_activos",
        ):
            activos = mercado.refrescar_activos_incremental()

        self.assertEqual(
            [item["activo"] for item in activos],
            [item["activo"] for item in candidates[1:]],
        )
        self.assertEqual(
            len(estado.activos_cache),
            mercado.MAX_ACTIVOS_ANALIZAR,
        )
        self.assertEqual(
            set(estado.velas_cache),
            {item["activo"] for item in candidates[1:]},
        )

    def test_pending_buffer_preload_rotates_after_budget_exhaustion(self):
        start = (
            int(time.time() // mercado.CANDLE_TIME)
            * mercado.CANDLE_TIME
            - 130 * mercado.CANDLE_TIME
        )
        complete_buffer = [
            {
                "from": start + index * mercado.CANDLE_TIME,
                "open": 1,
                "close": 1,
                "max": 1,
                "min": 1,
            }
            for index in range(130)
        ]
        clock = [0.0]
        attempted = []

        class SlowIQ(FakeIQ):
            def get_candles(self, asset, *_args, **_kwargs):
                attempted.append(asset)
                clock[0] += 9.0
                if asset == "asset-01":
                    return None
                return complete_buffer

        estado.Iq = SlowIQ({})
        pending = [
            {"activo": f"asset-{index:02}"}
            for index in range(1, 4)
        ]

        with patch.object(
            mercado.time,
            "perf_counter",
            side_effect=lambda: clock[0],
        ):
            mercado.precargar_velas_activos(
                pending,
                podar_cache=False,
            )
            mercado.precargar_velas_activos(
                pending,
                podar_cache=False,
            )

        self.assertEqual(attempted, ["asset-01", "asset-02"])
        self.assertIn("asset-02", estado.velas_cache)
        self.assertEqual(
            estado.refresh_activos_buffer_indice,
            2,
        )

    def test_preload_keeps_recent_continuous_candles_after_old_history_gap(self):
        now = int(time.time() // mercado.CANDLE_TIME) * mercado.CANDLE_TIME
        start = now - 1001 * mercado.CANDLE_TIME
        candles = []
        for index in range(999):
            gap = mercado.CANDLE_TIME if index < 600 else 2 * mercado.CANDLE_TIME
            candles.append({
                "from": start + index * mercado.CANDLE_TIME + gap,
                "open": 1,
                "close": 1,
                "max": 1,
                "min": 1,
            })

        class HistoricalIQ(FakeIQ):
            def get_candles(self, *_args, **_kwargs):
                return candles

            def get_server_timestamp(self):
                return now

        estado.Iq = HistoricalIQ({})
        result = mercado.precargar_velas_activos(
            ["asset-with-old-gap"],
        )

        buffer = estado.velas_cache["asset-with-old-gap"]
        self.assertEqual(result["nuevos"], 1)
        self.assertEqual(len(candles), 999)
        self.assertEqual(len(buffer), 399)
        self.assertTrue(mercado._buffer_velas_integro(buffer))
        self.assertEqual(
            buffer[-1]["from"],
            candles[-1]["from"],
        )

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

    def test_opcode_rejects_incomplete_binary_turbo_initialization(self):
        incomplete_init = {
            "binary": {
                "actives": {
                    "101": {"name": "binary.EURUSD"},
                },
            },
            "turbo": {"actives": {}},
        }
        iq = IQ_Option.__new__(IQ_Option)
        iq.api = object()
        iq._bootiq_init_v2_bootstrap = {"stale": True}
        original_actives = dict(OP_code.ACTIVES)

        try:
            with patch.object(
                iq,
                "get_all_init_v2",
                return_value=incomplete_init,
            ), patch.object(
                iq,
                "_get_all_init_legacy_bounded",
                return_value=None,
            ), patch("iqoptionapi.stable_api.time.sleep"):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "sin activos válidos para: turbo",
                ):
                    iq.get_ALL_Binary_ACTIVES_OPCODE(timeout=0.2)

            self.assertEqual(OP_code.ACTIVES, original_actives)
            self.assertIsNone(iq._bootiq_init_v2_bootstrap)
        finally:
            OP_code.ACTIVES.clear()
            OP_code.ACTIVES.update(original_actives)

    def test_opcode_startup_retries_once_after_forced_reconnect(self):
        class FakeIQ:
            def __init__(self):
                self.opcode_attempts = 0

            def get_ALL_Binary_ACTIVES_OPCODE(self):
                self.opcode_attempts += 1
                if self.opcode_attempts == 1:
                    raise RuntimeError("stale initialization channel")

            def get_all_ACTIVES_OPCODE(self):
                return {"EURUSD": 1}

        iq = FakeIQ()
        estado.Iq = iq

        with patch.object(
            conexion,
            "reconectar_iq",
            return_value=True,
        ) as reconnect, patch.object(conexion.time, "sleep"):
            self.assertTrue(conexion.actualizar_activos_opcode())

        reconnect.assert_called_once_with(forzar=True)
        self.assertEqual(iq.opcode_attempts, 2)

    def test_opcode_startup_retries_until_opcode_recovers(self):
        class FakeIQ:
            def __init__(self):
                self.opcode_attempts = 0
                self.connection_checks = 0

            def check_connect(self):
                self.connection_checks += 1
                return True

            def get_ALL_Binary_ACTIVES_OPCODE(self):
                self.opcode_attempts += 1
                if self.opcode_attempts < 3:
                    raise RuntimeError("initialization unavailable")

            def get_all_ACTIVES_OPCODE(self):
                return {"EURUSD": 1}

        iq = FakeIQ()
        estado.Iq = iq

        with patch.object(
            conexion,
            "reconectar_iq",
            return_value=True,
        ) as reconnect, patch.object(conexion.time, "sleep"):
            self.assertTrue(
                conexion.actualizar_activos_opcode(
                    max_intentos=3,
                    espera_inicial=0,
                )
            )

        self.assertEqual(iq.opcode_attempts, 3)
        reconnect.assert_not_called()

    def test_opcode_failure_reconnects_only_if_socket_is_down(self):
        class FakeIQ:
            def __init__(self):
                self.opcode_attempts = 0

            def check_connect(self):
                return self.opcode_attempts > 1

            def get_ALL_Binary_ACTIVES_OPCODE(self):
                self.opcode_attempts += 1
                if self.opcode_attempts == 1:
                    raise RuntimeError("connection dropped")

            def get_all_ACTIVES_OPCODE(self):
                return {"EURUSD": 1}

        iq = FakeIQ()
        estado.Iq = iq

        with patch.object(
            conexion,
            "reconectar_iq",
            return_value=True,
        ) as reconnect, patch.object(conexion.time, "sleep"):
            self.assertTrue(
                conexion.actualizar_activos_opcode(
                    max_intentos=2,
                    espera_inicial=0,
                )
            )

        reconnect.assert_called_once_with(forzar=True)

    def test_opcode_startup_can_be_bounded_in_unit_tests(self):
        class FakeIQ:
            def get_ALL_Binary_ACTIVES_OPCODE(self):
                raise RuntimeError("initialization unavailable")

        estado.Iq = FakeIQ()

        with patch.object(
            conexion,
            "reconectar_iq",
            return_value=True,
        ) as reconnect, patch.object(conexion.time, "sleep"):
            self.assertFalse(
                conexion.actualizar_activos_opcode(
                    max_intentos=2,
                    espera_inicial=0,
                )
            )

        reconnect.assert_called_once_with(forzar=True)

    def test_initialization_data_without_request_id_completes_single_pending_request(self):
        payload = {"turbo": {"actives": {}}}
        api = type("FakeAPI", (), {})()
        api.api_option_init_all_result_v2_by_request = {
            "pending-request": None,
        }

        initialization_data(
            api,
            {
                "name": "initialization-data",
                "msg": payload,
            },
        )

        self.assertEqual(
            api.api_option_init_all_result_v2_by_request[
                "pending-request"
            ],
            payload,
        )

    def test_untagged_initialization_data_is_ignored_when_requests_are_ambiguous(self):
        api = type("FakeAPI", (), {})()
        api.api_option_init_all_result_v2_by_request = {
            "request-one": None,
            "request-two": None,
        }

        initialization_data(
            api,
            {
                "name": "initialization-data",
                "msg": {"turbo": {"actives": {}}},
            },
        )

        self.assertEqual(
            api.api_option_init_all_result_v2_by_request,
            {
                "request-one": None,
                "request-two": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
