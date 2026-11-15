"""Regresion causal CHOCH: la referencia debe incluir la vela -2.

No hay IQ, trading, ni nuevos umbrales. Prueba solo la ventana
temporal usada por el detector existente.
"""
import unittest

from contexto_grafico import detectar_cambio_estructura_choch


class ChochReferenciaTemporalTest(unittest.TestCase):
    def preparar(self, highs, lows, apertura, cierre):
        opens = [100.0] * (len(highs) - 1) + [apertura]
        closes = [100.0] * (len(highs) - 1) + [cierre]
        return detectar_cambio_estructura_choch(
            highs, lows, closes, opens, lookback=10
        )

    def test_maximo_de_vela_anterior_no_se_omite(self):
        # La vela previa ya alcanzo 115. El cierre 112 no rompe 115.
        highs = [105.0] * 12 + [115.0, 113.0]
        lows = [90.0] * 13 + [100.0]
        resultado, _ = self.preparar(highs, lows, 102.0, 112.0)
        self.assertEqual(resultado, 0)

    def test_minimo_de_vela_anterior_no_se_omite(self):
        # La vela previa ya alcanzo 85. El cierre 88 no rompe 85.
        highs = [110.0] * 13 + [100.0]
        lows = [95.0] * 12 + [85.0, 87.0]
        resultado, _ = self.preparar(highs, lows, 98.0, 88.0)
        self.assertEqual(resultado, 0)

    def test_ruptura_alcista_nueva_sigue_detectandose(self):
        highs = [105.0] * 13 + [114.0]
        lows = [90.0] * 13 + [100.0]
        resultado, _ = self.preparar(highs, lows, 101.0, 112.0)
        self.assertEqual(resultado, 1)

    def test_ruptura_bajista_nueva_sigue_detectandose(self):
        highs = [110.0] * 13 + [100.0]
        lows = [95.0] * 13 + [86.0]
        resultado, _ = self.preparar(highs, lows, 99.0, 88.0)
        self.assertEqual(resultado, -1)

    def test_velas_insuficientes_no_crean_choch(self):
        highs = [105.0] * 13
        lows = [95.0] * 13
        resultado, _ = self.preparar(highs, lows, 100.0, 104.0)
        self.assertEqual(resultado, 0)


if __name__ == "__main__":
    unittest.main()
