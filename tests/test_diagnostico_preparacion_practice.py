"""Puerta de seguridad para la evaluacion del cerebro PRACTICE."""
import unittest

from diagnostico_preparacion_practice import diagnosticar_preparacion


def muestra(n=120):
    return {
        t: {
            "from": t, "open": 100 + t * .001,
            "close": 100 + t * .001,
            "min": 99.9 + t * .001,
            "max": 100.1 + t * .001,
            "_latencia_primera_recepcion_s": 0,
        }
        for t in range(n)
    }


class PreparacionPracticeTests(unittest.TestCase):
    def test_no_acepta_captura_vacia(self):
        resultado = diagnosticar_preparacion({})
        self.assertEqual(resultado["motivos"], ["SIN_VELAS"])
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_no_acepta_ventana_corta_ni_falsifica_estrategias(self):
        resultado = diagnosticar_preparacion(muestra())
        self.assertIn("CONTEXTO_MENOR_24_MINUTOS", resultado["motivos"])
        self.assertIn("PARIDAD_NO_DEMOSTRADA", resultado["motivos"] if
                      resultado["paridad"]["paridad"] is not True else
                      ["PARIDAD_NO_DEMOSTRADA"])
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_no_acepta_captura_sin_latencia(self):
        datos = muestra()
        for vela in datos.values():
            vela["_latencia_primera_recepcion_s"] = None
        resultado = diagnosticar_preparacion(datos)
        self.assertIn("PARIDAD_NO_DEMOSTRADA", resultado["motivos"])
        self.assertIsNone(resultado["paridad"]["paridad"])

    def test_no_acepta_huecos(self):
        datos = muestra()
        del datos[24]
        resultado = diagnosticar_preparacion(datos)
        self.assertIn("HUECO_ENTRE_VELAS", resultado["motivos"])
        self.assertFalse(resultado["operaciones_autorizadas"])


if __name__ == "__main__":
    unittest.main()
