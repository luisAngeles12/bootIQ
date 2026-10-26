import unittest
from auditoria_generalizacion_fase32 import evaluar_generalizacion


class GeneralizacionFase32Tests(unittest.TestCase):
    def test_rechaza_universo_externo_bajo_59(self):
        base = {"pa_fuerza": ".35", "rsi":"45", "puntaje":"17",
                "fecha_senal":"1791800940", "activo":"EURUSD-OTC"}
        filas=[dict(base,resultado_hipotetico="WIN" if i<55 else "LOSS")
               for i in range(100)]
        r=evaluar_generalizacion(filas)["A"]
        self.assertEqual(r["n_senales"],100)
        self.assertEqual(r["winrate_hipotetico"],55)
        self.assertFalse(r["supera_meta_59"])
        self.assertFalse(r["apto_para_promocion"])

    def test_20_es_maximo_no_minimo(self):
        base={"pa_fuerza":".35","calidad_setup":"BUENA",
              "subtipo_setup":"SWEEP_RUPTURA_CONFIRMABLE",
              "resultado_hipotetico":"WIN", "fecha_senal":"1791800940"}
        r=evaluar_generalizacion([dict(base,activo="AUDUSD-OTC")])["B"]
        self.assertEqual(r["mercados_distintos_en_replay"],1)
        self.assertFalse(r["apto_para_promocion"])

    def test_canceladas_nunca_autorizan(self):
        r=evaluar_generalizacion([{"pa_fuerza":".35","rsi":"45","puntaje":"17",
                                    "estado_operacion":"CANCELADA_CEREBRO",
                                    "resultado_hipotetico":"WIN"}])["A"]
        self.assertFalse(r["apto_para_promocion"])


if __name__=="__main__":
    unittest.main()
