"""Regresiones de paridad temporal PRACTICE, sin broker ni operaciones."""
import unittest

from paridad_sombra_practice import (
    comprobar_paridad, comprobar_paridad_recepcion_1s, evaluar_flujo, reproducir_cierres,
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

    def test_paridad_a_partir_de_latencias_observadas(self):
        datos = velas()
        latencias = {t: 0 for t in datos}
        resultado = comprobar_paridad_recepcion_1s(datos, latencias)
        self.assertTrue(resultado["paridad"])
        self.assertEqual(resultado["velas_con_retraso"], 0)
        self.assertFalse(resultado["operable"])

    def test_paridad_falla_por_retraso_de_ultima_vela(self):
        datos = velas()
        latencias = {t: 0 for t in datos}
        latencias[59] = 2
        resultado = comprobar_paridad_recepcion_1s(datos, latencias)
        self.assertFalse(resultado["paridad"])
        self.assertLess(resultado["cierres_flujo"], resultado["cierres_replay"])

    def test_sin_tiempos_registrados_no_se_declara_paridad(self):
        datos = velas(1)
        resultado = comprobar_paridad_recepcion_1s(datos, {})
        self.assertIsNone(resultado["paridad"])
        self.assertEqual(resultado["motivo"], "LATENCIAS_INCOMPLETAS")

    def test_vela_abierta_se_rechaza(self):
        datos = velas(1)
        with self.assertRaisesRegex(ValueError, "VELA_AUN_ABIERTA"):
            evaluar_flujo([(0, datos[0])])


    def test_rechaza_tiempos_de_recepcion_no_enteros(self):
        dato = velas(1)[0]
        for recibido in (True, 1.5, "1", -1):
            with self.subTest(recibido=recibido):
                with self.assertRaisesRegex(ValueError, "RECEPCION_INVALIDA"):
                    evaluar_flujo([(recibido, dato)])

    def test_latencias_booleanas_y_fraccionarias_no_son_paridad_valida(self):
        datos = velas(1)
        for invalida in (True, False, 0.5, "0", -1):
            with self.subTest(latencia=invalida):
                latencias = {t: 0 for t in datos}
                latencias[10] = invalida
                resultado = comprobar_paridad_recepcion_1s(datos, latencias)
                self.assertIsNone(resultado["paridad"])
                self.assertEqual(resultado["motivo"], "LATENCIAS_INVALIDAS")


    def test_interrupcion_recupera_contexto_sin_reutilizar_pasado(self):
        datos = velas(53)
        # 25 minutos normales, luego minuto 25 perdido completamente.
        for t in range(25 * 60, 26 * 60):
            del datos[t]
        llegadas = [(t + 1, vela) for t, vela in datos.items()]
        flujo = evaluar_flujo(llegadas)
        por_fin = dict(flujo)
        self.assertNotIn(26 * 60, por_fin)
        self.assertEqual(por_fin[27 * 60]["contexto"]["estado"], "SIN_DATOS")
        # Diagnostico requiere 20 minutos nuevos; estrategia requiere 24.
        self.assertEqual(por_fin[45 * 60]["contexto"]["estado"], "SIN_DATOS")
        self.assertNotEqual(por_fin[46 * 60]["contexto"]["estado"], "SIN_DATOS")
        self.assertTrue(all(c["estado"] == "SIN_SENAL"
                            for c in por_fin[49 * 60]["candidatos"]))
        self.assertTrue(all(c["razon"] != "SIN_DATOS"
                            for c in por_fin[50 * 60]["candidatos"]))
        self.assertEqual([fin for fin, _ in flujo], sorted(por_fin))
        self.assertTrue(all(
            diagnostico["arbitraje"]["operable"] is False
            for _, diagnostico in flujo
        ))
        self.assertTrue(comprobar_paridad(datos, llegadas)["paridad"])

    def test_duplicados_no_reemiten_ni_reescriben_cierres(self):
        datos = velas(3)
        referencia = evaluar_flujo([(t + 1, v) for t, v in datos.items()])
        llegadas = [(t + 1, v) for t, v in datos.items()]
        llegadas.append((12, dict(datos[10])))
        llegadas.append((125, dict(datos[59])))
        llegadas.sort(key=lambda par: (par[0], par[1]["from"]))
        self.assertEqual(evaluar_flujo(llegadas), referencia)

    def test_retraso_intermedio_rechaza_minuto_y_reanuda(self):
        datos = velas(3)
        # Segunda 10 de minuto cero: llega cuando minuto cero ya cerro.
        llegadas = [
            (t + 1 + (80 if t == 10 else 0), v)
            for t, v in datos.items()
        ]
        llegadas.sort(key=lambda par: (par[0], par[1]["from"]))
        cierres = [fin for fin, _ in evaluar_flujo(llegadas)]
        self.assertEqual(cierres, [120, 180])
        self.assertFalse(comprobar_paridad(datos, llegadas)["paridad"])


if __name__ == "__main__":
    unittest.main()
