"""Regresiones del analizador de resultados hipoteticos en sombra."""
import unittest
from evaluar_sombra_prospectiva_practice import evaluar


def fila(i, resultado="WIN", calidad="HIPOTETICO_VELA_COMPLETA_SIN_FILL"):
    return {"id": str(i), "decision": "NO_OPERAR",
            "resultado_hipotetico": resultado, "calidad_tiempo": calidad,
            "vela_entrada_from": str(1700000000 + 60 * i),
            "direccion": "call" if i % 2 else "put"}


class EvaluacionSombraTests(unittest.TestCase):
    def test_12_de_20_es_60_pero_no_autoriza(self):
        r = evaluar([fila(i, "WIN" if i < 12 else "LOSS") for i in range(20)])
        self.assertEqual(r["global"]["winrate_pct"], 60.0)
        self.assertTrue(r["todos_bloques_20_cumplen_60"])
        self.assertFalse(r["autoriza_operaciones"])
        self.assertFalse(r["rentabilidad_demostrada"])
        self.assertIsNone(r["pnl_broker"])

    def test_bloques_no_son_una_promesa_de_constancia(self):
        r = evaluar([fila(i, "WIN" if i % 20 < (12 if i < 20 else 11) else "LOSS")
                     for i in range(40)])
        self.assertEqual(r["bloques_20_cumplen_60"], 1)
        self.assertFalse(r["todos_bloques_20_cumplen_60"])

    def test_rechaza_fill_desconocido_pendientes_y_duplicados(self):
        r = evaluar([fila(1), fila(1), fila(2, ""),
                     fila(3, "WIN", "SIN_VELA_POSTERIOR_EN_BUFFER"),
                     fila(4, "EMPATE"), {**fila(5), "decision": "OPERAR"}])
        self.assertEqual(r["resueltas_validas"], 1)
        self.assertEqual(r["pendientes_sin_resultado"], 1)
        self.assertEqual(r["descartes"]["ID_DUPLICADO_O_VACIO"], 1)
        self.assertEqual(r["descartes"]["NO_RECHAZADA"], 1)
        self.assertEqual(r["descartes"]["CALIDAD_O_RESULTADO_INVALIDO"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)

    def test_sin_datos_no_declara_60_constante(self):
        r = evaluar([])
        self.assertIsNone(r["global"]["winrate_pct"])
        self.assertFalse(r["todos_bloques_20_cumplen_60"])
        self.assertFalse(r["autoriza_operaciones"])


if __name__ == "__main__":
    unittest.main()
