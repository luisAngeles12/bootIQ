import unittest
from auditoria_familias_fase3 import evaluar_familias


class FamiliaFase3Tests(unittest.TestCase):
    def test_un_solo_dia_no_acredita_generalizacion(self):
        datos=[{"familia_setup":"CONTINUACIÓN","fecha_senal":"2026-10-12",
                "resultado_hipotetico":"WIN"} for _ in range(80)]
        r=evaluar_familias(datos, minimo_por_dia=30)["CONTINUACIÓN"]
        self.assertFalse(r["supera_meta_en_dos_dias"])
        self.assertEqual(r["dias_con_muestra"],1)
        self.assertFalse(r["autoriza_operaciones"])

    def test_segundo_dia_perdedor_no_supera_meta(self):
        datos=[{"familia_setup":"REVERSIÓN","fecha_senal":"2026-10-12",
                "resultado_hipotetico":"WIN"} for _ in range(40)]
        datos.extend({"familia_setup":"REVERSIÓN","fecha_senal":"2026-10-13",
                      "resultado_hipotetico":"LOSS"} for _ in range(40))
        r=evaluar_familias(datos, minimo_por_dia=30)["REVERSIÓN"]
        self.assertEqual(r["dias_con_muestra"],2)
        self.assertFalse(r["supera_meta_en_dos_dias"])

    def test_sin_resultado_cerrado_se_excluye(self):
        datos=[{"familia_setup":"REVERSIÓN","resultado_hipotetico":"TIE"}]
        self.assertEqual(evaluar_familias(datos),{})


if __name__=="__main__":
    unittest.main()
