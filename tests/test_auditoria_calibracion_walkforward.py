import unittest

from auditoria_calibracion_walkforward import comparar_calibracion_walkforward


class WalkForwardTests(unittest.TestCase):
    def test_usa_solo_dias_anteriores_y_mide_empeoramiento(self):
        datos = [
            {"fecha_senal": "0", "clave_probabilidad_principal": "A",
             "probabilidad_estimada": "60", "resultado_hipotetico": "WIN",
             "decision_estadistica_sombra": "OPERAR_SOMBRA"},
            {"fecha_senal": "86400", "clave_probabilidad_principal": "A",
             "probabilidad_estimada": "60", "resultado_hipotetico": "LOSS",
             "decision_estadistica_sombra": "OPERAR_SOMBRA"},
        ]
        salida, descartadas = comparar_calibracion_walkforward(
            datos, horizontes=(3,), fuerzas=(1,)
        )
        self.assertEqual(descartadas, 0)
        self.assertEqual(len(salida), 2)
        self.assertEqual(salida[0]["con_historia"], 0)
        self.assertEqual(salida[0]["brier_actual"], salida[0]["brier_candidato"])
        self.assertEqual(salida[1]["con_historia"], 1)
        self.assertEqual(salida[1]["brier_actual"], 0.36)
        self.assertEqual(salida[1]["brier_candidato"], 0.64)
        self.assertLess(salida[1]["mejora_brier"], 0)

    def test_no_incluye_dia_actual_como_fuente_de_aprendizaje(self):
        datos = [
            {"fecha_senal": "60", "clave_probabilidad_principal": "A",
             "probabilidad_estimada": "50", "resultado_hipotetico": "WIN"},
            {"fecha_senal": "120", "clave_probabilidad_principal": "A",
             "probabilidad_estimada": "50", "resultado_hipotetico": "LOSS"},
        ]
        salida, _ = comparar_calibracion_walkforward(
            datos, horizontes=(60,), fuerzas=(1,)
        )
        self.assertEqual(len(salida), 1)
        self.assertEqual(salida[0]["con_historia"], 0)
        self.assertEqual(salida[0]["brier_actual"], salida[0]["brier_candidato"])

    def test_no_usa_resultado_real_para_rellenar_hipoteticos(self):
        salida, descartadas = comparar_calibracion_walkforward([
            {"fecha_senal": "0", "clave_probabilidad_principal": "A",
             "probabilidad_estimada": "60", "resultado": "WIN"},
        ])
        self.assertEqual(descartadas, 1)
        self.assertEqual(salida, [])

    def test_el_filtro_sombra_no_altera_la_decision(self):
        datos = [
            {"fecha_senal": "0", "clave_probabilidad_principal": "A",
             "probabilidad_estimada": "50", "resultado_hipotetico": "WIN",
             "decision_estadistica_sombra": "NO_OPERAR_SOMBRA"},
            {"fecha_senal": "86400", "clave_probabilidad_principal": "A",
             "probabilidad_estimada": "50", "resultado_hipotetico": "LOSS",
             "decision_estadistica_sombra": "OPERAR_SOMBRA"},
        ]
        salida, _ = comparar_calibracion_walkforward(
            datos, horizontes=(3,), fuerzas=(1,), solo_operar=True
        )
        self.assertEqual(len(salida), 1)
        self.assertEqual(salida[0]["n"], 1)
        self.assertEqual(salida[0]["con_historia"], 1)


if __name__ == "__main__":
    unittest.main()
