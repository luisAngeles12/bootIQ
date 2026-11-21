"""Regresiones de diagnostico de inactividad. Cero imports de broker."""
import unittest

from diagnostico_inactividad_practice import resumen_inactividad, texto_inactividad


class InactividadPracticeTests(unittest.TestCase):
    def diagnostico(self, metricas, senales=5, aperturas=0):
        return resumen_inactividad(
            metricas, senales, aperturas,
            memoria_oficial_estado="AUSENTE",
            segundos_sin_apertura=3900,
        )

    def test_cerebro_rechaza_todo_y_memoria_ausente(self):
        x = self.diagnostico({"cerebro_no_operar": 5})
        self.assertEqual(x["estado"], "CEREBRO_SIN_AUTORIZACION")
        self.assertEqual(x["memoria_oficial_estado_inicio"], "AUSENTE")
        self.assertEqual(x["segundos_sin_apertura_confirmada"], 3900)
        self.assertIn("CEREBRO_SIN_AUTORIZACION", texto_inactividad(x))
        self.assertTrue(x["no_autoriza_operaciones"])

    def test_no_hay_mercados(self):
        x = self.diagnostico({}, senales=0)
        self.assertEqual(x["estado"], "SIN_MERCADOS_ANALIZADOS")

    def test_no_hay_candidatas(self):
        x = self.diagnostico({"mercados_analizados": 20}, senales=0)
        self.assertEqual(x["estado"], "SIN_CANDIDATAS_GENERADAS")

    def test_candidatas_descartadas(self):
        x = self.diagnostico({
            "mercados_analizados": 20,
            "candidatas_generadas": 9,
        }, senales=0)
        self.assertEqual(x["estado"], "CANDIDATAS_DESCARTADAS_ANTES_DE_SENAL_FINAL")

    def test_fallo_envio(self):
        x = self.diagnostico({"directas_no_ejecutadas": 1})
        self.assertEqual(x["estado"], "AUTORIZADAS_PERO_ENVIO_NO_EJECUTADO")

    def test_protocolos_pendientes(self):
        x = self.diagnostico({"autorizadas_protocolo": 2})
        self.assertEqual(x["estado"], "AUTORIZADAS_A_PROTOCOLO_SIN_APERTURA_DIRECTA")

    def test_aperturas_confirmadas_tienen_prioridad(self):
        x = self.diagnostico({"cerebro_no_operar": 3}, aperturas=1)
        self.assertEqual(x["estado"], "APERTURAS_CONFIRMADAS")


if __name__ == "__main__":
    unittest.main()
