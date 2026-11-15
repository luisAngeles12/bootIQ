"""Pruebas sin IQ, sin red y sin permisos de operacion."""
import unittest

from monitor_deriva_estrategias import MonitorDerivaSombra


class MonitorDerivaTest(unittest.TestCase):
    def test_no_emite_alerta_sin_dos_ventanas(self):
        m = MonitorDerivaSombra()
        for i in range(15):
            dato = m.registrar_cierre("CHOCH alcista", 20.75, str(i))
        self.assertEqual(dato["estado"], "MUESTRA_INSUFICIENTE")
        self.assertFalse(dato["cooldown_activado"])

    def test_detecta_deterioro_sin_bloquear(self):
        m = MonitorDerivaSombra()
        for i in range(8):
            m.registrar_cierre("pullback", 20.75, str(i))
        for i in range(8, 16):
            dato = m.registrar_cierre("pullback", -25, str(i))
        self.assertEqual(dato["estado"], "DETERIORO_CANDIDATO")
        self.assertLess(dato["expectativa_reciente"], 0)
        self.assertFalse(dato["cooldown_activado"])
        self.assertEqual(dato["modo"], "SHADOW_SIN_AUTORIDAD")

    def test_no_inventa_deterioro_si_ambas_ventanas_son_negativas(self):
        m = MonitorDerivaSombra()
        for i in range(16):
            dato = m.registrar_cierre("sweep", -25, str(i))
        self.assertEqual(dato["estado"], "SIN_DETERIORO_DETECTADO")

    def test_deduplica_cierre_por_order_id(self):
        m = MonitorDerivaSombra()
        self.assertIsNotNone(m.registrar_cierre("CHOCH", 20.75, "abc"))
        self.assertIsNone(m.registrar_cierre("CHOCH", -25, "abc"))
        dato = m.registrar_cierre("CHOCH", 20.75, "def")
        self.assertEqual(dato["observaciones_recientes"], 2)

    def test_valores_invalidos_no_entran(self):
        m = MonitorDerivaSombra()
        for valor in (None, "NaN", float("inf"), "x"):
            self.assertIsNone(m.registrar_cierre("EMA", valor, str(valor)))
        self.assertIsNone(m.registrar_cierre("", 20.75, "1"))
        self.assertIsNone(m.registrar_cierre("EMA", 20.75, ""))

    def test_patrones_independientes(self):
        m = MonitorDerivaSombra()
        for i in range(16):
            m.registrar_cierre("A", 20.75 if i < 8 else -25, "a"+str(i))
        dato = m.registrar_cierre("B", 20.75, "b0")
        self.assertEqual(dato["estado"], "MUESTRA_INSUFICIENTE")


if __name__ == "__main__":
    unittest.main()
