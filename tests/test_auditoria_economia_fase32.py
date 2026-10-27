import unittest

from auditoria_economia_fase32 import evaluar_rentabilidad, punto_equilibrio


class EconomiaFase32Tests(unittest.TestCase):
    def test_break_even_depende_del_pago(self):
        self.assertAlmostEqual(punto_equilibrio(0.70), 58.8235, places=4)
        self.assertAlmostEqual(punto_equilibrio(0.80), 55.5556, places=4)
        with self.assertRaises(ValueError):
            punto_equilibrio(0)

    def test_canceladas_no_se_convierten_en_ganancias(self):
        filas = [{"estado_operacion": "CANCELADA_CEREBRO",
                  "resultado_hipotetico": "WIN", "resultado": "WIN",
                  "pnl_real_cerrado": "100"} for _ in range(100)]
        r = evaluar_rentabilidad(filas, payout_neto=.70)
        self.assertEqual(r["operaciones_cerradas"], 0)
        self.assertEqual(r["ignoradas"]["NO_EJECUTADA"], 100)
        self.assertIsNone(r["rentabilidad_observada_positiva"])
        self.assertFalse(r["autoriza_operacion"])

    def test_59_por_ciento_no_demuestra_pnl_sin_pagos(self):
        filas = [{"estado_operacion": "OPERADA_DIRECTA",
                  "resultado": "WIN" if i < 59 else "LOSS",
                  "activo": "EURUSD-OTC", "fecha_senal": "2026-10-26"} for i in range(100)]
        r = evaluar_rentabilidad(filas, payout_neto=.70)
        self.assertTrue(r["supera_59_observado"])
        self.assertTrue(r["supera_break_even_teorico"])
        self.assertIsNone(r["pnl_real_cerrado"])
        self.assertIsNone(r["rentabilidad_observada_positiva"])

    def test_positivo_con_pnl_completo_y_un_mercado_valido(self):
        filas = [{"estado_operacion": "OPERADA_DIRECTA",
                  "resultado": "WIN", "activo": "EURUSD-OTC",
                  "fecha_senal": "2026-10-26", "pnl_real_cerrado": "7"},
                 {"estado_operacion": "OPERADA_DIRECTA",
                  "resultado": "LOSS", "activo": "EURUSD-OTC",
                  "fecha_senal": "2026-10-26", "pnl_real_cerrado": "-5"}]
        r = evaluar_rentabilidad(filas)
        self.assertEqual(r["pnl_real_cerrado"], 2)
        self.assertTrue(r["rentabilidad_observada_positiva"])
        self.assertTrue(r["mercados_dentro_del_maximo"])
        self.assertEqual(r["mercados_distintos"], 1)
        self.assertFalse(r["autoriza_operacion"])

    def test_epoch_agrupa_operaciones_en_dias_utc(self):
        base = 1793059200
        filas = [
            {"estado_operacion": "OPERADA_DIRECTA", "resultado": "WIN",
             "fecha_senal": str(base + i*60), "pnl_real_cerrado": "2"}
            for i in (0, 1, 1440)
        ]
        r = evaluar_rentabilidad(filas)
        self.assertEqual(r["operaciones_cerradas"], 3)
        self.assertEqual(r["fechas_con_operaciones"], 2)
        self.assertEqual(r["pnl_real_cerrado"], 6.0)



if __name__ == "__main__":
    unittest.main()
