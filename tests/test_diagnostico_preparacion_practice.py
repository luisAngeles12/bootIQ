"""Puerta de seguridad para la evaluacion del cerebro PRACTICE."""
import unittest
from unittest.mock import patch

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
        self.assertTrue(resultado["paridad"]["paridad"])
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_no_acepta_captura_sin_latencia(self):
        datos = muestra()
        for vela in datos.values():
            vela["_latencia_primera_recepcion_s"] = None
        resultado = diagnosticar_preparacion(datos)
        self.assertIn("PARIDAD_NO_DEMOSTRADA", resultado["motivos"])
        self.assertIsNone(resultado["paridad"]["paridad"])

    @patch("diagnostico_preparacion_practice.resumen_comparativa")
    def test_totales_sin_verificar_no_cumplen_minimo(self, comparativa):
        # 20 WIN/LOSS por estrategia no bastan si solo 14 tienen
        # tiempo verificado, aunque no existan detecciones tardias.
        comparativa.return_value = {
            nombre: {
                "WIN": 10, "LOSS": 10,
                "resultados_con_tiempo_verificado": 14,
                "sin_latencia_registrada": 0,
                "detecciones_tardias": 0,
                "latencia_invalida": 0,
            }
            for nombre in (
                "RUPTURA_RETEST", "RECHAZO_ZONA",
                "CONTINUACION_TENDENCIA"
            )
        }
        resultado = diagnosticar_preparacion(muestra(24 * 60))
        for nombre in comparativa.return_value:
            self.assertIn("MUESTRA_INSUFICIENTE_" + nombre, resultado["motivos"])
            self.assertIn("TIEMPOS_SIN_VALIDAR_" + nombre, resultado["motivos"])
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_no_acepta_huecos(self):
        datos = muestra()
        del datos[24]
        resultado = diagnosticar_preparacion(datos)
        self.assertIn("HUECO_ENTRE_VELAS", resultado["motivos"])
        self.assertFalse(resultado["operaciones_autorizadas"])


if __name__ == "__main__":
    unittest.main()
