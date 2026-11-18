import unittest

from evaluar_combinaciones_contexto_practice import analizar_contextos


def fila(i, dia, pnl, mercado="TENDENCIA_ALCISTA", estado="CERRADA", modo="PRACTICE"):
    return {
        "order_id": str(i), "fecha": f"2026-11-{dia:02d} 12:00:00",
        "estado": estado, "modo_cuenta_configurado": modo,
        "estado_operacion": "OPERADA_DIRECTA",
        "resultado": str(pnl), "patron": "CHOCH bajista",
        "tipo_mercado": mercado, "activo": "USDCLP-OTC",
        "direccion": "put", "direccion_tendencia": "BAJISTA",
    }


class TestContextos(unittest.TestCase):
    def test_solo_practice_cerradas_y_unicas(self):
        rows = [fila(1, 10, 20), fila(2, 10, 20, modo="REAL"),
                fila(3, 10, -25, estado="ABIERTA")]
        data = analizar_contextos(rows, 2, 2)
        self.assertEqual(data["operaciones_cerradas_validas"], 1)
        self.assertEqual(data["estado"], "SIN_VALIDACION_TEMPORAL")
        self.assertFalse(data["autoriza_operaciones"])

    def test_no_confunde_condicion_con_estrategia_entera(self):
        rows = [fila(i, day, 20 if i % 2 else -25)
                for day in range(10, 20) for i in range(day*100, day*100+10)]
        result = analizar_contextos(rows, 10, 10)
        self.assertEqual(result["estado"], "COMPARACION_TEMPORAL_NO_CAUSAL")
        self.assertIsNone(result["hipotesis"])

    def test_hipotesis_train_no_se_reelige_con_test(self):
        rows = []
        for day in range(10, 20):
            for k in range(20):
                a = k < 10
                # A gana en train; pierde en test. B a la inversa.
                gain = a if day <= 15 else not a
                rows.append(fila(day*100+k, day, 20 if gain else -25,
                                 mercado="A" if a else "B"))
        result = analizar_contextos(rows, 10, 10)
        self.assertEqual(result["hipotesis"]["variable"], "tipo_mercado")
        self.assertEqual(result["hipotesis"]["valor"], "A")
        self.assertEqual(result["hipotesis"]["test"]["neto"], -750)
        self.assertFalse(result["hipotesis"]["replica_mejora_oos"])
        self.assertFalse(result["modifica_cerebro"])

    def test_duplicados_conflictivos_no_cuentan(self):
        result = analizar_contextos([fila(1,10,20),fila(1,10,-25),fila(2,11,20)],2,2)
        self.assertEqual(result["operaciones_cerradas_validas"], 1)
        self.assertEqual(result["descartes"]["ORDER_ID_REPETIDO"], 1)


if __name__ == "__main__":
    unittest.main()
