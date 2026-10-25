import unittest
from auditoria_evidencia_core4_multiventana import evaluar_evidencia_multiventana, evaluar_rutas_por_separado


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


    def test_septiembre_octubre_no_mezclan_r1_y_r1r2(self):
        rutas = evaluar_rutas_por_separado([
            {"regla":"R1_INDEFINIDO_PREMIUM", "ventana":"sep15-18", "wins":5, "losses":1},
            {"regla":"R1_INDEFINIDO_PREMIUM", "ventana":"oct12", "wins":9, "losses":3},
            {"regla":"R1_INDEFINIDO_PREMIUM|R2_RECHAZO_COMPRADOR_CONFIRMADO",
             "ventana":"sep15-18", "wins":1, "losses":0},
            {"regla":"R1_INDEFINIDO_PREMIUM|R2_RECHAZO_COMPRADOR_CONFIRMADO",
             "ventana":"oct12", "wins":3, "losses":1},
        ])
        self.assertEqual(rutas["R1_INDEFINIDO_PREMIUM"]["n"], 18)
        self.assertEqual(rutas["R1_INDEFINIDO_PREMIUM"]["wilson_inferior_95"], 54.78)
        combinado = rutas["R1_INDEFINIDO_PREMIUM|R2_RECHAZO_COMPRADOR_CONFIRMADO"]
        self.assertEqual(combinado["n"], 5)
        self.assertEqual(combinado["wilson_inferior_95"], 37.55)
        self.assertFalse(any(v["supera_59_con_confianza"] for v in rutas.values()))

    def test_no_acepta_ruta_anonima(self):
        with self.assertRaises(ValueError):
            evaluar_rutas_por_separado([{"ventana":"oct","wins":3,"losses":1}])

if __name__=="__main__":
    unittest.main()
