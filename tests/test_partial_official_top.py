import unittest
from unittest.mock import patch

import bot
import estado
from mercado import CANDLE_TIME, VELAS_CACHE_CERRADAS


def valid_buffer():
    return [{"from": i * CANDLE_TIME} for i in range(VELAS_CACHE_CERRADAS)]


class PartialOfficialTopTests(unittest.TestCase):
    def test_nineteen_valid_and_one_missing_can_be_analyzed(self):
        activos = [{"activo": f"A{i}"} for i in range(20)]
        buffers = {f"A{i}": valid_buffer() for i in range(19)}
        with patch.object(estado, "velas_cache", buffers):
            validos, faltantes = bot._filtrar_activos_con_buffer(activos)
        self.assertEqual(len(validos), 19)
        self.assertEqual(faltantes, ["A19"])

    def test_one_valid_market_is_sufficient(self):
        activos = [{"activo": "VALIDO"}, {"activo": "SIN_BUFFER"}]
        with patch.object(estado, "velas_cache", {"VALIDO": valid_buffer()}):
            validos, faltantes = bot._filtrar_activos_con_buffer(activos)
        self.assertEqual([item["activo"] for item in validos], ["VALIDO"])
        self.assertEqual(faltantes, ["SIN_BUFFER"])

    def test_discontinuous_buffers_are_not_analyzed(self):
        activos = [{"activo": "INVALIDO"}]
        candles = valid_buffer()
        candles[-1]["from"] += CANDLE_TIME
        with patch.object(estado, "velas_cache", {"INVALIDO": candles}):
            validos, faltantes = bot._filtrar_activos_con_buffer(activos)
        self.assertEqual(validos, [])
        self.assertEqual(faltantes, ["INVALIDO"])


if __name__ == "__main__":
    unittest.main()
