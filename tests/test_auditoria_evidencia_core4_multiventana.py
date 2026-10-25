import unittest
from auditoria_evidencia_core4_multiventana import evaluar_evidencia_multiventana


class EvidenciaCore4MultiventanaTests(unittest.TestCase):
    def test_casos_septiembre_y_octubre_aun_no_justifican_59(self):
        r = evaluar_evidencia_multiventana([
            {"ventana":"sep15-18","wins":6,"losses":1},
            {"ventana":"oct12","wins":12,"losses":4},
        ])
        self.assertEqual(r["n"],23)
        self.assertEqual(r["wr_observado"],78.26)
        self.assertEqual(r["wilson_inferior_95"],58.1)
        self.assertFalse(r["supera_59_con_confianza"])
        self.assertFalse(r["autoriza_trading"])

    def test_una_racha_buena_no_reemplaza_ventanas(self):
        r=evaluar_evidencia_multiventana([{"ventana":"solo-un-dia","wins":60,"losses":0}])
        self.assertFalse(r["cumple_minimo_muestra_y_tiempo"])

    def test_tres_ventanas_sinteticas_pueden_superar_meta_sin_dar_autoridad(self):
        r=evaluar_evidencia_multiventana([
            {"ventana":str(i),"wins":18,"losses":2} for i in range(3)
        ])
        self.assertTrue(r["supera_59_con_confianza"])
        self.assertFalse(r["autoriza_trading"])

    def test_rechaza_ventanas_duplicadas_y_conteos_invalidos(self):
        with self.assertRaises(ValueError):
            evaluar_evidencia_multiventana([
                {"ventana":"dia","wins":2,"losses":1},
                {"ventana":"dia","wins":2,"losses":1},
            ])
        with self.assertRaises(ValueError):
            evaluar_evidencia_multiventana([{"ventana":"otro","wins":-1,"losses":2}])


if __name__=="__main__":
    unittest.main()
