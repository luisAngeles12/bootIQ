"""Regresiones de paridad temporal PRACTICE, sin broker ni operaciones."""
import unittest

from paridad_sombra_practice import (
    comprobar_paridad, evaluar_flujo, reproducir_cierres,
)


def velas(minutos=26, inicio=0):
    salida = {}
    for t in range(inicio, inicio + minutos * 60):
        precio = 100.0 + 0.0001 * t + 0.0002 * (t % 13)
        salida[t] = {
            "from": t, "open": precio, "close": precio + 0.00001,
            "min": precio - 0.00001, "max": precio + 0.00002,
        }
    return salida


class PruebasParidadSombra(unittest.TestCase):
    def test_flujo_igual_replay_en_minutos_completos(self):
        datos = velas()
        llegadas = [(t + 1, v) for t, v in datos.items()]
        resultado = comprobar_paridad(datos, llegadas)
        self.assertTrue(resultado["paridad"])
        self.assertEqual(resultado["cierres_replay"], 26)
        self.assertFalse(resultado["operable"])
        self.assertTrue(all(x[1]["arbitraje"]["operable"] is False
                            for x in evaluar_flujo(llegadas)))

    def test_sin_anticipar_velas_de_minuto_siguiente(self):
        datos = velas()
        flujo = [(t + 1, v) for t, v in datos.items()]
        original = evaluar_flujo(flujo)
        futuro = velas(1, len(datos))
        # Cambiar drásticamente la proxima vela no altera decisiones previas.
        for v in futuro.values():
            v["open"] = 300
            v["close"] = 300
            v["min"] = 300
            v["max"] = 300
        extendido = evaluar_flujo(flujo + [(t + 1, v) for t, v in futuro.items()])
        self.assertEqual(original, extendido[:len(original)])

    def test_llegada_tardia_no_reescribe_el_pasado(self):
        datos = velas(2)
        llegadas = [(t + 1, v) for t, v in datos.items() if t != 59]
        llegadas.append((122, datos[59]))
        resultados = evaluar_flujo(llegadas)
        self.assertEqual([t for t, _ in resultados], [120])
        self.assertNotEqual(resultados, reproducir_cierres(datos))

    def test_minuto_incompleto_no_autoriza_arbitraje(self):
        datos = velas(2)
        llegadas = [(t + 1, v) for t, v in datos.items() if t != 15]
        self.assertEqual([fin for fin, _ in evaluar_flujo(llegadas)], [120])

    def test_recepciones_desordenadas_se_rechazan(self):
        datos = velas(1)
        with self.assertRaisesRegex(ValueError, "RECEPCIONES_DESORDENADAS"):
            evaluar_flujo([(3, datos[0]), (2, datos[1])])

    def test_vela_abierta_se_rechaza(self):
        datos = velas(1)
        with self.assertRaisesRegex(ValueError, "VELA_AUN_ABIERTA"):
            evaluar_flujo([(0, datos[0])])


if __name__ == "__main__":
    unittest.main()
