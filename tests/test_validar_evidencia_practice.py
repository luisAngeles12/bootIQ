import unittest
from datetime import datetime, timezone

from validar_evidencia_practice import (
    limite_inferior_wilson, verificar_evidencia_sostenida,
)


def ts(dia):
    return int(datetime(2026, 10, dia, tzinfo=timezone.utc).timestamp())


def eventos(wins, losses, calidad="TIEMPO_VERIFICADO"):
    return ([{"resultado": "WIN", "calidad_tiempo": calidad}] * wins
            + [{"resultado": "LOSS", "calidad_tiempo": calidad}] * losses)


class ValidacionEvidenciaPracticeTests(unittest.TestCase):
    def test_captura_37_84_no_esta_validada(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(27), eventos(14, 23, "LATENCIA_NO_REGISTRADA"))
        ])
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertEqual(r["wr_hipotetico"], 37.84)
        self.assertIn("MENOS_DE_TRES_DIAS", r["motivos"])
        self.assertIn("LATENCIA_SIN_VERIFICAR_O_TARDIA", r["motivos"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_pasar_57_en_un_solo_dia_no_basta(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(27), eventos(100, 0))
        ])
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertIn("MENOS_DE_TRES_DIAS", r["motivos"])

    def test_tres_dias_con_muestra_suficiente_solo_evidencia_preliminar(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(26), eventos(70, 10)),
            ("USDINR-OTC", ts(27), eventos(70, 10)),
            ("USDINR-OTC", ts(28), eventos(70, 10)),
        ])
        self.assertEqual(r["estado"], "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO")
        self.assertGreater(r["limite_inferior_95_pct"], 57)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_dia_con_resultado_malo_impide_validacion(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(26), eventos(80, 0)),
            ("USDINR-OTC", ts(27), eventos(7, 13)),
            ("USDINR-OTC", ts(28), eventos(80, 0)),
        ])
        self.assertIn("SESION_BAJO_OBJETIVO", r["motivos"])
        self.assertEqual(r["estado"], "NO_VALIDADA")

    def test_wilson_limita_muestras_pequenas(self):
        self.assertLess(limite_inferior_wilson(6, 10), .57)
        self.assertEqual(limite_inferior_wilson(0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
