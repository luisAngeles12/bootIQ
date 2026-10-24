import unittest

from auditoria_contextual_operaciones import (
    agrupar_senales_por_contexto,
    agrupar_factores_estrategia,
)


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

    def test_analiza_rsi_y_accion_precio_sin_mezclar_clases(self):
        comunes = {
            "patron": "reacción compradora en soporte",
            "direccion": "call",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "calidad_mercado": "NORMAL",
            "estado_tendencia": "ALCISTA_DEBIL",
            "accion_precio": "RECHAZO_COMPRADOR_CONFIRMADO",
            "rsi": "48.7",
        }
        filas = [
            {**comunes, "cerebro_unico_decision": "NO_OPERAR", "resultado_hipotetico": "WIN"},
            {**comunes, "cerebro_unico_decision": "NO_OPERAR", "resultado_hipotetico": "LOSS"},
            {**comunes, "cerebro_unico_decision": "OPERAR", "motivo_ejecucion": "OPERACION_DIRECTA_CEREBRO_UNICO", "resultado_hipotetico": "LOSS"},
        ]
        grupos = agrupar_factores_estrategia(filas, minimo=1)
        rsi_cancelado = [g for g in grupos if g["dimension"] == "RSI" and g["clase"] == "CANCELADA_HIPOTETICA"]
        self.assertEqual(len(rsi_cancelado), 1)
        self.assertEqual(rsi_cancelado[0]["valor"], "RSI_45_55")
        self.assertEqual((rsi_cancelado[0]["total"], rsi_cancelado[0]["wins"]), (2, 1))
        self.assertEqual(rsi_cancelado[0]["wr_hipotetico"], 50.0)
        self.assertLess(rsi_cancelado[0]["limite_inferior_wilson"], 50.0)
        directas = [g for g in grupos if g["dimension"] == "ACCION_PRECIO" and g["clase"] == "DIRECTA_SIMULADA"]
        self.assertEqual((len(directas), directas[0]["losses"]), (1, 1))

    def test_excluye_rsi_invalido_y_muestras_pequenas(self):
        filas = [{"patron": "CHOCH", "rsi": "desconocido", "resultado_hipotetico": "WIN"}]
        self.assertEqual(agrupar_factores_estrategia(filas, minimo=2), [])
        grupos = agrupar_factores_estrategia(filas, minimo=1)
        self.assertIn("RSI_SIN_DATOS", [g["valor"] for g in grupos])


if __name__ == "__main__":
    unittest.main()
