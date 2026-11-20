import unittest
from investigar_patrones_practice import explorar


def filas(n=30):
    return [{"order_id": str(i), "fecha": f"2026-11-{1+i//10:02d}T12:{i%10:02d}:00+00:00",
             "estado": "CERRADA", "modo_cuenta_configurado": "PRACTICE",
             "resultado": "20.75" if i%10 < 6 else "-25",
             "patron": "CHOCH", "origen_autoridad": "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"}
            for i in range(n)]


class ExplorarPatronesTests(unittest.TestCase):
    def test_tercios_exploratorios_no_autorizan(self):
        r = explorar(filas())
        f = r["familias"][0]
        self.assertEqual(f["n"], 30)
        self.assertEqual([p["n"] for p in f["tercios_cronologicos"]], [10, 10, 10])
        self.assertTrue(f["tercios_todos_60_y_netos"])
        self.assertFalse(f["evidencia_v3_prospectiva_certificada"])
        self.assertFalse(r["autoriza_cambiar_reglas"])

    def test_no_selecciona_solo_resultados_favorables(self):
        r = explorar(filas(30) + [dict(filas(1)[0], order_id="999", resultado="-25")])
        self.assertEqual(r["total_evaluables"], 31)
        self.assertEqual(r["global"]["losses"], 13)

    def test_rechaza_real_y_no_confirmado(self):
        datos = filas(3)
        datos[0]["modo_cuenta_configurado"] = "REAL"
        datos[1]["modo_cuenta_configurado"] = ""
        r = explorar(datos)
        self.assertEqual(r["total_evaluables"], 1)
        self.assertEqual(r["descartes"]["MODO_NO_CONFIRMADO"], 2)

    def test_separa_origen_bootstrap_y_v3(self):
        datos = filas(30)
        datos[-1]["origen_autoridad"] = "V3"
        r = explorar(datos)
        self.assertEqual(len(r["familias"]), 2)
        self.assertEqual(r["familias"][1]["n"], 1)
        self.assertIsNone(r["familias"][1]["tercios_cronologicos"])

    def test_excluye_duplicados_y_empates(self):
        datos = filas(3)
        datos[1]["order_id"] = datos[0]["order_id"]
        datos[2]["resultado"] = "0"
        r = explorar(datos)
        self.assertEqual(r["total_evaluables"], 1)
        self.assertEqual(r["descartes"]["ID_AUSENTE_O_DUPLICADO"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)


if __name__ == "__main__":
    unittest.main()
