import unittest

from auditoria_calibracion_sombra import resumir_calibracion_sombra


class CalibracionSombraTests(unittest.TestCase):
    def test_probabilidad_y_resultado_hipotetico_no_se_confunden_con_real(self):
        filas = [
            {"decision_estadistica_sombra": "OPERAR_SOMBRA",
             "probabilidad_estimada": "60", "resultado_hipotetico": "WIN",
             "estado_operacion": "CANCELADA_CEREBRO", "resultado": "LOSS",
             "fecha_senal": "1791807060"},
            {"decision_estadistica_sombra": "OPERAR_SOMBRA",
             "probabilidad_estimada": "60", "resultado_hipotetico": "LOSS",
             "estado_operacion": "CANCELADA_CEREBRO", "resultado": "WIN",
             "fecha_senal": "1791807060"},
        ]
        resumen, descartadas = resumir_calibracion_sombra(filas)
        self.assertEqual(descartadas, 0)
        g = resumen[0]
        self.assertEqual(g["n"], 2)
        self.assertEqual(g["wins_hipoteticos"], 1)
        self.assertEqual(g["probabilidad_promedio"], 60.0)
        self.assertEqual(g["winrate_hipotetico"], 50.0)
        self.assertEqual(g["diferencia_pp"], -10.0)
        self.assertEqual(g["minutos_distintos"], 1)
        self.assertEqual(g["dias_distintos"], 1)

    def test_rechaza_probabilidad_no_numerica_fuera_de_rango_y_empates(self):
        filas = [
            {"probabilidad_estimada": "no", "resultado_hipotetico": "WIN"},
            {"probabilidad_estimada": "101", "resultado_hipotetico": "WIN"},
            {"probabilidad_estimada": "-2", "resultado_hipotetico": "LOSS"},
            {"probabilidad_estimada": "50", "resultado_hipotetico": "TIE"},
            {"probabilidad_estimada": "50", "resultado": "WIN",
             "resultado_hipotetico": ""},
        ]
        resumen, descartadas = resumir_calibracion_sombra(filas)
        self.assertEqual(descartadas, 5)
        self.assertEqual(resumen, [])

    def test_separa_decisiones_sombra_y_conserva_fechas_utc(self):
        filas = [
            {"decision_estadistica_sombra": "NO_OPERAR_SOMBRA",
             "probabilidad_estimada": "40", "resultado_hipotetico": "LOSS",
             "fecha": "2026-10-12T23:00:00-04:00"},
            {"decision_estadistica_sombra": "OPERAR_SOMBRA",
             "probabilidad_estimada": "60", "resultado_hipotetico": "WIN",
             "fecha": "2026-10-13T03:00:00Z"},
        ]
        resumen, descartadas = resumir_calibracion_sombra(filas)
        self.assertEqual(descartadas, 0)
        self.assertEqual(len(resumen), 2)
        self.assertEqual({g["decision_sombra"] for g in resumen},
                         {"NO_OPERAR_SOMBRA", "OPERAR_SOMBRA"})
        self.assertEqual(sum(g["dias_distintos"] for g in resumen), 2)


if __name__ == "__main__":
    unittest.main()
