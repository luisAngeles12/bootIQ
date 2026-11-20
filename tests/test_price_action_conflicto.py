import unittest
from unittest.mock import patch

from price_action import patron_price_action_avanzado


class PriceActionConflictTests(unittest.TestCase):
    def test_opposing_candle_patterns_return_neutral(self):
        with (
            patch(
                "price_action.morning_evening_star",
                return_value=(1, "morning star alcista"),
            ),
            patch(
                "price_action.pin_bar",
                return_value=(-1, "pin bar bajista"),
            ),
            patch(
                "price_action.martillo_shooting_star",
                return_value=(0, "sin martillo"),
            ),
            patch(
                "price_action.patron_velas",
                return_value=(0, "sin patrón"),
            ),
            patch(
                "price_action.ruptura_master_candle",
                return_value=(0, "sin ruptura"),
            ),
        ):
            resultado = patron_price_action_avanzado(
                [1.0] * 6,
                [1.0] * 6,
                [1.0] * 6,
                [1.0] * 6,
            )

        self.assertEqual(resultado, (0, "patrones en conflicto", 0))

    def test_agreeing_patterns_keep_the_strongest_pattern(self):
        with (
            patch(
                "price_action.morning_evening_star",
                return_value=(1, "morning star alcista"),
            ),
            patch(
                "price_action.pin_bar",
                return_value=(1, "pin bar alcista"),
            ),
            patch(
                "price_action.martillo_shooting_star",
                return_value=(0, "sin martillo"),
            ),
            patch(
                "price_action.patron_velas",
                return_value=(0, "sin patrón"),
            ),
            patch(
                "price_action.ruptura_master_candle",
                return_value=(0, "sin ruptura"),
            ),
        ):
            resultado = patron_price_action_avanzado(
                [1.0] * 6,
                [1.0] * 6,
                [1.0] * 6,
                [1.0] * 6,
            )

        self.assertEqual(resultado, (1, "morning star alcista", 5))


if __name__ == "__main__":
    unittest.main()
