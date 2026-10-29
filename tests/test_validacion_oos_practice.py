"""Ensayos de no filtracion de holdout para estrategia PRACTICE."""
import unittest
from datetime import datetime, timezone

from validacion_oos_practice import validar_oos_por_dias

NOMBRES = ("RUPTURA_RETEST", "RECHAZO_ZONA", "CONTINUACION_TENDENCIA")


def dia(n):
    return int(datetime(2026, 10, n, tzinfo=timezone.utc).timestamp())


def eventos(comienzo, victorias, perdidas):
    return [
        {"timestamp_senal": comienzo + 60 * (i + 1),
         "resultado": "WIN" if i < victorias else "LOSS",
         "calidad_tiempo": "TIEMPO_VERIFICADO"}
        for i in range(victorias + perdidas)
    ]


def sesiones(holdout_estrategia_b=5):
    datos = {nombre: [] for nombre in NOMBRES}
    for n in range(1, 11):
        instante = dia(n)
        datos[NOMBRES[0]].append((
            "USDINR-OTC", instante, eventos(instante, 36 if n <= 7 else 40,
                                            4 if n <= 7 else 0)))
        datos[NOMBRES[1]].append((
            "USDINR-OTC", instante, eventos(
                instante, 39 if n <= 7 else holdout_estrategia_b,
                1 if n <= 7 else 40 - holdout_estrategia_b)))
        datos[NOMBRES[2]].append((
            "USDINR-OTC", instante, eventos(instante, 15, 25)))
    return datos


class ValidacionOOSTests(unittest.TestCase):
    def test_holdout_no_puede_reseleccionar_ganador(self):
        resultado = validar_oos_por_dias(sesiones(5))
        self.assertEqual(resultado["estrategia_fijada"], "RECHAZO_ZONA")
        self.assertEqual(resultado["estado"], "OOS_NO_VALIDADO")
        self.assertIn("HOLDOUT_BAJO_CRITERIOS", resultado["motivos"])
        self.assertEqual(resultado["dias_desarrollo"], 7)
        self.assertEqual(resultado["dias_holdout"], 3)
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_holdout_favorable_solo_evidencia_preliminar(self):
        resultado = validar_oos_por_dias(sesiones(39))
        self.assertEqual(resultado["estado"], "EVIDENCIA_OOS_PRELIMINAR")
        self.assertEqual(resultado["estrategia_fijada"], "RECHAZO_ZONA")
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_una_sesion_no_se_trata_como_holdout(self):
        datos = {nombre: [("USDINR-OTC", dia(1), eventos(dia(1), 40, 0))]
                 for nombre in NOMBRES}
        resultado = validar_oos_por_dias(datos)
        self.assertEqual(resultado["estado"], "OOS_NO_VALIDADO")
        self.assertIn("MENOS_DE_DOS_DIAS", resultado["motivos"])

    def test_catalogo_incompleto_se_rechaza(self):
        datos = sesiones()
        del datos[NOMBRES[0]]
        with self.assertRaisesRegex(ValueError, "CATALOGO_ESTRATEGIAS_INCOMPLETO"):
            validar_oos_por_dias(datos)


if __name__ == "__main__":
    unittest.main()
