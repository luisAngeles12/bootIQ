import unittest
from auditoria_rutas_core4_frecuencia import auditar_rutas_core4


class RutasCore4FrecuenciaTests(unittest.TestCase):
    def test_winrate_alto_con_poca_muestra_no_autoriza(self):
        f={"core4_match_previo":"True","core4_reglas_previas":"R1","estado_operacion":"OPERADA_DIRECTA",
           "resultado_hipotetico":"WIN","fecha_senal":"1789473960","activo":"A"}
        r, fuera=auditar_rutas_core4([f]*16)
        self.assertEqual(fuera,0)
        x=r[("R1","SIN_VETO")]
        self.assertEqual(x["winrate_operadas_backtest"],100)
        self.assertFalse(x["cumple_objetivo_y_cobertura"])
        self.assertFalse(x["autoriza_modificar_veto"])

    def test_rechazos_no_son_operaciones_ejecutadas(self):
        filas=[
            {"core4_match_previo":True,"core4_reglas_previas":"R2",
             "core4_invalidacion_selectiva_previa":True,
             "estado_operacion":"CANCELADA_CEREBRO","resultado_hipotetico":"WIN"},
            {"core4_match_previo":True,"core4_reglas_previas":"R2",
             "core4_invalidacion_selectiva_previa":True,
             "estado_operacion":"CANCELADA_CEREBRO","resultado_hipotetico":"LOSS"},
            {"core4_match_previo":False,"estado_operacion":"CANCELADA_CEREBRO"}
        ]
        r,fuera=auditar_rutas_core4(filas)
        self.assertEqual(fuera,1)
        x=r[("R2","VETO")]
        self.assertEqual(x["operadas"],0)
        self.assertEqual(x["win_hipoteticas_veto"],1)
        self.assertEqual(x["loss_hipoteticas_veto"],1)
        self.assertIsNone(x["winrate_operadas_backtest"])

    def test_cancelacion_protocolo_no_equivale_a_trade(self):
        f={"core4_match_previo":True,"core4_reglas_previas":"R1",
           "estado_operacion":"CANCELADA_PROTOCOLO","resultado_hipotetico":"WIN"}
        r,_=auditar_rutas_core4([f])
        x=r[("R1","SIN_VETO")]
        self.assertEqual(x["canceladas_protocolo"],1)
        self.assertEqual(x["operadas"],0)


if __name__=="__main__":
    unittest.main()
