import unittest
from auditoria_generacion_fase33 import auditar_generacion_sin_core4


class GeneracionFase33Tests(unittest.TestCase):
    @staticmethod
    def fila(dia, resultado="WIN", familia="CONTINUACIÓN"):
        return {"core4_match_previo": "False", "familia_setup": familia,
                "calidad_setup": "BUENA", "resultado_hipotetico": resultado,
                "fecha_senal": f"2026-10-{dia:02d}T12:00:00+00:00"}

    def test_no_match_contado_sin_promocion(self):
        filas = [self.fila(12, "WIN")]*80 + [self.fila(12, "LOSS")]*20
        r = auditar_generacion_sin_core4(filas)
        self.assertEqual(r["sin_match"], 100)
        g = r["grupos"][("CONTINUACIÓN", "BUENA")]
        self.assertEqual(g["winrate_hipotetico"], 80.0)
        self.assertFalse(g["cumple_cobertura_exploratoria"])
        self.assertFalse(g["autoriza_operar"])

    def test_pico_un_dia_no_gana_en_otros(self):
        filas = [self.fila(12, "WIN")]*80 + [self.fila(12, "LOSS")]*20
        filas += [self.fila(13, "WIN")]*8 + [self.fila(13, "LOSS")]*12
        filas += [self.fila(14, "WIN")]*8 + [self.fila(14, "LOSS")]*12
        r = auditar_generacion_sin_core4(filas)
        g = r["grupos"][("CONTINUACIÓN", "BUENA")]
        self.assertFalse(g["cumple_cobertura_exploratoria"])
        self.assertEqual(len(g["por_dia"]), 3)

    def test_tres_dias_y_wilson_permanece_sin_autoridad(self):
        filas = []
        for dia in (12, 13, 14):
            filas += [self.fila(dia, "WIN")]*40
            filas += [self.fila(dia, "LOSS")]*10
        r = auditar_generacion_sin_core4(filas)
        g = r["grupos"][("CONTINUACIÓN", "BUENA")]
        self.assertTrue(g["cumple_cobertura_exploratoria"])
        self.assertFalse(g["autoriza_operar"])
        self.assertFalse(r["autoriza_operar"])

    def test_sin_match_debe_ser_false_explicito(self):
        filas = [self.fila(12), {"core4_match_previo": True,
                 "resultado_hipotetico": "LOSS"},
                 {"resultado_hipotetico": "WIN"}]
        r = auditar_generacion_sin_core4(filas)
        self.assertEqual(r["sin_match"], 1)

    def test_sin_etiqueta_no_imputa_win(self):
        filas = [self.fila(12, ""), self.fila(12, "WIN")]
        r = auditar_generacion_sin_core4(filas)
        self.assertEqual(r["sin_match"], 2)
        self.assertEqual(r["sin_match_sin_resultado_o_fecha"], 1)
        self.assertEqual(r["grupos"][("CONTINUACIÓN", "BUENA")]["n"], 1)


if __name__ == "__main__":
    unittest.main()
