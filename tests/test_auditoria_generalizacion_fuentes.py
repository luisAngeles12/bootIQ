import unittest

from auditoria_generalizacion_fuentes import resumir_generalizacion_fuentes


class GeneralizacionFuentesTests(unittest.TestCase):
    def test_fuente_historica_y_oos_se_miden_por_separado(self):
        filas = [
            {"clave_probabilidad_principal": "CONTEXTO_SETUP|A",
             "fuente_probabilidad_principal": "{'total': 23, 'winrate': 65.22}",
             "probabilidad_estimada": "57.79", "resultado_hipotetico": "LOSS",
             "estado_operacion": "CANCELADA_CEREBRO", "resultado": "WIN",
             "activo": "AAA", "fecha_senal": "1791807060"},
            {"clave_probabilidad_principal": "CONTEXTO_SETUP|A",
             "fuente_probabilidad_principal": "{'total': 23, 'winrate': 65.22}",
             "probabilidad_estimada": "57.79", "resultado_hipotetico": "WIN",
             "estado_operacion": "CANCELADA_CEREBRO", "resultado": "LOSS",
             "activo": "BBB", "fecha_senal": "1791807060"},
        ]
        grupos, descartadas = resumir_generalizacion_fuentes(filas)
        self.assertEqual(descartadas, 0)
        self.assertEqual(len(grupos), 1)
        g = grupos[0]
        self.assertEqual(g["n"], 2)
        self.assertEqual(g["muestra_memoria"], 23)
        self.assertEqual(g["winrate_memoria"], 65.22)
        self.assertEqual(g["wins_hipoteticos"], 1)
        self.assertEqual(g["winrate_hipotetico"], 50.0)
        self.assertEqual(g["brecha_pp"], -7.79)
        self.assertEqual(g["activos_distintos"], 2)
        self.assertEqual(g["minutos_distintos"], 1)

    def test_malformado_no_ejecuta_codigo_ni_inventa_muestra(self):
        grupos, _ = resumir_generalizacion_fuentes([{
            "clave_probabilidad_principal": "A",
            "fuente_probabilidad_principal": "__import__('os').system('echo unsafe')",
            "probabilidad_estimada": "50",
            "resultado_hipotetico": "WIN",
        }])
        self.assertIsNone(grupos[0]["muestra_memoria"])
        self.assertIsNone(grupos[0]["winrate_memoria"])

    def test_no_reutiliza_resultado_ejecutado_como_hipotetico(self):
        grupos, descartadas = resumir_generalizacion_fuentes([
            {"clave_probabilidad_principal": "A",
             "probabilidad_estimada": "60", "resultado": "WIN"},
            {"clave_probabilidad_principal": "A",
             "probabilidad_estimada": "60", "resultado_hipotetico": "TIE"},
            {"clave_probabilidad_principal": "",
             "probabilidad_estimada": "60", "resultado_hipotetico": "WIN"},
        ])
        self.assertEqual(grupos, [])
        self.assertEqual(descartadas, 3)


    def test_descompone_error_sin_cambiar_probabilidades(self):
        filas = [
            {"clave_probabilidad_principal": "A",
             "fuente_probabilidad_principal": "{'total': 23, 'winrate': 65.22, 'probabilidad_ajustada': 60}",
             "fuente_probabilidad_respaldo": "{'probabilidad_ajustada': 55}",
             "probabilidad_estimada": "58", "resultado_hipotetico": "WIN"},
            {"clave_probabilidad_principal": "A",
             "fuente_probabilidad_principal": "{'total': 23, 'winrate': 65.22, 'probabilidad_ajustada': 60}",
             "fuente_probabilidad_respaldo": "{'probabilidad_ajustada': 55}",
             "probabilidad_estimada": "58", "resultado_hipotetico": "LOSS"},
        ]
        grupos, descartadas = resumir_generalizacion_fuentes(filas)
        self.assertEqual(descartadas, 0)
        g = grupos[0]
        self.assertEqual(g["pred_promedio"], 58.0)
        self.assertEqual(g["n_principal"], 2)
        self.assertEqual(g["n_respaldo"], 2)
        self.assertAlmostEqual(g["brier_modelo"], 0.2564)
        self.assertAlmostEqual(g["brier_principal"], 0.26)
        self.assertAlmostEqual(g["brier_respaldo"], 0.2525)
        self.assertLess(g["brier_prior"], g["brier_modelo"])



if __name__ == "__main__":
    unittest.main()
