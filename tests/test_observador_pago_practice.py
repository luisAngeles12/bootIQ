"""Pruebas de comisiones TURBO del WebSocket, sin broker."""
import unittest

from observador_pago_practice import leer_comision_turbo


class ObservadorPagoPracticeTests(unittest.TestCase):
    def test_comision_reciente_solo_estimacion_sombra(self):
        r = leer_comision_turbo({"USDINR-OTC": {1000: 15}},
                                "USDINR-OTC", 1001)
        self.assertEqual(r["estado"], "COMISION_RECIENTE_ESTIMACION_CONSERVADORA")
        self.assertEqual(r["payout_neto"], .84)
        self.assertFalse(r["operable"])

    def test_comision_desactualizada_no_sirve(self):
        r = leer_comision_turbo({"USDINR-OTC": {1000: 15}},
                                "USDINR-OTC", 1061)
        self.assertEqual(r["estado"], "PAYOUT_NO_VERIFICADO")
        self.assertEqual(r["motivo"], "COTIZACION_DESACTUALIZADA")

    def test_otro_activo_no_comparte_pago(self):
        r = leer_comision_turbo({"EURUSD-OTC": {1000: 10}},
                                "USDINR-OTC", 1001)
        self.assertEqual(r["motivo"], "SIN_EVENTO_ACTIVO")

    def test_comision_futura_o_corrupta_es_bloqueada(self):
        for datos in ({"USDINR-OTC": {1002: 20}},
                      {"USDINR-OTC": {1000: float("nan")}},
                      {"USDINR-OTC": {1000: -1}}):
            with self.subTest(datos=datos):
                r = leer_comision_turbo(datos, "USDINR-OTC", 1001)
                self.assertEqual(r["estado"], "PAYOUT_NO_VERIFICADO")
                self.assertFalse(r["operable"])

    def test_sin_evento_no_inventa_pago(self):
        r = leer_comision_turbo({}, "USDINR-OTC", 1001)
        self.assertIsNone(r["payout_neto"])
        self.assertEqual(r["motivo"], "SIN_EVENTO_ACTIVO")


if __name__ == "__main__":
    unittest.main()
