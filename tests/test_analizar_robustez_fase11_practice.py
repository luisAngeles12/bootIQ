import unittest
from analizar_robustez_fase11_practice import analizar, wilson_95


def datos(n=20, wins=12):
    return [{"tipo_cuenta": "PRACTICE", "resultado": "WIN" if i < wins else "LOSS",
             "fecha_cierre": "2026-11-18T23:00:00+00:00"} for i in range(n)]


class RobustezTest(unittest.TestCase):
    def test_intervalo_12_de_20_no_demuestra_tasa_verdadera_60(self):
        r = analizar(datos())
        self.assertEqual(r["winrate_pct"], 60.0)
        self.assertLess(r["intervalo_wilson_95_pct"][0], 60)
        self.assertFalse(r["limite_inferior_supera_60"])
        self.assertEqual(r["dias_utc_distintos"], 1)

    def test_todos_wins_y_cero_muestra(self):
        self.assertEqual(wilson_95(0, 0), None)
        self.assertEqual(wilson_95(20, 20)[1], 100.0)
        self.assertFalse(analizar([])["limite_inferior_supera_60"])

    def test_agrupacion_dias_utc_no_fecha_local(self):
        a = datos(2, 1)
        a[1]["fecha_cierre"] = "2026-11-18T20:30:00-04:00"
        r = analizar(a)
        self.assertEqual(r["dias_utc_distintos"], 2)
        self.assertEqual(r["operaciones_por_dia_utc"]["2026-11-19"], 1)

    def test_rechaza_real_y_resultados_sin_cerrar(self):
        a = datos()
        a[0]["tipo_cuenta"] = "REAL"
        with self.assertRaisesRegex(ValueError, "SOLO_PRACTICE"):
            analizar(a)
        a[0]["tipo_cuenta"] = "PRACTICE"
        a[0]["resultado"] = "PENDIENTE"
        with self.assertRaisesRegex(ValueError, "RESULTADO_NO_CERRADO"):
            analizar(a)

    def test_no_acepta_hora_sin_zona(self):
        a = datos()
        a[0]["fecha_cierre"] = "2026-11-18T23:00:00"
        with self.assertRaisesRegex(ValueError, "FECHA_CIERRE_INVALIDA"):
            analizar(a)

    def test_wilson_invalido(self):
        for w, n in [(-1, 20), (21, 20), (0, -1)]:
            with self.assertRaisesRegex(ValueError, "CONTEOS_INVALIDOS"):
                wilson_95(w, n)

if __name__ == "__main__":
    unittest.main()
