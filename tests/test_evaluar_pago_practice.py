"""Pruebas de rentabilidad teorica condicionada al payout PRACTICE."""
import unittest

from evaluar_pago_practice import evaluar_viabilidad_pago


def eventos(wins, losses, pago=None, fuente="PRACTICE_PREENTRADA"):
    return [
        {"resultado": "WIN" if i < wins else "LOSS",
         "calidad_tiempo": "TIEMPO_VERIFICADO",
         "payout_neto": pago, "payout_fuente": fuente,
         "timestamp_entrada_hipotetica": 1000 + i * 60,
         "timestamp_payout_utc": 999 + i * 60}
        for i in range(wins + losses)
    ]


class PagoPracticeTests(unittest.TestCase):
    def test_no_inventa_pago_ni_rentabilidad(self):
        r = evaluar_viabilidad_pago(eventos(100, 0))
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertIn("PAYOUT_NO_VERIFICADO", r["motivos"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_57_no_basta_con_pago_muy_bajo(self):
        r = evaluar_viabilidad_pago(eventos(70, 30, .6))
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertEqual(r["equilibrio_con_payout_minimo_pct"], 62.5)
        self.assertIn("LIMITE_ESTADISTICO_NO_SUPERA_OBJETIVO_Y_EQUILIBRIO",
                      r["motivos"])

    def test_muestra_sintetica_favorable_solo_evidencia_preliminar(self):
        r = evaluar_viabilidad_pago(eventos(300, 0, .8))
        self.assertEqual(r["estado"], "EVIDENCIA_ECONOMICA_PRELIMINAR")
        self.assertEqual(r["equilibrio_con_payout_minimo_pct"], 55.56)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_pago_observado_despues_no_sirve(self):
        r = evaluar_viabilidad_pago(eventos(200, 0, .8, "POST_RESULTADO"))
        self.assertIn("PAYOUT_SIN_PROCEDENCIA_PREENTRADA", r["motivos"])
        self.assertEqual(r["estado"], "NO_VALIDADA")

    def test_pago_minimo_rige_y_no_la_media(self):
        filas = eventos(200, 0, .9)
        filas[0]["payout_neto"] = .01
        r = evaluar_viabilidad_pago(filas)
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertGreater(r["equilibrio_con_payout_minimo_pct"], 98)
        self.assertFalse(r["operaciones_autorizadas"])


    def test_pago_posterior_a_entrada_es_invalido_aunque_todo_gane(self):
        filas = eventos(200, 0, .8)
        filas[0]["timestamp_payout_utc"] = (
            filas[0]["timestamp_entrada_hipotetica"] + 1
        )
        r = evaluar_viabilidad_pago(filas)
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertIn("PAYOUT_SIN_TIEMPO_PREENTRADA_VERIFICABLE", r["motivos"])

    def test_pago_antiguo_o_sin_timestamp_es_invalido(self):
        for invalido in (None, 500, True):
            with self.subTest(valor=invalido):
                filas = eventos(200, 0, .8)
                filas[0]["timestamp_payout_utc"] = invalido
                r = evaluar_viabilidad_pago(filas)
                self.assertEqual(r["estado"], "NO_VALIDADA")
                self.assertIn("PAYOUT_SIN_TIEMPO_PREENTRADA_VERIFICABLE",
                              r["motivos"])


if __name__ == "__main__":
    unittest.main()
