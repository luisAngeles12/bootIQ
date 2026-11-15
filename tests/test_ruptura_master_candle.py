"""Regresion causal master candle: ruptura solo con vela posterior cerrada."""
import unittest

from price_action import master_candle, ruptura_master_candle


class RupturaMasterCandleTest(unittest.TestCase):
    def setUp(self):
        # Vela maestra [90, 110], cuatro interiores [95, 105].
        self.highs = [110, 105, 104, 106, 103]
        self.lows = [90, 95, 96, 94, 97]
        self.closes = [100, 101, 100, 102, 99]

    def test_master_previo_valido(self):
        existe, superior, inferior, _ = master_candle(
            self.highs, self.lows, 4
        )
        self.assertTrue(existe)
        self.assertEqual((superior, inferior), (110, 90))

    def test_ruptura_alcista_posterior(self):
        self.assertEqual(
            ruptura_master_candle(
                self.closes + [112],
                self.highs + [113],
                self.lows + [101],
            )[0], 1
        )

    def test_ruptura_bajista_posterior(self):
        self.assertEqual(
            ruptura_master_candle(
                self.closes + [88],
                self.highs + [99],
                self.lows + [87],
            )[0], -1
        )

    def test_sin_ruptura_si_cierra_dentro(self):
        self.assertEqual(
            ruptura_master_candle(
                self.closes + [105],
                self.highs + [108],
                self.lows + [96],
            )[0], 0
        )

    def test_sin_master_previo_no_inventa_ruptura(self):
        highs = [110, 105, 111, 106, 103, 113]
        lows = [90, 95, 96, 94, 97, 101]
        self.assertEqual(
            ruptura_master_candle(self.closes + [112], highs, lows)[0], 0
        )

    def test_historia_insuficiente_es_neutra(self):
        self.assertEqual(
            ruptura_master_candle(
                [100, 101, 102, 103, 104],
                [110, 105, 104, 106, 103],
                [90, 95, 96, 94, 97],
            )[0], 0
        )

    def test_ultimo_cierre_no_se_usa_en_master_previo(self):
        # Cierre extraordinario de la vela de ruptura no puede
        # contaminar la ventana anterior de contencion.
        r1 = ruptura_master_candle(
            self.closes + [112], self.highs + [113], self.lows + [101]
        )
        r2 = ruptura_master_candle(
            self.closes + [120], self.highs + [121], self.lows + [101]
        )
        self.assertEqual(r1[0], r2[0])


if __name__ == "__main__":
    unittest.main()
