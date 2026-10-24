import unittest

from auditoria_contextual_operaciones import (
    agrupar_senales_por_contexto,
    agrupar_factores_estrategia,
    auditar_integridad_contextual,
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
             "estado_operacion": "OPERADA_DIRECTA", "resultado": "LOSS",
             "resultado_hipotetico": "WIN"},
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
            {**comunes, "cerebro_unico_decision": "OPERAR", "motivo_ejecucion": "OPERACION_DIRECTA_CEREBRO_UNICO", "estado_operacion": "OPERADA_DIRECTA", "resultado": "LOSS", "resultado_hipotetico": "WIN"},
        ]
        grupos = agrupar_factores_estrategia(filas, minimo=1)
        rsi_cancelado = [g for g in grupos if g["dimension"] == "RSI" and g["clase"] == "CANCELADA_HIPOTETICA"]
        self.assertEqual(len(rsi_cancelado), 1)
        self.assertEqual(rsi_cancelado[0]["valor"], "RSI_45_55")
        self.assertEqual((rsi_cancelado[0]["total"], rsi_cancelado[0]["wins"]), (2, 1))
        self.assertEqual(rsi_cancelado[0]["wr_contextual"], 50.0)
        self.assertLess(rsi_cancelado[0]["limite_inferior_wilson"], 50.0)
        directas = [g for g in grupos if g["dimension"] == "ACCION_PRECIO" and g["clase"] == "DIRECTA_SIMULADA"]
        self.assertEqual((len(directas), directas[0]["losses"]), (1, 1))

    def test_excluye_rsi_invalido_y_muestras_pequenas(self):
        filas = [{"patron": "CHOCH", "rsi": "desconocido", "resultado_hipotetico": "WIN"}]
        self.assertEqual(agrupar_factores_estrategia(filas, minimo=2), [])
        grupos = agrupar_factores_estrategia(filas, minimo=1)
        self.assertIn("RSI_SIN_DATOS", [g["valor"] for g in grupos])

    def test_protocolo_ejecutado_usa_resultado_de_su_entrada(self):
        comunes = {
            "patron": "breakout retest alcista", "direccion": "call",
            "tipo_mercado": "TENDENCIA_ALCISTA", "estado_tendencia": "ALCISTA_NORMAL",
        }
        filas = [
            {**comunes, "estado_operacion": "OPERADA_PROTOCOLO", "resultado": "LOSS", "resultado_hipotetico": "WIN"},
            {**comunes, "estado_operacion": "CANCELADA_PROTOCOLO", "resultado": "LOSS", "resultado_hipotetico": "WIN"},
        ]
        grupos = {x["clase"]: x for x in agrupar_senales_por_contexto(filas)}
        self.assertEqual(grupos["PROTOCOLO_SIMULADO"]["losses"], 1)
        self.assertEqual(grupos["PROTOCOLO_SIMULADO"]["fuente_resultado"], "resultado")
        self.assertEqual(grupos["CANCELADA_HIPOTETICA"]["wins"], 1)
        self.assertEqual(grupos["CANCELADA_HIPOTETICA"]["fuente_resultado"], "resultado_hipotetico")

    def test_no_sustituye_resultado_ausente_por_hipotetico(self):
        filas = [{"estado_operacion": "OPERADA_PROTOCOLO", "resultado": "", "resultado_hipotetico": "WIN"}]
        self.assertEqual(agrupar_senales_por_contexto(filas), [])

    def test_integridad_informa_perdidas_de_cobertura_sin_imputar(self):
        filas = [
            {"estado_operacion": "OPERADA_PROTOCOLO", "resultado": "", "resultado_hipotetico": "WIN"},
            {"estado_operacion": "CANCELADA_CEREBRO", "resultado_hipotetico": "LOSS", "patron": "CHOCH", "tipo_mercado": "RANGO"},
            {"estado_operacion": "OPERADA_DIRECTA", "resultado": "WIN", "patron": "CHOCH", "tipo_mercado": "RANGO", "estado_tendencia": "ALCISTA_NORMAL", "accion_precio": "RECHAZO"},
        ]
        resultado = auditar_integridad_contextual(filas)
        self.assertEqual((resultado["total"], resultado["con_resultado_valido"], resultado["sin_resultado_valido"]), (3, 2, 1))
        self.assertEqual((resultado["sin_mercado"], resultado["sin_tendencia"], resultado["sin_accion_precio"]), (0, 1, 1))
        self.assertEqual(resultado["por_clase"]["PROTOCOLO_SIMULADO"], 1)


if __name__ == "__main__":
    unittest.main()
