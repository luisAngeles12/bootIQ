import unittest

from auditoria_cobertura_estabilidad import resumir_cobertura_estabilidad


class CoberturaEstabilidadTests(unittest.TestCase):
    def test_divide_por_muestra_y_no_infiere_estabilidad(self):
        filas = [
            {"total": "4", "estabilidad_disponible": "False"},
            {"total": "5", "estabilidad_disponible": "False"},
            {"total": "11", "estabilidad_disponible": "True",
             "persistencia_direccion": "0.667"},
            {"total": "12", "estabilidad_disponible": "False"},
            {"total": "19", "estabilidad_disponible": "True",
             "persistencia_direccion": "1.0"},
            {"total": "20", "estabilidad_disponible": "True"},
            {"total": "50", "estabilidad_disponible": "True"},
        ]
        r, invalidas = resumir_cobertura_estabilidad(filas)
        self.assertEqual(invalidas, 0)
        self.assertEqual(r["0_4"]["sin_estabilidad"], 1)
        self.assertEqual(r["5_11"]["fuentes"], 2)
        self.assertEqual(r["5_11"]["estabilidad_disponible"], 1)
        self.assertEqual(r["12_19"]["estabilidad_disponible"], 1)
        self.assertEqual(r["20_49"]["fuentes"], 1)
        self.assertEqual(r["50_MAS"]["fuentes"], 1)

    def test_ausencia_no_se_convierte_en_estabilidad_ni_penalizacion(self):
        r, _ = resumir_cobertura_estabilidad([
            {"total": 30, "estabilidad_disponible": "", "persistencia_direccion": ""},
            {"total": 30},
        ])
        self.assertEqual(r["20_49"]["fuentes"], 2)
        self.assertEqual(r["20_49"]["sin_estabilidad"], 2)
        self.assertEqual(r["20_49"]["con_persistencia"], 0)

    def test_cuenta_persistencia_sin_confundirla_con_flag(self):
        r, _ = resumir_cobertura_estabilidad([
            {"total": 15, "estabilidad_disponible": False,
             "persistencia_direccion": "0.333"},
            {"total": 15, "estabilidad_disponible": True,
             "persistencia_direccion": "no_disponible"},
        ])
        self.assertEqual(r["12_19"]["estabilidad_disponible"], 1)
        self.assertEqual(r["12_19"]["con_persistencia"], 1)


if __name__ == "__main__":
    unittest.main()
