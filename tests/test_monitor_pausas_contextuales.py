import unittest

from monitor_pausas_contextuales import evaluar_contextos_cerrados


class MonitorPausasTests(unittest.TestCase):
    def test_no_aplica_pausas_y_no_mezcla_contextos(self):
        base = {"estado": "CERRADA", "patron": "CHOCH", "direccion": "PUT", "tipo_mercado": "TENDENCIA_BAJISTA"}
        filas = [
            {**base, "fecha": 1, "resultado": -25},
            {**base, "fecha": 2, "resultado": -25},
            {**base, "fecha": 3, "resultado": 20},
            {**base, "fecha": 4, "tipo_mercado": "RANGO", "resultado": 20},
            {**base, "fecha": 5, "estado": "ABIERTA", "resultado": -500},
            {**base, "fecha": 6, "resultado": "NaN"},
        ]
        reporte, descartes = evaluar_contextos_cerrados(filas, ventana=3, muestra_minima=3)
        por_mercado = {r["mercado"]: r for r in reporte}
        self.assertEqual(por_mercado["TENDENCIA_BAJISTA"]["neto"], -30)
        self.assertEqual(por_mercado["TENDENCIA_BAJISTA"]["estado_observacion"], "REVISAR_PERDIDAS_CONTEXTUALES")
        self.assertEqual(por_mercado["RANGO"]["estado_observacion"], "MUESTRA_INSUFICIENTE")
        self.assertTrue(all(not r["pausa_aplicada"] for r in reporte))
        self.assertEqual(descartes, {"no_cerrada": 1, "resultado_invalido": 1})

    def test_restringe_la_ventana_y_no_usa_hipoteticos(self):
        base = {"estado": "CERRADA", "patron": "REACCION", "direccion": "CALL", "tipo_mercado": "RANGO"}
        filas = [
            {**base, "fecha": 1, "resultado": -25},
            {**base, "fecha": 2, "resultado": 20},
            {**base, "fecha": 3, "resultado": 20, "resultado_hipotetico": "LOSS"},
        ]
        reporte, _ = evaluar_contextos_cerrados(filas, ventana=2, muestra_minima=2)
        self.assertEqual((reporte[0]["muestra"], reporte[0]["neto"]), (2, 40))
        self.assertEqual(reporte[0]["estado_observacion"], "SIN_PERDIDA_NETA_EN_VENTANA")

    def test_acepta_fechas_textuales_del_historial_live(self):
        base = {"estado": "CERRADA", "patron": "CHOCH", "direccion": "CALL", "tipo_mercado": "TENDENCIA_ALCISTA"}
        reporte, descartes = evaluar_contextos_cerrados([
            {**base, "fecha": "2026-09-15 15:55:06", "resultado": -25},
            {**base, "fecha": "2026-09-15 15:56:06", "resultado": 20},
        ], ventana=2, muestra_minima=2)
        self.assertEqual((reporte[0]["muestra"], reporte[0]["neto"]), (2, -5))
        self.assertEqual(descartes, {})


if __name__ == "__main__":
    unittest.main()
