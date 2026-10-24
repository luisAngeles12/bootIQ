import unittest

from auditoria_vetos_cerebro import auditar_vetos_temporales


class AuditoriaVetosTests(unittest.TestCase):
    def test_separa_dias_y_no_cuenta_operadas(self):
        base = {"estado_operacion": "CANCELADA_CEREBRO", "decision_estadistica_sombra": "OPERAR_SOMBRA",
                "cerebro_unico_motivos": "D7.9: veto", "resultado_hipotetico": "WIN"}
        filas = [
            {**base, "fecha": "1789473960"},
            {**base, "fecha": "1789560360", "resultado_hipotetico": "LOSS"},
            {**base, "fecha": "1789473960", "estado_operacion": "OPERADA_DIRECTA"},
        ]
        grupos, excluidos = auditar_vetos_temporales(filas, minimo=1)
        self.assertEqual((grupos[0]["n"], grupos[0]["wins"], grupos[0]["losses"]), (2, 1, 1))
        self.assertEqual(len(grupos[0]["dias"]), 2)
        self.assertEqual(excluidos["operada_no_hipotetica"], 1)

    def test_no_duplica_reglas_ni_inventa_resultados(self):
        base = {"estado_operacion": "CANCELADA_CEREBRO", "decision_estadistica_sombra": "OPERAR_CON_PROTOCOLO_SOMBRA",
                "fecha": "1789473960", "cerebro_unico_motivos": "D7.1: motivo | D7.1: mismo motivo | D7.9: segundo"}
        grupos, excluidos = auditar_vetos_temporales([
            {**base, "resultado_hipotetico": "WIN"},
            {**base, "resultado_hipotetico": "SIN_DATOS"},
        ], minimo=1)
        self.assertEqual((len(grupos), grupos[0]["regla"], grupos[0]["n"]), (1, "D7.1+D7.9", 1))
        self.assertEqual(excluidos["sin_resultado_hipotetico"], 1)


if __name__ == "__main__":
    unittest.main()
