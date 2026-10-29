import unittest

from evaluar_captura_fresca_practice import diagnostico_direcciones


class DiagnosticoDireccionesTests(unittest.TestCase):
    def test_call_put_separados_sin_reclasificar_empates(self):
        eventos = [
            {"direccion": "call", "resultado": "WIN", "calidad_tiempo": "LATENCIA_NO_REGISTRADA"},
            {"direccion": "call", "resultado": "LOSS", "calidad_tiempo": "LATENCIA_NO_REGISTRADA"},
            {"direccion": "put", "resultado": "LOSS", "calidad_tiempo": "DETECCION_TARDIA"},
            {"direccion": "put", "resultado": "EMPATE", "calidad_tiempo": "DETECCION_TARDIA"},
            {"direccion": "put", "resultado": "SIN_FUTURO", "calidad_tiempo": "DETECCION_TARDIA"},
        ]
        resumen = diagnostico_direcciones(eventos)
        self.assertEqual(resumen["call"]["wr_hipotetico"], 50.0)
        self.assertEqual(resumen["put"]["wr_hipotetico"], 0.0)
        self.assertEqual(resumen["put"]["EMPATE"], 1)
        self.assertEqual(resumen["put"]["SIN_FUTURO"], 1)
        self.assertEqual(resumen["put"]["detecciones_tardias"], 3)

    def test_direccion_sin_muestra_no_inventa_resultados(self):
        resumen = diagnostico_direcciones([])
        self.assertIsNone(resumen["call"]["wr_hipotetico"])
        self.assertIsNone(resumen["put"]["wr_hipotetico"])
        self.assertEqual(resumen["call"]["senales_no_solapadas"], 0)


if __name__ == "__main__":
    unittest.main()
