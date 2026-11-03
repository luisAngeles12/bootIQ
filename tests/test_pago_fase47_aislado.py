"""Regresiones de la puerta economica PRACTICE: no importa broker."""
import unittest
from evaluar_pago_practice import evaluar_viabilidad_pago

def eventos(n=120, payout=.8):
    return [{
        "resultado": "WIN" if i < 90 else "LOSS",
        "calidad_tiempo": "TIEMPO_VERIFICADO",
        "payout_neto": payout,
        "payout_fuente": "PRACTICE_PREENTRADA",
        "timestamp_payout_utc": 1000 + i * 60,
        "timestamp_entrada_hipotetica": 1001 + i * 60,
    } for i in range(n)]

class PagoFase47Aislado(unittest.TestCase):
    def test_sin_payout_bloquea(self):
        e = eventos()
        for x in e: x["payout_neto"] = None
        r = evaluar_viabilidad_pago(e)
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertIn("PAYOUT_NO_VERIFICADO", r["motivos"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_payout_postentrada_bloquea(self):
        e = eventos()
        e[0]["timestamp_payout_utc"] = e[0]["timestamp_entrada_hipotetica"]
        r = evaluar_viabilidad_pago(e)
        self.assertIn("PAYOUT_SIN_TIEMPO_PREENTRADA_VERIFICABLE", r["motivos"])
        self.assertEqual(r["estado"], "NO_VALIDADA")

    def test_payout_bajo_no_aprueba_rentabilidad(self):
        r = evaluar_viabilidad_pago(eventos(payout=.1))
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertFalse(r["operaciones_autorizadas"])

    def test_muestra_sintetica_favorable_no_autoriza_trading(self):
        e = eventos(300)
        for x in e: x["resultado"] = "WIN"
        r = evaluar_viabilidad_pago(e)
        self.assertEqual(r["estado"], "EVIDENCIA_ECONOMICA_PRELIMINAR")
        self.assertFalse(r["operaciones_autorizadas"])

if __name__ == "__main__":
    unittest.main()
