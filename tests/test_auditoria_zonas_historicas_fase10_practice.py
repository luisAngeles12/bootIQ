"""F10: pruebas de causalidad de niveles anteriores; sin broker."""
import unittest
from zonas import (
    _zonas_historicas_independientes,
    soporte_resistencia_zonas,
    validar_interaccion_soporte_resistencia,
)


class AuditoriaZonasHistoricas(unittest.TestCase):
    def _datos(self):
        highs = [102.0] * 181
        lows = [99.0] * 181
        return highs, lows

    def test_resistencia_anterior_a_las_100_velas_se_recupera(self):
        highs, lows = self._datos()
        for i in (10, 20, 30):
            highs[i] = 110.0
        _, resistencia = soporte_resistencia_zonas(
            price=105.0, highs=highs, lows=lows, vol=1.0
        )
        self.assertAlmostEqual(resistencia["precio"], 110.0)
        self.assertEqual(resistencia["fuerza"], 3)
        self.assertEqual(resistencia["origen"], "EXTREMOS_HISTORICOS_PREVIOS")

    def test_ultima_vela_no_fabrica_tercer_contacto(self):
        highs, lows = self._datos()
        highs[150] = 110.0
        highs[160] = 110.0
        _, anterior = soporte_resistencia_zonas(105.0, highs, lows, 1.0)
        highs[-1] = 110.0
        _, actual = soporte_resistencia_zonas(105.0, highs, lows, 1.0)
        self.assertEqual(actual["precio"], anterior["precio"])
        self.assertEqual(actual["fuerza"], anterior["fuerza"])
        self.assertEqual(actual["fuerza"], 1)

    def test_tres_velas_consecutivas_no_son_tres_rechazos(self):
        niveles = [102.0] * 20
        for i in (6, 7, 8):
            niveles[i] = 110.0
        zonas = _zonas_historicas_independientes(
            niveles, tolerancia=0.45, minimo_toques=3
        )
        self.assertFalse(any(abs(z["precio"] - 110) < 0.45 for z in zonas))

    def test_contactos_separados_si_cuentan(self):
        niveles = [102.0] * 20
        for i in (3, 8, 14):
            niveles[i] = 110.0
        zonas = _zonas_historicas_independientes(
            niveles, tolerancia=0.45, minimo_toques=3
        )
        self.assertTrue(any(abs(z["precio"] - 110) < 0.45
                            and z["fuerza"] == 3 for z in zonas))

    def test_puntaje_alto_no_supera_resistencia_fuerte_sin_ruptura(self):
        ok, causa = validar_interaccion_soporte_resistencia(
            "call", [100]*6, [104]*6, [105]*6, [99]*6,
            99, 105, 1, 25, "continuacion", "TENDENCIA_ALCISTA",
            "LIMPIO", False, "SIN_DATOS",
            cerca_resistencia=True, resistencia_fuerte=True,
        )
        self.assertFalse(ok)
        self.assertIn("historica fuerte", causa)

    def test_nombre_retest_no_equivale_a_ruptura_confirmada(self):
        ok, _ = validar_interaccion_soporte_resistencia(
            "put", [100]*6, [100]*6, [105]*6, [99]*6,
            99, 105, 1, 25, "breakout retest", "TENDENCIA_BAJISTA",
            "LIMPIO", False, "SIN_DATOS",
            cerca_soporte=True, soporte_fuerte=True,
        )
        self.assertFalse(ok)

    def test_ruptura_confirmada_no_se_bloquea_por_ser_zona_fuerte(self):
        ok, _ = validar_interaccion_soporte_resistencia(
            "call", [100]*6, [106]*6, [107]*6, [99]*6,
            99, 105, 1, 25, "breakout", "TENDENCIA_ALCISTA",
            "LIMPIO", True, "RUPTURA_RESISTENCIA_CONFIRMADA",
            cerca_resistencia=True, resistencia_fuerte=True,
        )
        self.assertTrue(ok)

    def test_datos_incompletos_no_permiten_inventar_zonas(self):
        with self.assertRaisesRegex(ValueError, "HISTORICO_ZONAS_INSUFICIENTE"):
            soporte_resistencia_zonas(105.0, [], [], 1.0)
        with self.assertRaisesRegex(ValueError, "HISTORICO_ZONAS_INSUFICIENTE"):
            soporte_resistencia_zonas(105.0, [102, 103], [99], 1.0)


if __name__ == "__main__":
    unittest.main()
