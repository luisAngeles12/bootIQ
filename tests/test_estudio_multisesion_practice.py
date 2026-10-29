import unittest
from unittest.mock import patch

from estudio_multisesion_practice import estudiar_sesiones


def evento(resultado, tiempo="TIEMPO_VERIFICADO"):
    return {"resultado": resultado, "calidad_tiempo": tiempo,
            "direccion": "call"}


class EstudioMultisesionPracticeTests(unittest.TestCase):
    @patch("estudio_multisesion_practice.comparar_estrategias")
    def test_no_combina_candidatos_de_distintas_estrategias(self, comparar):
        comparar.return_value = {
            "RUPTURA_RETEST": [evento("LOSS")],
            "RECHAZO_ZONA": [evento("WIN")],
            "CONTINUACION_TENDENCIA": [],
        }
        r = estudiar_sesiones([("USDINR-OTC", 1793148931, {})])
        self.assertEqual(r["RUPTURA_RETEST"]["resumen"]["LOSS"], 1)
        self.assertEqual(r["RUPTURA_RETEST"]["resumen"]["WIN"], 0)
        self.assertEqual(r["RECHAZO_ZONA"]["resumen"]["WIN"], 1)
        self.assertEqual(r["CONTINUACION_TENDENCIA"]["resumen"]["senales_no_solapadas"], 0)
        self.assertTrue(all(not x["evidencia"]["operaciones_autorizadas"]
                            for x in r.values()))

    @patch("estudio_multisesion_practice.comparar_estrategias")
    def test_una_sesion_no_basta_aunque_gane_todo(self, comparar):
        comparar.return_value = {
            "RUPTURA_RETEST": [evento("WIN") for _ in range(25)],
            "RECHAZO_ZONA": [],
            "CONTINUACION_TENDENCIA": [],
        }
        r = estudiar_sesiones([("USDINR-OTC", 1793148931, {})])
        self.assertEqual(r["RUPTURA_RETEST"]["resumen"]["wr_hipotetico"], 100.0)
        self.assertEqual(r["RUPTURA_RETEST"]["evidencia"]["estado"], "NO_VALIDADA")
        self.assertIn("MENOS_DE_TRES_DIAS",
                      r["RUPTURA_RETEST"]["evidencia"]["motivos"])


if __name__ == "__main__":
    unittest.main()
