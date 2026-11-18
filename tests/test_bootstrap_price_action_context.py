"""Regresion: riesgo PA exige pendiente y cruza transporte de evidencia.

Solo usa velas sinteticas y stubs. No se conecta al broker.
"""
import unittest
from unittest.mock import patch

import bootstrap_practice as b
import price_action as pa
from constructor_evidencia import construir_evidencia_operacion


def velas(cierre):
    # Velas validas sin falsas rupturas, rechazos ni patrones adicionales.
    return [cierre] * 6, [cierre] * 6, [cierre + 0.2] * 6, [cierre - 0.2] * 6


def decision_sin_estadistica():
    return {
        "decision": "NO_OPERAR", "bloquear_por_riesgo": False,
        "resultado_decision_estadistica_sombra": {
            "decision": "SIN_DATOS_ESTADISTICOS"
        },
        "resultado_decision_oficial": {
            "motivo": "Sin fuente histórica principal utilizable."
        },
    }


def senal_con_zona(direccion, diagnostico):
    return {
        "activo": "TEST-OTC", "direccion": direccion,
        "patron": "CHOCH bajista" if direccion == "put" else "CHOCH alcista",
        "calidad_mercado": "NORMAL", "validacion_mercado_ok": True,
        "validacion_zona_sr_ok": True,
        "validacion_accion_precio_ok": diagnostico["permite"],
        "accion_precio": diagnostico["accion"],
        "accion_precio_requiere_pendiente": diagnostico.get("requiere_pendiente") is True,
        "modo_entrada_setup": "DIRECTA", "prioridad": 3,
        "riesgo_estructural_critico_setup": False,
        "requiere_confirmacion_setup": False,
        "requiere_ruptura_setup": False,
        "mercado_evidencias": [],
    }


class DetectorContratoZonaTest(unittest.TestCase):
    def probar_conflicto(self, direccion, soporte, resistencia, esperado):
        o, c, h, l = velas(100)
        with patch.object(pa, "lectura_avanzada_price_action",
                          return_value={"tipo": "MERCADO_MIXTO", "direccion": "NEUTRA"}):
            d = pa.diagnostico_accion_precio_zona(
                direccion, o, c, h, l, soporte, resistencia, 1.0
            )
        self.assertEqual(d["accion"], esperado)
        self.assertTrue(d["requiere_pendiente"])
        evidencia = construir_evidencia_operacion(senal_con_zona(direccion, d))
        self.assertTrue(evidencia["accion_precio_requiere_pendiente"])
        self.assertTrue(evidencia["validacion_zona_sr_ok"])
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            self.assertFalse(b.habilitable_sin_memoria(
                evidencia, decision_sin_estadistica()
            ))

    def test_put_cerca_soporte(self):
        self.probar_conflicto("put", 99.8, 105,
                             "PUT_SOPORTE_CERCA_SIN_RUPTURA")

    def test_call_cerca_resistencia(self):
        self.probar_conflicto("call", 95, 100.2,
                             "CALL_RESISTENCIA_CERCA_SIN_RUPTURA")

    def test_no_autoriza_zona_sr_invalidada_antes_de_cerebro(self):
        o, c, h, l = velas(100)
        with patch.object(pa, "lectura_avanzada_price_action",
                          return_value={"tipo": "MERCADO_MIXTO", "direccion": "NEUTRA"}):
            d = pa.diagnostico_accion_precio_zona(
                "call", o, c, h, l, 95, 105, 1.0
            )
        self.assertEqual(d["accion"], "CALL_ZONA_NEUTRA")
        senal = senal_con_zona("call", d)
        senal["validacion_zona_sr_ok"] = False
        evidencia = construir_evidencia_operacion(senal)
        self.assertFalse(evidencia["validacion_zona_sr_ok"])
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            self.assertFalse(b.habilitable_sin_memoria(
                evidencia, decision_sin_estadistica()
            ))

    def test_neutral_confirmada_no_esta_bloqueada_por_nuevo_contrato(self):
        o, c, h, l = velas(100)
        with patch.object(pa, "lectura_avanzada_price_action",
                          return_value={"tipo": "MERCADO_MIXTO", "direccion": "NEUTRA"}):
            d = pa.diagnostico_accion_precio_zona(
                "call", o, c, h, l, 95, 105, 1.0
            )
        evidencia = construir_evidencia_operacion(senal_con_zona("call", d))
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            self.assertTrue(b.habilitable_sin_memoria(
                evidencia, decision_sin_estadistica()
            ))


if __name__ == "__main__":
    unittest.main()
