import unittest

from price_action import diagnosticar_micro_rechazo_1s


def v(t, apertura, cierre, minimo, maximo):
    return {"from": t, "open": apertura, "close": cierre,
            "min": minimo, "max": maximo}


class MicroRechazoSegundoTests(unittest.TestCase):
    def test_call_dos_cierres_despues_de_penetrar_soporte(self):
        velas = [v(100, 99, 99, 98, 100),
                 v(101, 99, 101, 99, 101),
                 v(102, 101, 102, 101, 103)]
        r = diagnosticar_micro_rechazo_1s(velas, 100, "call", 103)
        self.assertEqual(r["estado"], "MICRO_RECHAZO_CONFIRMADO")
        self.assertFalse(r["operable"])

    def test_put_dos_cierres_despues_de_penetrar_resistencia(self):
        velas = [v(200, 101, 101, 100, 102),
                 v(201, 101, 99, 99, 101),
                 v(202, 99, 98, 98, 99)]
        r = diagnosticar_micro_rechazo_1s(velas, 100, "put", 203)
        self.assertEqual(r["estado"], "MICRO_RECHAZO_CONFIRMADO")

    def test_una_sola_recuperacion_no_se_confirma(self):
        velas = [v(99, 101, 101, 100, 102),
                 v(100, 99, 99, 98, 100),
                 v(101, 99, 101, 99, 101)]
        r = diagnosticar_micro_rechazo_1s(velas, 100, "call", 102)
        self.assertEqual(r["estado"], "RECHAZO_EN_FORMACION")

    def test_ultima_vela_abierta_no_aporta_confirmacion(self):
        velas = [v(100, 99, 99, 98, 100),
                 v(101, 99, 101, 99, 101),
                 v(102, 101, 102, 101, 103)]
        r = diagnosticar_micro_rechazo_1s(velas, 100, "call", 102)
        self.assertEqual(r["estado"], "SIN_DATOS")

    def test_hueco_temporal_invalida(self):
        velas = [v(100, 99, 99, 98, 100),
                 v(102, 99, 101, 99, 101),
                 v(103, 101, 102, 101, 103)]
        r = diagnosticar_micro_rechazo_1s(velas, 100, "call", 104)
        self.assertEqual(r["estado"], "HUECO_TEMPORAL")

    def test_datos_antiguos_se_rechazan(self):
        velas = [v(100, 99, 99, 98, 100),
                 v(101, 99, 101, 99, 101),
                 v(102, 101, 102, 101, 103)]
        r = diagnosticar_micro_rechazo_1s(velas, 100, "call", 150)
        self.assertEqual(r["estado"], "DATOS_DESACTUALIZADOS")

    def test_no_hay_senal_si_no_hay_invasion(self):
        velas = [v(100, 101, 101, 101, 102),
                 v(101, 101, 102, 101, 103),
                 v(102, 102, 103, 102, 104)]
        r = diagnosticar_micro_rechazo_1s(velas, 100, "call", 103)
        self.assertEqual(r["estado"], "SIN_INVASION")


if __name__ == "__main__":
    unittest.main()
