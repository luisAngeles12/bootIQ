"""Evaluacion causal del arbitro de BootIQ, sin broker ni ordenes."""
import unittest
from unittest.mock import patch

from evaluar_arbitro_fresco import evaluar_arbitro


def datos(n=26):
    return {
        t: {"from": t, "open": 100, "close": 101,
            "min": 99, "max": 102,
            "_latencia_primera_recepcion_s": 0}
        for t in range(n * 60)
    }


def diagnostico(motivo="UNA_ESTRATEGIA", direccion="call"):
    confirmado = motivo == "UNA_ESTRATEGIA"
    return {
        "arbitraje": {
            "estado": ("CANDIDATO_SOMBRA_NO_OPERABLE" if confirmado
                       else "NO_OPERAR"),
            "direccion": direccion if confirmado else None,
            "estrategias": ["RECHAZO_ZONA"] if confirmado else [],
            "motivo": motivo,
            "operable": False,
        }
    }


class EvaluarArbitroFrescoTests(unittest.TestCase):
    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_resultados_solo_de_decisiones_del_arbitro(self, fn):
        fn.return_value = diagnostico()
        r = evaluar_arbitro(datos())
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]["resultado"], "WIN")
        self.assertEqual(r[1]["resultado"], "SIN_FUTURO")
        self.assertEqual(r[0]["estrategias_que_coinciden"], ["RECHAZO_ZONA"])
        self.assertFalse(r[0]["operable"])

    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_no_cuenta_estrategias_bloqueadas_por_conflicto(self, fn):
        fn.return_value = diagnostico("CONFLICTO_DE_DIRECCIONES")
        self.assertEqual(evaluar_arbitro(datos()), [])

    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_cierre_de_senal_no_se_usa_como_precio_de_entrada(self, fn):
        fn.return_value = diagnostico()
        velas = datos(25)
        velas[23 * 60 + 59]["close"] = 99
        velas[24 * 60]["open"] = 110
        velas[24 * 60]["max"] = 111
        r = evaluar_arbitro(velas)
        self.assertEqual(r[0]["resultado"], "LOSS")
        self.assertEqual(r[0]["timestamp_entrada_hipotetica"], 24 * 60)

    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_senal_tardia_no_es_verificada(self, fn):
        fn.return_value = diagnostico()
        velas = datos(25)
        velas[23 * 60 + 59]["_latencia_primera_recepcion_s"] = 1
        r = evaluar_arbitro(velas)
        self.assertEqual(r[0]["calidad_tiempo"], "DETECCION_TARDIA")

    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_arbitro_no_puede_autorizar_orden_real(self, fn):
        fn.return_value = diagnostico()
        fn.return_value["arbitraje"]["operable"] = True
        with self.assertRaisesRegex(RuntimeError, "ARBITRO_AUTORIZO_OPERACION"):
            evaluar_arbitro(datos())

    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_horizonte_con_minuto_intermedio_ausente_no_cuenta_win(self, fn):
        fn.return_value = diagnostico()
        velas = datos(28)
        # Horizonte 3m: falta minuto 25, aunque minuto 26 existe.
        for t in range(25 * 60, 26 * 60):
            del velas[t]
        r = evaluar_arbitro(velas, horizonte_minutos=3)
        self.assertEqual(r[0]["resultado"], "SIN_FUTURO")

    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_latencias_invalidas_no_son_verificadas(self, fn):
        fn.return_value = diagnostico()
        for demora in (-1, False, 0.5, "0"):
            with self.subTest(demora=demora):
                velas = datos(25)
                velas[23 * 60 + 59]["_latencia_primera_recepcion_s"] = demora
                evento = evaluar_arbitro(velas)[0]
                self.assertEqual(evento["calidad_tiempo"],
                                 "LATENCIA_INVALIDA_O_NO_REGISTRADA")


    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_vela_intermedia_tardia_invalida_senal_del_minuto(self, fn):
        fn.return_value = diagnostico()
        velas = datos(25)
        # Vela 10 se recibe despues del cierre, aunque la 59 llegue a tiempo.
        velas[23 * 60 + 10]["_latencia_primera_recepcion_s"] = 70
        evento = evaluar_arbitro(velas)[0]
        self.assertEqual(evento["calidad_tiempo"], "DETECCION_TARDIA")
        self.assertNotEqual(evento["calidad_tiempo"], "TIEMPO_VERIFICADO")

    @patch("evaluar_arbitro_fresco.diagnosticar_cierre")
    def test_vela_intermedia_demorada_pero_antes_del_cierre_valida(self, fn):
        fn.return_value = diagnostico()
        velas = datos(25)
        velas[23 * 60 + 10]["_latencia_primera_recepcion_s"] = 2
        self.assertEqual(evaluar_arbitro(velas)[0]["calidad_tiempo"],
                         "TIEMPO_VERIFICADO")


if __name__ == "__main__":
    unittest.main()
