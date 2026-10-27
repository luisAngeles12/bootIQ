import unittest
from auditoria_breakout_pre_evento_fase33 import auditar_velas_breakout


class ReplayBreakoutPreEventoTests(unittest.TestCase):
    @staticmethod
    def velas(lado):
        if lado == "call":
            c = [99.0]*128 + [101.5, 101.0]
            h = [100.0]*128 + [102.5, 102.0]
            l = [99.0]*128 + [98.5, 100.2]
        else:
            c = [96.0]*128 + [93.7, 94.0]
            h = [96.0]*128 + [96.2, 94.8]
            l = [95.0]*128 + [93.5, 93.8]
        return [{"from": str(1000000000+i*60), "open": str(c[i]),
                 "close": str(c[i]), "max": str(h[i]), "min": str(l[i])}
                for i in range(130)]

    def test_ambos_lados_reconocidos_solo_en_sombra(self):
        for lado in ("call", "put"):
            with self.subTest(lado=lado):
                x = auditar_velas_breakout(self.velas(lado), activo=lado)
                self.assertEqual(x["ventanas"], 1)
                self.assertEqual(x["actuales"], 0)
                self.assertEqual(x["sombra"], 1)
                self.assertFalse(x["autoriza_operar"])
                self.assertEqual(x["eventos"][0]["direccion"], lado.upper())

    def test_cantidad_insuficiente_cierra_sin_señales(self):
        x = auditar_velas_breakout(self.velas("call")[:129])
        self.assertEqual(x["ventanas"], 0)
        self.assertEqual(x["sombra"], 0)

    def test_evento_historico_no_depende_de_vela_futura(self):
        base = self.velas("call")
        extendida = base + [{"from": str(1000000000+130*60),
                            "open": "101", "close": "101",
                            "max": "102", "min": "100"}]
        a = auditar_velas_breakout(base)["eventos"][0]
        b = auditar_velas_breakout(extendida)["eventos"][0]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
