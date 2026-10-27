import unittest

from diagnostico_breakout_retest_sombra import diagnosticar_breakout_retest_sombra
from zonas import soporte_resistencia_zonas, breakout_retest


class BreakoutRetestSombraTests(unittest.TestCase):
    @staticmethod
    def caso_call():
        opens = [99.5] * 118 + [99.7, 100.5]
        closes = [99.5] * 118 + [100.8, 100.6]
        highs = [100.0] * 118 + [101.0, 100.9]
        lows = [99.0] * 118 + [99.6, 100.02]
        return opens, closes, highs, lows

    def test_call_previa_resistencia(self):
        resultado = diagnosticar_breakout_retest_sombra(*self.caso_call())
        self.assertEqual(resultado["br_call_sombra"], 1)
        self.assertEqual(resultado["br_put_sombra"], 0)
        self.assertAlmostEqual(resultado["br_call_nivel_sombra"], 100.0)

    def test_put_previo_soporte(self):
        opens, closes, highs, lows = self.caso_call()
        mirror = lambda xs: [205.0 - x for x in xs]
        resultado = diagnosticar_breakout_retest_sombra(
            mirror(opens), mirror(closes), mirror(lows), mirror(highs)
        )
        self.assertEqual(resultado["br_call_sombra"], 0)
        self.assertEqual(resultado["br_put_sombra"], -1)
        self.assertAlmostEqual(resultado["br_put_nivel_sombra"], 105.0)

    def test_diferencial_detector_operativo_permanece_intacto(self):
        opens, closes, highs, lows = self.caso_call()
        vol = sum(h - l for h, l in zip(highs[-14:], lows[-14:])) / 14
        soporte, resistencia = soporte_resistencia_zonas(
            closes[-1], highs, lows, vol
        )
        resultado_original, _ = breakout_retest(
            opens, closes, highs, lows, resistencia, "resistencia"
        )
        self.assertEqual(resultado_original, 0)
        resultado_sombra = diagnosticar_breakout_retest_sombra(
            opens, closes, highs, lows
        )
        self.assertEqual(resultado_sombra["br_call_sombra"], 1)

    def test_diferencial_put_no_activa_detector_original(self):
        opens, closes, highs, lows = self.caso_call()
        espejo = lambda xs: [205.0 - x for x in xs]
        opens, closes, highs, lows = (
            espejo(opens), espejo(closes), espejo(lows), espejo(highs)
        )
        vol = sum(h - l for h, l in zip(highs[-14:], lows[-14:])) / 14
        soporte, resistencia = soporte_resistencia_zonas(
            closes[-1], highs, lows, vol
        )
        resultado_original, _ = breakout_retest(
            opens, closes, highs, lows, soporte, "soporte"
        )
        self.assertEqual(resultado_original, 0)
        resultado_sombra = diagnosticar_breakout_retest_sombra(
            opens, closes, highs, lows
        )
        self.assertEqual(resultado_sombra["br_put_sombra"], -1)

    def test_no_retest_no_senal(self):
        opens, closes, highs, lows = self.caso_call()
        lows[-1] = 100.6
        resultado = diagnosticar_breakout_retest_sombra(opens, closes, highs, lows)
        self.assertEqual(resultado["br_call_sombra"], 0)

    def test_cierre_contrario_no_senal(self):
        opens, closes, highs, lows = self.caso_call()
        closes[-1] = 99.9
        resultado = diagnosticar_breakout_retest_sombra(opens, closes, highs, lows)
        self.assertEqual(resultado["br_call_sombra"], 0)

    def test_sin_datos_suficientes_neutral(self):
        resultado = diagnosticar_breakout_retest_sombra(
            [1] * 10, [1] * 10, [2] * 10, [0] * 10
        )
        self.assertEqual(resultado["br_call_sombra"], 0)
        self.assertIsNone(resultado["br_put_nivel_sombra"])

    def test_nivel_previo_no_se_recalcula_con_velas_de_ruptura(self):
        # Un pico exagerado en las velas de ruptura/retest no puede
        # alterar la zona histórica: highs[:-2] excluye ambas.
        opens, closes, highs, lows = self.caso_call()
        resultado_antes = diagnosticar_breakout_retest_sombra(
            opens, closes, highs, lows
        )
        highs[-2] = 120.0
        highs[-1] = 130.0
        resultado_despues = diagnosticar_breakout_retest_sombra(
            opens, closes, highs, lows
        )
        self.assertEqual(
            resultado_antes["br_call_nivel_sombra"],
            resultado_despues["br_call_nivel_sombra"],
        )


if __name__ == "__main__":
    unittest.main()
