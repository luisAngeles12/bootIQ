import unittest
from auditoria_hipotesis_fase32 import coincide_hipotesis, resumir_hipotesis_ventanas


class HipotesisFase32Tests(unittest.TestCase):
    def test_intervalos_exactos_y_fuentes_independientes(self):
        a = {"pa_fuerza":"0.25","rsi":"40","puntaje":"15"}
        b = {"pa_fuerza":"0.49","calidad_setup":"BUENA",
             "subtipo_setup":"SWEEP_RUPTURA_CONFIRMABLE"}
        self.assertTrue(coincide_hipotesis(a,"A"))
        self.assertTrue(coincide_hipotesis(b,"B"))
        self.assertFalse(coincide_hipotesis(dict(a,rsi="50"),"A"))
        self.assertFalse(coincide_hipotesis(dict(b,pa_fuerza="0.50"),"B"))

    def test_ventana_pequena_no_valida_aunque_winrate_alto(self):
        datos=[
            ("sep",[{"pa_fuerza":"0.3","rsi":"45","puntaje":"18",
                     "resultado_hipotetico":"WIN"} for _ in range(68)]),
            ("oct2",[{"pa_fuerza":"0.3","rsi":"45","puntaje":"18",
                      "resultado_hipotetico":"LOSS"} for _ in range(2)]),
        ]
        r=resumir_hipotesis_ventanas(datos)["A"]
        self.assertFalse(r["cobertura_suficiente"])
        self.assertFalse(r["evidencia_59_transferible"])
        self.assertFalse(r["autoriza_operacion"])

    def test_evidencia_excepcional_aun_no_activa_trading(self):
        filas=[{"pa_fuerza":".31","calidad_setup":"BUENA",
                "subtipo_setup":"SWEEP_RUPTURA_CONFIRMABLE",
                "resultado_hipotetico":"WIN"} for _ in range(50)]
        r=resumir_hipotesis_ventanas([("v1",filas),("v2",filas),("v3",filas)])["B"]
        self.assertTrue(r["evidencia_59_transferible"])
        self.assertFalse(r["autoriza_operacion"])

    def test_no_duplica_periodos(self):
        with self.assertRaises(ValueError):
            resumir_hipotesis_ventanas([("oct",[]),("oct",[])])

if __name__=="__main__":
    unittest.main()
