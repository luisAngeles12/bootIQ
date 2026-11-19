"""Auditoria causal: cobertura de zonas anteriores y contaminacion de vela actual.

Solo compara implementaciones; NO cambia umbrales ni habilita operaciones.
"""
import unittest
from zonas import zonas_reales, soporte_resistencia_zonas


class AuditoriaZonasHistoricas(unittest.TestCase):
    def test_zona_previa_de_181_velas_puede_desaparecer_del_lookback_100(self):
        # Tres rechazos a un maximo antiguo, no presentes en las ultimas 100.
        highs = [110.0 if i in (10, 20, 30) else 102.0 for i in range(181)]
        lows = [99.0 for _ in highs]
        hist = zonas_reales(highs[:-1], lows[:-1],
                            minimo_toques=3, tolerancia_base=0.45)
        corta = zonas_reales(highs[-100:], lows[-100:],
                             minimo_toques=3, tolerancia_base=0.45)
        self.assertTrue(any(abs(z["precio"] - 110) < 0.45 for z in hist))
        self.assertFalse(any(abs(z["precio"] - 110) < 0.45 for z in corta))

    def test_ultima_vela_modifica_el_universo_de_zonas_actual(self):
        # El calculo vigente incluye la vela senal ([-100:]); una zona
        # antigua con 2 contactos se convierte en 3 solo por la senal.
        highs = [102.0 for _ in range(181)]
        for i in (150, 160):
            highs[i] = 110.0
        lows = [99.0 for _ in highs]
        historico_sin_senal = zonas_reales(highs[-101:-1], lows[-101:-1],
                                           minimo_toques=3, tolerancia_base=0.45)
        highs[-1] = 110.0
        incluyendo_senal = zonas_reales(highs[-100:], lows[-100:],
                                         minimo_toques=3, tolerancia_base=0.45)
        self.assertFalse(any(abs(z["precio"] - 110) < 0.45 for z in historico_sin_senal))
        self.assertTrue(any(abs(z["precio"] - 110) < 0.45 for z in incluyendo_senal))

    def test_fuerza_actual_no_asegura_contactos_temporales_independientes(self):
        # Repetir el mismo nivel en velas consecutivas cuenta como
        # fuerza elevada, sin separacion cronologica de rechazos.
        highs = [110.0, 110.0, 110.0]
        lows = [99.0, 99.0, 99.0]
        zonas = zonas_reales(highs, lows, minimo_toques=3, tolerancia_base=0.45)
        self.assertTrue(any(z["fuerza"] >= 3 for z in zonas))
        self.assertEqual(len(highs), 3)

    def test_detector_publico_no_usa_mas_de_100_velas(self):
        highs = [102.0] * 181
        lows = [99.0] * 181
        for i in (10, 20, 30):
            highs[i] = 110.0
        soporte, resistencia = soporte_resistencia_zonas(
            price=105.0, highs=highs, lows=lows, vol=1.0
        )
        self.assertNotAlmostEqual(resistencia["precio"], 110.0, places=1)


if __name__ == "__main__":
    unittest.main()
