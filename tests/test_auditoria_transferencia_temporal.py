import unittest

from auditoria_transferencia_temporal import comparar_ventanas_por_fuente


class TransferenciaTemporalTests(unittest.TestCase):
    def test_distingue_desviaciones_de_la_misma_fuente_en_dos_ventanas(self):
        septiembre = [
            {"clave_probabilidad_principal": "FUENTE_A",
             "probabilidad_estimada": "60", "resultado_hipotetico": "WIN",
             "activo": "AAA", "fecha_senal": "1789473960"},
            {"clave_probabilidad_principal": "FUENTE_A",
             "probabilidad_estimada": "60", "resultado_hipotetico": "LOSS",
             "activo": "BBB", "fecha_senal": "1789474020"},
        ]
        octubre = [
            {"clave_probabilidad_principal": "FUENTE_A",
             "probabilidad_estimada": "60", "resultado_hipotetico": "LOSS",
             "activo": "CCC", "fecha_senal": "1791807060"},
            {"clave_probabilidad_principal": "FUENTE_A",
             "probabilidad_estimada": "60", "resultado_hipotetico": "LOSS",
             "activo": "DDD", "fecha_senal": "1791807120"},
        ]
        resumen, descartadas = comparar_ventanas_por_fuente(
            [("septiembre", septiembre), ("octubre", octubre)],
            minimo_global=4,
        )
        self.assertEqual(descartadas, {"septiembre": 0, "octubre": 0})
        self.assertEqual(len(resumen), 1)
        self.assertEqual(resumen[0]["n_total"], 4)
        self.assertEqual(resumen[0]["rango_brecha_pp"], 50.0)
        self.assertEqual(
            resumen[0]["ventanas"]["septiembre"]["winrate_hipotetico"], 50.0
        )
        self.assertEqual(
            resumen[0]["ventanas"]["octubre"]["winrate_hipotetico"], 0.0
        )

    def test_no_confunde_resultados_reales_con_hipoteticos(self):
        datos = [
            {"clave_probabilidad_principal": "A", "probabilidad_estimada": "70",
             "resultado": "WIN", "resultado_hipotetico": ""},
        ]
        resumen, descartadas = comparar_ventanas_por_fuente(
            [("a", datos), ("b", datos)], minimo_global=0
        )
        self.assertEqual(resumen, [])
        self.assertEqual(descartadas, {"a": 1, "b": 1})

    def test_no_duplica_nombre_de_ventana_ni_fuente_solo_en_un_periodo(self):
        datos = [{"clave_probabilidad_principal": "A",
                  "probabilidad_estimada": "55",
                  "resultado_hipotetico": "WIN"}]
        with self.assertRaises(ValueError):
            comparar_ventanas_por_fuente([("x", datos), ("x", datos)])
        resumen, _ = comparar_ventanas_por_fuente(
            [("x", datos), ("y", [])], minimo_global=0
        )
        self.assertEqual(resumen, [])


if __name__ == "__main__":
    unittest.main()
