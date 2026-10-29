import unittest

from estrategias_contexto_fresco import (
    ruptura_retest, rechazo_zona, continuacion_tendencia,
    diagnosticar_estrategias,
)


def vela(i, o=101, c=101, l=100, h=102):
    return {"from": i * 60, "end": (i + 1) * 60,
            "open": o, "close": c, "low": l, "high": h}


def base():
    return [vela(i) for i in range(24)]


class EstrategiasContextoFrescoTests(unittest.TestCase):
    def test_ruptura_retest_call_con_nivel_previo(self):
        v = base()
        v[-3] = vela(21, 101, 103, 101, 103)
        v[-2] = vela(22, 103, 102.5, 101.9, 103)
        v[-1] = vela(23, 102.5, 104, 102.4, 104)
        r = ruptura_retest(v, "TENDENCIA_ALCISTA")
        self.assertEqual((r["direccion"], r["nivel_previo"]), ("call", 102))
        self.assertFalse(r["operable"])
        self.assertIsNone(ruptura_retest(v, "CAOTICO")["direccion"])

    def test_ruptura_retest_put_con_soporte_previo(self):
        v = base()
        v[-3] = vela(21, 101, 98, 98, 101)
        v[-2] = vela(22, 98, 98.5, 98, 100)
        v[-1] = vela(23, 98.5, 97, 97, 98.5)
        r = ruptura_retest(v, "TENDENCIA_BAJISTA")
        self.assertEqual((r["direccion"], r["nivel_previo"]), ("put", 100))

    def test_rechazo_zona_exige_recuperacion_posterior(self):
        v = base()
        v[-2] = vela(22, 100, 99, 98, 101)
        v[-1] = vela(23, 99, 101, 99, 102)
        r = rechazo_zona(v, "RANGO")
        self.assertEqual((r["direccion"], r["nivel_previo"]), ("call", 100))
        self.assertIsNone(rechazo_zona(v, "TENDENCIA_ALCISTA")["direccion"])

    def test_continuacion_exige_retroceso_y_confirmacion(self):
        v = base()
        v[-2] = vela(22, 102, 100, 99, 102)
        v[-1] = vela(23, 100, 103, 100, 103)
        r = continuacion_tendencia(v, "TENDENCIA_ALCISTA")
        self.assertEqual(r["direccion"], "call")
        self.assertFalse(r["operable"])

    def test_huecos_bloquean_las_tres(self):
        v = base()
        v[-1]["from"] += 60
        v[-1]["end"] += 60
        for r in diagnosticar_estrategias(v, "TENDENCIA_ALCISTA"):
            self.assertEqual(r["razon"], "HUECO_TEMPORAL")
            self.assertFalse(r["operable"])

    def test_no_usa_ultima_vela_si_falta_contexto(self):
        self.assertEqual(ruptura_retest(base()[:10], "TENDENCIA_ALCISTA")["razon"],
                         "SIN_DATOS")


if __name__ == "__main__":
    unittest.main()
