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
                "fallo_velas_ronda_d76d",
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
        estado.fallo_velas_ronda_d76d = False

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

    def test_missing_open_time_preserves_healthy_official_top(self):
        estado.activos_cache = [{"activo": "healthy", "score_filtro": 70}]
        estado.velas_cache = {
            "healthy": [
                {"from": i * mercado.CANDLE_TIME}
                for i in range(mercado.VELAS_CACHE_CERRADAS)
            ]
        }
        with patch.object(mercado, "reconectar_iq") as reconnect:
            mercado.refrescar_activos_incremental()
            mercado.refrescar_activos_incremental()
        reconnect.assert_not_called()
        self.assertEqual(estado.fallos_open_time, 0)
        self.assertEqual(len(estado.velas_cache["healthy"]), mercado.VELAS_CACHE_CERRADAS)

    def test_asset_scan_uses_candle_api_timeout_budget(self):
        class NoCandlesIQ(FakeIQ):
            def get_candles(self, *_args, **kwargs):
                self.candle_kwargs = kwargs
                return None

        estado.Iq = NoCandlesIQ({})
        estado.metricas_ronda = {"scan_candles_none": 0}

        self.assertIsNone(
            mercado.evaluar_estabilidad_activo(
                "asset",
                "turbo",
            )
        )
        self.assertEqual(
            estado.Iq.candle_kwargs,
            {
                "timeout": mercado.TIMEOUT_CANDLES_SCAN,
                "drain_timeout": mercado.DRENAJE_CANDLES_SCAN,
            },
        )

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
            - mercado.VELAS_CACHE_CERRADAS * mercado.CANDLE_TIME
        )
        complete_buffer = [
            {
                "from": start + index * mercado.CANDLE_TIME,
                "open": 1,
                "close": 1,
                "max": 1,
                "min": 1,
            }
            for index in range(mercado.VELAS_CACHE_CERRADAS)
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
            - mercado.VELAS_CACHE_CERRADAS * mercado.CANDLE_TIME
        )
        complete_buffer = [
            {
                "from": start + index * mercado.CANDLE_TIME,
                "open": 1,
                "close": 1,
                "max": 1,
                "min": 1,
            }
            for index in range(mercado.VELAS_CACHE_CERRADAS)
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

    def test_reconnect_rebuilds_official_buffers_before_open_time(self):
        now = int(time.time() // mercado.CANDLE_TIME) * mercado.CANDLE_TIME
        start = now - mercado.VELAS_CACHE_CERRADAS * mercado.CANDLE_TIME
        candles = [
            {"from": start + i * mercado.CANDLE_TIME,
             "open": 1, "close": 1, "max": 1, "min": 1}
            for i in range(mercado.VELAS_CACHE_CERRADAS)
        ]
        estado.activos_cache = [{"activo": "official-asset", "score_filtro": 90}]
        estado.velas_cache = {}
        estado.refresh_activos_top_pendiente = []
        with patch.object(mercado, "precargar_velas_activos") as preload:
            result = mercado.refrescar_activos_incremental()
        self.assertEqual(result, [])
        preload.assert_called_once_with(estado.activos_cache, podar_cache=False)
        self.assertFalse(hasattr(estado.Iq, "timeout"))

    def test_startup_messages_do_not_repeat_each_unprepared_candle(self):
        import inspect
        import bot
        source = inspect.getsource(bot.main)
        self.assertIn('ultimo_aviso_cache_sin_publicar != "PREPARANDO"', source)
        self.assertIn('analisis pausado hasta contar con cache valida', source)
        self.assertNotIn("bucket_aviso_cache =", source)

    def test_reconnect_keeps_failures_visible_without_attempt_counter(self):
        import inspect
        source = inspect.getsource(conexion.reconectar_iq)
        self.assertNotIn('f"Reconexión IQ {intento}/{intentos}', source)
        self.assertIn("Reconexión no confirmada:", source)
        self.assertIn("IQ Option reconectado correctamente.", source)

    def test_scanner_reports_rejection_breakdown_without_changing_thresholds(self):
        import inspect
        source = inspect.getsource(mercado.refrescar_activos_incremental)
        self.assertIn("D9.98 SCAN CAUSAS TOP20", source)
        self.assertIn('"scan_candles_none"', source)
        self.assertIn('"scan_continuidad_temporal"', source)
        self.assertIn('"scan_calidad"', source)
        self.assertIn('"scan_score"', source)
        self.assertIn('"scan_tendencia_indefinida"', source)
        self.assertIn('"scan_tendencia_debil"', source)
        self.assertIn('"scan_rango_debil"', source)
        self.assertIn('"scan_excepcion"', source)
        self.assertIn('"descartados_score"', source)
        self.assertIn("MAX_ACTIVOS_ANALIZAR", source)

    def test_candle_gap_diagnostics_identify_missing_intervals(self):
        candles = [
            {"from": 60}, {"from": 120}, {"from": 300},
            {"from": 360}, {"from": 360},
        ]
        result = mercado._diagnosticar_huecos_velas(candles)
        self.assertEqual(result["unicas"], 4)
        self.assertEqual(result["huecos"], 1)
        self.assertEqual(result["saltos_recientes"], [(120, 300, 2)])
        self.assertEqual(result["primera"], 60)
        self.assertEqual(result["ultima"], 360)

    def test_live_gate_accepts_up_to_twenty_with_valid_buffers(self):
        import inspect
        import bot

        source = inspect.getsource(bot.main)
        self.assertIn(
            "if not (0 < len(activos) <= MAX_ACTIVOS_ANALIZAR):",
            source,
        )
        self.assertIn(
            "MERCADOS SELECCIONADOS SIN BUFFERS VALIDOS",
            source,
        )
        self.assertNotIn(
            "if len(activos) != MAX_ACTIVOS_ANALIZAR:",
            source,
        )
        self.assertIn("_buffer_velas_integro(", source)
        self.assertNotIn(
            'if item["activo"] not in faltantes_buffer_d76d',
            source,
        )

    def test_fewer_than_twenty_valid_candidates_can_be_selected(self):
        now = int(time.time() // mercado.CANDLE_TIME) * mercado.CANDLE_TIME
        start = now - mercado.VELAS_CACHE_CERRADAS * mercado.CANDLE_TIME
        buffer = [
            {
                "from": start + i * mercado.CANDLE_TIME,
                "open": 1, "close": 1, "max": 1, "min": 1,
            }
            for i in range(mercado.VELAS_CACHE_CERRADAS)
        ]
        candidates = [
            {"activo": f"asset-{i:02}", "score_filtro": 90}
            for i in range(14)
        ]
        estado.velas_cache = {
            candidate["activo"]: list(buffer)
            for candidate in candidates
        }

        required, ready, count = mercado._seleccionar_top_con_buffers(candidates)

        self.assertEqual(required, 14)
        self.assertEqual(count, 14)
        self.assertEqual(len(ready), 14)
        self.assertEqual(len(ready), required)

    def test_top_target_stays_capped_at_twenty(self):
        candidates = [
            {"activo": f"asset-{index:02}", "score_filtro": 90}
            for index in range(24)
        ]
        required, _ready, _count = mercado._seleccionar_top_con_buffers(candidates)
        self.assertEqual(required, mercado.MAX_ACTIVOS_ANALIZAR)

    def test_preload_uses_bounded_candle_timeout(self):
        class RecordingIQ(FakeIQ):
            def get_candles(self, *_args, **kwargs):
                self.kwargs = kwargs
                return None

        estado.Iq = RecordingIQ({})
        mercado.precargar_velas_activos(
            ["asset-without-data"],
            podar_cache=False,
        )

        self.assertEqual(
            estado.Iq.kwargs["timeout"],
            min(6.0, mercado.PRESUPUESTO_PRECARGA_D76D - 1.0),
        )
        self.assertEqual(
            estado.Iq.kwargs["drain_timeout"],
            1.0,
        )
        self.assertNotIn("asset-without-data", estado.velas_cache)

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
            def get_candles(self, _asset, _interval, count, *_args, **_kwargs):
                self.requested_count = count
                return candles

            def get_server_timestamp(self):
                return now

        estado.Iq = HistoricalIQ({})
        result = mercado.precargar_velas_activos(
            ["asset-with-old-gap"],
        )

        buffer = estado.velas_cache["asset-with-old-gap"]
        self.assertEqual(result["nuevos"], 1)
        self.assertEqual(
            estado.Iq.requested_count,
            mercado.VELAS_CACHE_SOLICITADAS,
        )
        self.assertEqual(len(candles), 999)
        self.assertEqual(len(buffer), mercado.VELAS_CACHE_CERRADAS)
        self.assertTrue(mercado._buffer_velas_integro(buffer))
        self.assertEqual(
            buffer[-1]["from"],
            candles[-1]["from"],
        )

    def test_stale_candles_invalidate_only_the_affected_asset_buffer(self):
        now = int(time.time() // mercado.CANDLE_TIME) * mercado.CANDLE_TIME
        expected = now - mercado.CANDLE_TIME
        stale_last = expected - 2 * mercado.CANDLE_TIME
        start = (
            stale_last
            - (mercado.VELAS_CACHE_CERRADAS - 1)
            * mercado.CANDLE_TIME
        )
        buffer = [
            {
                "from": start + index * mercado.CANDLE_TIME,
                "open": 1,
                "close": 1,
                "max": 1,
                "min": 1,
            }
            for index in range(mercado.VELAS_CACHE_CERRADAS)
        ]
        stale_recent = [
            {
                "from": stale_last - 3 * mercado.CANDLE_TIME
                + index * mercado.CANDLE_TIME,
                "open": 1,
                "close": 1,
                "max": 1,
                "min": 1,
            }
            for index in range(4)
        ]

        class StaleCandlesIQ(FakeIQ):
            def get_server_timestamp(self):
                return now

            def get_candles(self, *_args, **_kwargs):
                return stale_recent

        estado.Iq = StaleCandlesIQ({})
        estado.velas_cache = {"stale-asset": buffer}
        estado.fallo_velas_ronda_d76d = False

        self.assertIsNone(mercado.obtener_velas("stale-asset"))
        self.assertFalse(estado.fallo_velas_ronda_d76d)
        self.assertNotIn("stale-asset", estado.velas_cache)

    def test_disconnected_iq_still_invalidates_the_round(self):
        class DisconnectedIQ(FakeIQ):
            def check_connect(self):
                return False

        estado.Iq = DisconnectedIQ({})
        estado.fallo_velas_ronda_d76d = False

        self.assertIsNone(mercado.obtener_velas("asset"))
        self.assertTrue(estado.fallo_velas_ronda_d76d)

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

    def test_late_initialization_data_id_completes_single_pending_request(self):
        payload = {"binary": {"actives": {"101": {"name": "binary.EURUSD"}}}}
        api = type("FakeAPI", (), {})()
        api.api_option_init_all_result_v2_by_request = {
            "current-request": None,
        }

        initialization_data(
            api,
            {
                "name": "initialization-data",
                "request_id": "expired-request",
                "msg": payload,
            },
        )

        self.assertEqual(
            api.api_option_init_all_result_v2_by_request[
                "current-request"
            ],
            payload,
        )

    def test_late_initialization_data_id_is_ignored_when_requests_are_ambiguous(self):
        api = type("FakeAPI", (), {})()
        api.api_option_init_all_result_v2_by_request = {
            "request-one": None,
            "request-two": None,
        }

        initialization_data(
            api,
            {
                "name": "initialization-data",
                "request_id": "expired-request",
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

    def test_initialization_data_request_uses_numeric_correlated_id(self):
        payload = {
            "binary": {"actives": {"101": {"name": "binary.EURUSD"}}},
            "turbo": {"actives": {"102": {"name": "turbo.USDJPY"}}},
        }

        class FakeAPI:
            def get_api_option_init_all_v2(self, request_id):
                self.request_id = request_id
                initialization_data(
                    self,
                    {
                        "name": "initialization-data",
                        "request_id": request_id,
                        "msg": payload,
                    },
                )

        iq = IQ_Option.__new__(IQ_Option)
        iq.api = FakeAPI()
        iq.check_connect = lambda: True

        result = iq.get_all_init_v2(timeout=0.2)

        self.assertTrue(iq.api.request_id.isdigit())
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main()
