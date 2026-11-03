import unittest

from contexto_mercado_fresco import consolidar_minutos, diagnosticar_contexto


def velas(n=3600, tendencia=0.001):
    return {
        t: {"from": t, "open": 100 + t * tendencia,
            "close": 100 + (t + 1) * tendencia,
            "min": 100 + t * tendencia,
            "max": 100 + (t + 1) * tendencia}
        for t in range(n)
    }


class ContextoFrescoTests(unittest.TestCase):
    def test_consolida_solo_60_segundos_cerrados(self):
        minutos = consolidar_minutos(velas(125))
        self.assertEqual(len(minutos), 2)
        self.assertEqual([x["from"] for x in minutos], [0, 60])
        self.assertEqual(minutos[0]["end"], 60)
        self.assertEqual(minutos[0]["close"], 100.06)

    def test_no_construye_minuto_incompleto_con_hueco(self):
        datos = velas(120)
        del datos[43]
        minutos = consolidar_minutos(datos)
        self.assertEqual(len(minutos), 1)
        self.assertEqual(minutos[0]["from"], 60)

    def test_contexto_tendencia_no_autoriza_operar(self):
        minutos = consolidar_minutos(velas(1200))
        r = diagnosticar_contexto(minutos)
        self.assertEqual(r["estado"], "TENDENCIA_ALCISTA")
        self.assertFalse(r["operable"])

    def test_hueco_entre_minutos_bloquea(self):
        minutos = consolidar_minutos(velas(1260))
        del minutos[10]
        self.assertEqual(diagnosticar_contexto(minutos)["estado"], "SUCIO")

    def test_sin_calentamiento_no_inventa_contexto(self):
        self.assertEqual(diagnosticar_contexto([])["estado"], "SIN_DATOS")

    def test_no_acepta_precio_corrupto(self):
        datos = velas(60)
        datos[4]["close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "PRECIO_NO_FINITO"):
            consolidar_minutos(datos)


if __name__ == "__main__":
    unittest.main()
