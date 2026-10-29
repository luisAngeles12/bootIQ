import unittest

from sondear_velas_1s_practice import evaluar_captura_finalizada


def vela(t, apertura=101, cierre=101, minimo=100, maximo=102):
    return {
        "from": t, "open": apertura, "close": cierre,
        "min": minimo, "max": maximo,
        "_latencia_primera_recepcion_s": 0,
    }


class EvaluacionAutomaticaSondeoTests(unittest.TestCase):
    def test_fin_captura_evalua_sin_importar_broker_ni_ordenar(self):
        datos = {t: vela(t) for t in range(100, 183)}
        datos[120] = vela(120, 100, 99, 99, 101)
        datos[121] = vela(121, 99, 101, 99, 101)
        datos[122] = vela(122, 101, 101, 101, 102)
        datos[182] = vela(182, 101, 102, 100, 102)
        r = evaluar_captura_finalizada(datos)
        self.assertEqual(r["WIN"], 1)
        self.assertEqual(r["LOSS"], 0)
        self.assertEqual(r["con_tiempo_verificado"], 1)
        self.assertEqual(r["wr_hipotetico"], 100.0)
        self.assertEqual(r["senales_no_solapadas"], 1)

    def test_sin_muestra_no_proclama_winrate(self):
        r = evaluar_captura_finalizada({100: vela(100)})
        self.assertIsNone(r["wr_hipotetico"])
        self.assertEqual(r["senales_no_solapadas"], 0)


if __name__ == "__main__":
    unittest.main()
