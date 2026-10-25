import unittest
from auditoria_factores_cerebro import analizar_factores_cancelados


class FactoresCerebroTests(unittest.TestCase):
    def test_un_dia_no_justifica_candidato_aunque_tenga_muchas_senales(self):
        filas = [{"estado_operacion": "CANCELADA_CEREBRO", "resultado_hipotetico": "WIN",
                  "patron": "CHOCH alcista", "activo": "A" + str(i % 10),
                  "fecha_senal": str(1789473960 + 60*i)} for i in range(40)]
        grupos, excluidos = analizar_factores_cancelados(filas, minimo=1)
        p = next(g for g in grupos if g["factor"] == "patron")
        self.assertEqual(p["n"], 40)
        self.assertEqual(p["wr_hipotetico"], 100)
        self.assertFalse(p["cobertura_temporal_suficiente"])
        self.assertFalse(p["candidato_productivo"])
        self.assertEqual(excluidos["no_cancelada"], 0)

    def test_excluye_operadas_y_resultados_faltantes(self):
        base = {"patron": "X", "fecha_senal": "1789473960", "activo": "A"}
        filas = [dict(base, estado_operacion="OPERADA_DIRECTA", resultado_hipotetico="WIN"),
                 dict(base, estado_operacion="CANCELADA_CEREBRO", resultado_hipotetico=""),
                 dict(base, estado_operacion="CANCELADA_CEREBRO", resultado_hipotetico="LOSS")]
        grupos, excluidos = analizar_factores_cancelados(filas, minimo=1)
        p = next(g for g in grupos if g["factor"] == "patron")
        self.assertEqual((p["n"], p["wins_hipoteticos"]), (1, 0))
        self.assertEqual(excluidos, {"no_cancelada": 1, "sin_resultado_hipotetico": 1})

    def test_datos_sin_fecha_no_obtienen_cobertura_temporal(self):
        filas = [{"estado_operacion": "CANCELADA_CEREBRO", "resultado_hipotetico": "WIN",
                  "patron": "X", "activo": str(i), "fecha": "INVALIDO"} for i in range(45)]
        grupos, _ = analizar_factores_cancelados(filas, minimo=1)
        p = next(g for g in grupos if g["factor"] == "patron")
        self.assertEqual((p["dias"], p["minutos"]), (0, 0))
        self.assertFalse(p["cobertura_temporal_suficiente"])

if __name__ == "__main__":
    unittest.main()
