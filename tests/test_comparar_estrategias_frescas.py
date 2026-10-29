import unittest
from unittest.mock import patch

from comparar_estrategias_frescas import comparar_estrategias, resumen_comparativa


def velas_minutos(n=26):
    return {
        t: {"from": t, "open": 100, "close": 101,
            "min": 99, "max": 102,
            "_latencia_primera_recepcion_s": 0}
        for t in range(n * 60)
    }


def candidato():
    return [
        {"estrategia": "RUPTURA_RETEST", "estado": "CANDIDATO_SOMBRA",
         "direccion": "call"},
        {"estrategia": "RECHAZO_ZONA", "estado": "SIN_SENAL",
         "direccion": None},
        {"estrategia": "CONTINUACION_TENDENCIA", "estado": "SIN_SENAL",
         "direccion": None},
    ]


class CompararEstrategiasFrescasTests(unittest.TestCase):
    def test_sin_movimiento_ningun_candidato(self):
        r = resumen_comparativa(velas_minutos())
        self.assertEqual(set(r), {
            "RUPTURA_RETEST", "RECHAZO_ZONA", "CONTINUACION_TENDENCIA"})
        self.assertTrue(all(v["senales_no_solapadas"] == 0 for v in r.values()))

    @patch("comparar_estrategias_frescas.diagnosticar_estrategias",
           side_effect=lambda *_: candidato())
    @patch("comparar_estrategias_frescas.diagnosticar_contexto",
           return_value={"estado": "TENDENCIA_ALCISTA"})
    def test_no_solapa_por_estrategia_ni_inventa_ultima_salida(self, *_mocks):
        datos = velas_minutos(26)
        r = comparar_estrategias(datos)
        self.assertEqual(len(r["RUPTURA_RETEST"]), 2)
        self.assertEqual(r["RUPTURA_RETEST"][0]["resultado"], "WIN")
        self.assertEqual(r["RUPTURA_RETEST"][1]["resultado"], "SIN_FUTURO")
        self.assertEqual(len(r["RECHAZO_ZONA"]), 0)
        self.assertEqual(len(r["CONTINUACION_TENDENCIA"]), 0)

    @patch("comparar_estrategias_frescas.diagnosticar_estrategias",
           side_effect=lambda *_: candidato())
    @patch("comparar_estrategias_frescas.diagnosticar_contexto",
           return_value={"estado": "TENDENCIA_ALCISTA"})
    def test_latencia_desconocida_no_es_verificada(self, *_mocks):
        datos = velas_minutos(25)
        datos[23 * 60 + 59]["_latencia_primera_recepcion_s"] = None
        r = comparar_estrategias(datos)
        self.assertEqual(r["RUPTURA_RETEST"][0]["calidad_tiempo"],
                         "LATENCIA_NO_REGISTRADA")

    @patch("comparar_estrategias_frescas.diagnosticar_estrategias",
           side_effect=lambda *_: candidato())
    @patch("comparar_estrategias_frescas.diagnosticar_contexto",
           return_value={"estado": "TENDENCIA_ALCISTA"})
    def test_no_utiliza_el_cierre_conocido_como_precio_de_entrada(self, *_mocks):
        datos = velas_minutos(25)
        # Cierre de confirmacion 99, pero la primera apertura futura 110.
        # Resultado real del replay: 101 < 110 -> LOSS. Usar 99 seria WIN.
        datos[23 * 60 + 59]["close"] = 99
        datos[24 * 60]["open"] = 110
        datos[24 * 60]["max"] = 111
        r = comparar_estrategias(datos)
        primera = r["RUPTURA_RETEST"][0]
        self.assertEqual(primera["resultado"], "LOSS")
        self.assertEqual(primera["timestamp_entrada_hipotetica"], 24 * 60)
        self.assertEqual(primera["modelo_entrada"],
                         "APERTURA_PRIMERA_VELA_FUTURA_NO_EJECUTADA")

    @patch("comparar_estrategias_frescas.diagnosticar_estrategias",
           side_effect=lambda *_: candidato())
    @patch("comparar_estrategias_frescas.diagnosticar_contexto",
           return_value={"estado": "TENDENCIA_ALCISTA"})
    def test_un_segundo_de_demora_invalida_entrada_exacta(self, *_mocks):
        datos = velas_minutos(25)
        datos[23 * 60 + 59]["_latencia_primera_recepcion_s"] = 1
        r = comparar_estrategias(datos)
        self.assertEqual(r["RUPTURA_RETEST"][0]["calidad_tiempo"],
                         "DETECCION_TARDIA")

    def test_rechaza_horizonte_invalido(self):
        with self.assertRaisesRegex(ValueError, "HORIZONTE_INVALIDO"):
            comparar_estrategias({}, 0)

    @patch("comparar_estrategias_frescas.diagnosticar_estrategias",
           side_effect=lambda *_: candidato())
    @patch("comparar_estrategias_frescas.diagnosticar_contexto",
           return_value={"estado": "TENDENCIA_ALCISTA"})
    def test_horizonte_con_minuto_intermedio_ausente_no_cuenta_win(self, *_mocks):
        datos = velas_minutos(28)
        for t in range(25 * 60, 26 * 60):
            del datos[t]
        r = comparar_estrategias(datos, horizonte_minutos=3)
        self.assertEqual(r["RUPTURA_RETEST"][0]["resultado"], "SIN_FUTURO")


if __name__ == "__main__":
    unittest.main()
