import ast
import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mercado import (
    CANDLE_TIME,
    VELAS_CACHE_CERRADAS,
    _datos_desde_velas,
)
from utils import vela_ohlc_valida


def cargar_lector_backtest_aislado():
    ruta = Path(__file__).resolve().parents[1] / "backtest_bot_real.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    funcion = next(
        nodo for nodo in arbol.body
        if isinstance(nodo, ast.FunctionDef)
        and nodo.name == "leer_csv_velas"
    )
    modulo = ast.fix_missing_locations(
        ast.Module(body=[funcion], type_ignores=[])
    )
    ambito = {"csv": csv, "vela_ohlc_valida": vela_ohlc_valida}
    exec(compile(modulo, str(ruta), "exec"), ambito)
    return ambito["leer_csv_velas"]


class VelaOhlcValidationTests(unittest.TestCase):
    def test_accepts_valid_candle_and_flat_doji(self):
        self.assertTrue(vela_ohlc_valida("100", "100.5", "101", "99"))
        self.assertTrue(vela_ohlc_valida(100, 100, 100, 100))

    def test_rejects_prices_outside_candle_range(self):
        self.assertFalse(vela_ohlc_valida(100, 101, 100.5, 99))
        self.assertFalse(vela_ohlc_valida(100, 100.5, 101, 100.1))
        self.assertFalse(vela_ohlc_valida(100, 100, 99, 101))

    def test_rejects_non_finite_or_non_numeric_prices(self):
        self.assertFalse(vela_ohlc_valida(100, float("nan"), 101, 99))
        self.assertFalse(vela_ohlc_valida(100, 100, float("inf"), 99))
        self.assertFalse(vela_ohlc_valida(None, 100, 101, 99))

    def test_live_candle_conversion_fails_closed_on_invalid_ohlc(self):
        candles = [
            {
                "from": index * CANDLE_TIME,
                "open": 100.0,
                "close": 100.1,
                "max": 100.2,
                "min": 99.9,
            }
            for index in range(VELAS_CACHE_CERRADAS)
        ]
        self.assertIsNotNone(_datos_desde_velas(candles))

        candles[80]["max"] = 100.05
        self.assertIsNone(_datos_desde_velas(candles))

    def test_live_candle_conversion_rejects_non_finite_ohlc(self):
        candles = [
            {
                "from": index * CANDLE_TIME,
                "open": 100.0,
                "close": 100.1,
                "max": 100.2,
                "min": 99.9,
            }
            for index in range(VELAS_CACHE_CERRADAS)
        ]
        candles[-1]["close"] = float("nan")
        self.assertIsNone(_datos_desde_velas(candles))

    def test_backtest_reader_rejects_invalid_ohlc_row(self):
        leer_csv_velas = cargar_lector_backtest_aislado()
        with TemporaryDirectory() as temp:
            path = Path(temp) / "velas.csv"
            path.write_text(
                "from,open,close,max,min\n"
                "60,100,101,100.5,99\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "CSV_VELA_OHLC_INVALIDA"):
                leer_csv_velas(str(path))


if __name__ == "__main__":
    unittest.main()
