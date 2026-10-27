import unittest

from indicadores import calcular_rsi


class RSIWilderTests(unittest.TestCase):
    def test_sin_datos_suficientes(self):
        self.assertIsNone(calcular_rsi([100.0] * 14, period=14))

    def test_precio_plano_es_neutral(self):
        self.assertEqual(calcular_rsi([100.0] * 30), 50.0)

    def test_tendencia_ascendente_pura(self):
        self.assertEqual(calcular_rsi(list(range(30))), 100.0)

    def test_tendencia_descendente_pura(self):
        self.assertEqual(calcular_rsi(list(range(30, 0, -1))), 0.0)

    def test_suavizado_wilder_no_media_movil_simple(self):
        # Tras cuatro subidas y dos bajadas, la media simple
        # de los últimos dos cambios sería RSI=0. Wilder=25.
        precios = [100, 101, 102, 103, 104, 103, 102]
        self.assertAlmostEqual(calcular_rsi(precios, period=2), 25.0)

    def test_no_acepta_nan(self):
        self.assertIsNone(calcular_rsi([100.0] * 14 + [float("nan")]))


if __name__ == "__main__":
    unittest.main()
