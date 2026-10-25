import unittest
from auditoria_calidad_frecuencia_cerebro import resumir_frecuencia_cerebro


class CalidadFrecuenciaCerebroTests(unittest.TestCase):
    def test_no_convierte_59_por_senal_en_bloqueo(self):
        rows = [
            {"fecha_senal": "1789473960", "activo": "A", "estado_operacion": "OPERADA_DIRECTA",
             "probabilidad_estimada": "55", "resultado": "WIN"},
            {"fecha_senal": "1789473960", "activo": "B", "estado_operacion": "CANCELADA_CEREBRO",
             "probabilidad_estimada": "59", "resultado_hipotetico": "LOSS"},
            {"fecha_senal": "1789474020", "activo": "A", "estado_operacion": "CANCELADA_PROTOCOLO",
             "probabilidad_estimada": ""},
        ]
        g = next(iter(resumir_frecuencia_cerebro(rows).values()))
        self.assertEqual(g["senales"], 3)
        self.assertEqual(g["operadas_backtest"], 1)
        self.assertEqual(g["predicciones_ge59"], 1)
        self.assertEqual(g["minutos_con_senal"], 2)
        self.assertEqual(g["operadas_por_100_senales"], 33.33)
        self.assertTrue(g["payout_y_pnl_no_evaluables"])

    def test_fechas_independientes_y_probabilidad_invalida(self):
        rows = [{"fecha_senal": "1789473960", "estado_operacion": "OPERADA_DIRECTA",
                 "probabilidad_estimada": "101"},
                {"fecha_senal": "1789560360", "estado_operacion": "CANCELADA_CEREBRO",
                 "probabilidad_estimada": "sin dato"}]
        g = resumir_frecuencia_cerebro(rows)
        self.assertEqual(len(g), 2)
        self.assertEqual(sum(x["predicciones_con_dato"] for x in g.values()), 0)
        self.assertEqual(sum(x["operadas_backtest"] for x in g.values()), 1)

    def test_no_inventa_ganancias_contra_factuales(self):
        rows = [{"estado_operacion": "CANCELADA_CEREBRO", "resultado_hipotetico": "WIN"}]
        g = resumir_frecuencia_cerebro(rows)["SIN_FECHA"]
        self.assertEqual(g["operadas_backtest"], 0)
        self.assertIsNone(g["operadas_por_100_minutos_con_senal"])
        self.assertTrue(g["payout_y_pnl_no_evaluables"])


if __name__ == "__main__":
    unittest.main()
