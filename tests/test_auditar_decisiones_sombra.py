"""Escenarios integrales de seguridad del cerebro de BootIQ en sombra."""
import unittest
from unittest.mock import patch

from auditar_decisiones_sombra import resumir_decisiones_sombra
from observador_minuto_sombra import ObservadorMinutoSombra
from paridad_sombra_practice import diagnosticar_cierre


def barras():
    return [
        {"from": i * 60, "end": (i + 1) * 60,
         "open": 100 + i * .1, "high": 100.2 + i * .1,
         "low": 99.9 + i * .1, "close": 100.1 + i * .1}
        for i in range(25)
    ]


class AuditoriaCerebroSombraTests(unittest.TestCase):
    def test_todo_el_cerebro_no_autoriza_operaciones(self):
        salida = diagnosticar_cierre(barras())
        resumen = resumir_decisiones_sombra([(1500, salida)])
        self.assertEqual(resumen["minutos_evaluados"], 1)
        self.assertEqual(resumen["operaciones"], 0)
        self.assertFalse(resumen["operaciones_autorizadas"])

    def test_contexto_caotico_bloquea_candidato(self):
        falsos = [
            {"estrategia": nombre, "estado": "CANDIDATO_SOMBRA",
             "direccion": "call", "operable": False}
            for nombre in (
                "RUPTURA_RETEST", "RECHAZO_ZONA", "CONTINUACION_TENDENCIA")
        ]
        with patch("paridad_sombra_practice.diagnosticar_contexto",
                   return_value={"estado": "CAOTICO", "operable": False}), \
             patch("paridad_sombra_practice.diagnosticar_estrategias",
                   return_value=falsos):
            salida = diagnosticar_cierre(barras())
        self.assertEqual(salida["arbitraje"]["estado"], "NO_OPERAR")
        resumen = resumir_decisiones_sombra([(1500, salida)])
        self.assertEqual(resumen["contextos"]["CAOTICO"], 1)
        self.assertEqual(resumen["operaciones"], 0)

    def test_rechaza_autorizacion_en_cualquier_etapa(self):
        diagnostico = diagnosticar_cierre(barras())
        diagnostico["candidatos"][0]["operable"] = True
        with self.assertRaisesRegex(RuntimeError, "ESTRATEGIA_OPERABLE_INESPERADA"):
            resumir_decisiones_sombra([(1500, diagnostico)])

    def test_rechaza_cierres_duplicados(self):
        diagnostico = diagnosticar_cierre(barras())
        with self.assertRaisesRegex(ValueError, "CIERRE_DUPLICADO"):
            resumir_decisiones_sombra([(1500, diagnostico), (1500, diagnostico)])

    def test_minuto_incompleto_no_produce_decision(self):
        observador = ObservadorMinutoSombra()
        salida = []
        for t in range(60):
            if t == 12:
                continue
            precio = 100 + t * .001
            salida.extend(observador.registrar({
                "from": t, "open": precio, "close": precio,
                "min": precio, "max": precio,
            }, t + 1))
        self.assertEqual(salida, [])
        self.assertEqual(resumir_decisiones_sombra(salida)["operaciones"], 0)


if __name__ == "__main__":
    unittest.main()
