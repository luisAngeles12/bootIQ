import unittest
from auditoria_transferencia_estrategias_multiventana import evaluar_transferencia_estrategias


class TransferenciaEstrategiasTests(unittest.TestCase):
    def test_misma_configuracion_debe_superar_59_en_ambas_ventanas(self):
        def filas(wins, total, activo="A"):
            return [{"activo":activo,"patron":"CHOCH","direccion":"call",
                     "resultado_hipotetico":"WIN" if i<wins else "LOSS"} for i in range(total)]
        r=evaluar_transferencia_estrategias(filas(20,30),filas(16,30),minimo_por_periodo=20)
        self.assertEqual(r["mercados_comunes"],1)
        self.assertGreater(r["combinaciones_elegibles"],0)
        self.assertEqual(r["combinaciones_superan_59_ambos"],0)
        self.assertFalse(any(x["autoriza_trading"] for x in r["resultados"]))

    def test_comparacion_no_mezcla_activos_que_solo_estan_en_un_periodo(self):
        a=[{"activo":"A","patron":"X","resultado_hipotetico":"WIN"},
           {"activo":"B","patron":"X","resultado_hipotetico":"WIN"}]
        b=[{"activo":"A","patron":"X","resultado_hipotetico":"LOSS"},
           {"activo":"C","patron":"X","resultado_hipotetico":"WIN"}]
        r=evaluar_transferencia_estrategias(a,b,minimo_por_periodo=1)
        self.assertEqual(r["mercados_comunes"],1)
        self.assertEqual((r["senales_train_comunes"],r["senales_oos_comunes"]),(1,1))

    def test_sin_resultado_no_es_win_ni_loss(self):
        a=[{"activo":"A","patron":"X","resultado_hipotetico":"WIN"}]
        b=[{"activo":"A","patron":"X","resultado_hipotetico":"SIN_DATOS"}]
        r=evaluar_transferencia_estrategias(a,b,minimo_por_periodo=1)
        self.assertEqual(r["combinaciones_elegibles"],0)


if __name__=="__main__":
    unittest.main()
