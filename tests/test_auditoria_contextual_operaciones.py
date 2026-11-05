import unittest

from auditoria_contextual_operaciones import agrupar_senales_por_contexto


class AuditoriaContextualTests(unittest.TestCase):
    def test_separa_entradas_de_canceladas_y_protocolos_no_confirmados(self):
        comunes = {
            "patron": "reacción compradora en soporte",
            "direccion": "call",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
        }
        filas = [
            {**comunes, "cerebro_unico_decision": "NO_OPERAR",
             "motivo_ejecucion": "CANCELADA_CEREBRO_UNICO_NO_OPERAR",
             "resultado_hipotetico": "WIN"},
            {**comunes, "cerebro_unico_decision": "OPERAR",
             "motivo_ejecucion": "OPERACION_DIRECTA_CEREBRO_UNICO",
             "resultado_hipotetico": "LOSS"},
            {**comunes, "cerebro_unico_decision": "OPERAR_CON_PROTOCOLO",
             "motivo_ejecucion": "SOMBRA_RUPTURA_RESISTENCIA_NO_CONFIRMADA",
             "resultado_hipotetico": "WIN"},
        ]
        grupos = agrupar_senales_por_contexto(filas)
        self.assertEqual(len(grupos), 3)
        por_clase = {fila["clase"]: fila for fila in grupos}
        self.assertEqual(por_clase["CANCELADA_HIPOTETICA"]["wins"], 1)
        self.assertEqual(por_clase["DIRECTA_SIMULADA"]["losses"], 1)
        self.assertEqual(
            por_clase["OTRA_SENAL_EVALUADA"]["wins"], 1,
        )

    def test_no_cuenta_empates_ni_registros_sin_resultado(self):
        filas = [
            {"resultado_hipotetico": "TIE", "patron": "CHOCH"},
            {"resultado_hipotetico": "", "patron": "CHOCH"},
        ]
        self.assertEqual(agrupar_senales_por_contexto(filas), [])


if __name__ == "__main__":
    unittest.main()
