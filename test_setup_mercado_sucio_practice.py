"""Defensa SUCIO/CAOTICO independiente del puntaje del setup.

Esta prueba usa solo motor_setup; no conecta al broker.
"""
import unittest

from motor_setup import clasificar_setup_estrategico


class CalidadMercadoSetupTests(unittest.TestCase):
    def _clasificar(self, calidad, puntaje=95):
        senal = {
            "patron": "pullback alcista a EMA",
            "direccion": "call",
            "puntaje": puntaje,
        }
        contexto = {
            "calidad_mercado": calidad,
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "direccion_tendencia": "ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
            "fuerza_tendencia": 65,
            "pa_tipo": "RECHAZO_COMPRADOR_CONFIRMADO",
            "pa_direccion": "CALL",
            "cerca_soporte": True,
        }
        return clasificar_setup_estrategico(senal, contexto)

    def test_sucio_nunca_premium_aunque_el_puntaje_sea_alto(self):
        for calidad in ("SUCIO", "sucio", " SUCIO "):
            with self.subTest(calidad=calidad):
                dato = self._clasificar(calidad)
                self.assertEqual(dato["calidad_setup"], "DEBIL")
                self.assertEqual(dato["modo_entrada"], "NO_OPERAR")
                self.assertTrue(dato["riesgo_estructural_critico_setup"])

    def test_caotico_nunca_premium_aunque_el_puntaje_sea_alto(self):
        for calidad in ("CAOTICO", "caotico", " CAOTICO "):
            with self.subTest(calidad=calidad):
                dato = self._clasificar(calidad)
                self.assertEqual(dato["calidad_setup"], "DEBIL")
                self.assertEqual(dato["modo_entrada"], "NO_OPERAR")
                self.assertTrue(dato["riesgo_estructural_critico_setup"])

    def test_limpio_no_recibe_veto_sucio(self):
        dato = self._clasificar("LIMPIO")
        self.assertEqual(dato["calidad_setup"], "PREMIUM")
        self.assertNotEqual(dato["modo_entrada"], "NO_OPERAR")

    def test_normal_no_recibe_veto_sucio(self):
        dato = self._clasificar("NORMAL")
        self.assertEqual(dato["calidad_setup"], "PREMIUM")
        self.assertNotEqual(dato["modo_entrada"], "NO_OPERAR")


if __name__ == "__main__":
    unittest.main()
