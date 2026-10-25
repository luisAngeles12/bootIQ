import unittest

from detector_riesgo_compuesto import evaluar_riesgo_compuesto


class RiesgoBaseProvisionalTests(unittest.TestCase):
    def test_media_provisional_no_agrega_riesgo(self):
        evidencia = {"direccion": "CALL", "base_estrategia": "MEDIA"}
        neutral = evaluar_riesgo_compuesto(evidencia)
        sin_etiqueta = evaluar_riesgo_compuesto({"direccion": "CALL"})
        self.assertEqual(neutral["riesgo_puntos"], sin_etiqueta["riesgo_puntos"])
        self.assertNotIn("base_estrategia_insuficiente", neutral["categorias_riesgo"])

    def test_debil_explicita_conserva_penalizacion(self):
        debil = evaluar_riesgo_compuesto({"direccion": "PUT", "base_estrategia": "DEBIL"})
        neutral = evaluar_riesgo_compuesto({"direccion": "PUT", "base_estrategia": "MEDIA"})
        self.assertEqual(debil["riesgo_puntos"], neutral["riesgo_puntos"] + 1)
        self.assertIn("base_estrategia_insuficiente", debil["categorias_riesgo"])

    def test_no_cambia_otras_condiciones_de_riesgo(self):
        comunes = {"direccion": "PUT", "tipo_mercado": "TENDENCIA_ALCISTA",
                   "accion_precio": "PUT_SOPORTE_CERCA_SIN_RUPTURA"}
        media = evaluar_riesgo_compuesto({**comunes, "base_estrategia": "MEDIA"})
        sin_base = evaluar_riesgo_compuesto(comunes)
        self.assertEqual(media, sin_base)


if __name__ == "__main__":
    unittest.main()
