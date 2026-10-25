import unittest
from auditoria_causas_cancelacion import clasificar_causa_cancelacion, resumir_causas_cancelacion


class CausasCancelacionTests(unittest.TestCase):
    def test_autoridad_generica_inhabilitada_con_sombra_favorable(self):
        f = {"estado_operacion": "CANCELADA_CEREBRO",
             "decision_estadistica_sombra": "OPERAR_SOMBRA",
             "fase4_motivo": "V3_SOMBRA_FAVORABLE_SIN_AUTORIDAD_GENERICA: favorable.",
             "resultado_hipotetico": "WIN", "cerebro_unico_riesgo": "EXTREMO"}
        self.assertEqual(clasificar_causa_cancelacion(f), "AUTORIDAD_GENERICA_DESHABILITADA")
        self.assertEqual(resumir_causas_cancelacion([f])["AUTORIDAD_GENERICA_DESHABILITADA"],
                         {"n": 1, "hipotetico_WIN": 1})

    def test_veto_expreso_sin_duplicar_y_sin_inventar_resultado(self):
        f = {"estado_operacion": "CANCELADA_CEREBRO",
             "fase4_motivo": "D7.9: veto | D7.1: veto | D7.9: repetido"}
        self.assertEqual(clasificar_causa_cancelacion(f), "VETO_EXPRESO_D7.1+D7.9")
        self.assertEqual(resumir_causas_cancelacion([f])["VETO_EXPRESO_D7.1+D7.9"],
                         {"n": 1, "sin_resultado_hipotetico": 1})

    def test_no_confunde_riesgo_ni_win_con_causa(self):
        f = {"estado_operacion": "CANCELADA_CEREBRO", "cerebro_unico_riesgo": "EXTREMO",
             "resultado_hipotetico": "LOSS"}
        self.assertEqual(clasificar_causa_cancelacion(f), "SIN_CAUSA_DEMOSTRADA")

    def test_no_usa_hipotetico_para_operadas(self):
        f = {"estado_operacion": "OPERADA_DIRECTA", "resultado": "WIN"}
        self.assertEqual(resumir_causas_cancelacion([f]), {"NO_CANCELADA": {"n": 1}})

    def test_estadistica_desfavorable_y_muestra_insuficiente(self):
        a = {"estado_operacion": "CANCELADA_CEREBRO",
             "decision_sombra_origen": "NO_OPERAR_SOMBRA"}
        b = {"estado_operacion": "CANCELADA_CEREBRO",
             "decision_sombra_origen": "NO_OPERAR_SOMBRA_MUESTRA_INSUFICIENTE"}
        self.assertEqual(clasificar_causa_cancelacion(a), "PROBABILIDAD_NO_AUTORIZADA")
        self.assertEqual(clasificar_causa_cancelacion(b), "MUESTRA_ESTADISTICA_INSUFICIENTE")


if __name__ == "__main__":
    unittest.main()
