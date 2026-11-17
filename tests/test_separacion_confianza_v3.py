"""Regresión de separación entre confianza V3 y ajustes diagnósticos.

Todas las dependencias externas se simulan: no requiere broker ni memoria.
"""
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import motor_decision as motor


class SeparacionConfianzaV3Tests(unittest.TestCase):
    def test_ajuste_price_action_no_cambia_confianza_ni_decision_oficial(self):
        legacy = {
            "resultado_inferencia": {},
            "ponderacion": {},
            "resultado_confianza": {},
            "resultado_decision": {"decision": "NO_OPERAR"},
            "confianza_base": 50,
            "confianza": 80,
            "ajuste_aprendizaje": 0,
            "ajuste_ponderacion": 0,
            "auditoria_confianza": {},
        }
        aprendizaje = {
            "probabilidad_estimada": 58.25,
            "intervalo_probabilidad_inferior": 52,
            "intervalo_probabilidad_superior": 64,
            "muestra_historica": 40,
            "confiabilidad_muestra": "ALTA",
        }
        oficial = {
            "decision": "NO_OPERAR",
            "operar": False,
            "requiere_protocolo": False,
            "modo_ejecucion": "BLOQUEADA",
            "bloquear_por_riesgo": False,
            "motivo": "PRUEBA_AISLADA",
        }

        for ajuste_pa in (-30, 0, 30):
            with self.subTest(ajuste_pa=ajuste_pa), ExitStack() as pila:
                simulaciones = {
                    "evaluar_riesgo_compuesto": {"riesgo_nivel": "BAJO", "riesgo_puntos": 0},
                    "evaluar_veto_tecnico_sombra": {},
                    "evaluar_aprendizaje_historico": aprendizaje,
                    "evaluar_price_action_decision": {"ajuste": ajuste_pa, "motivos": []},
                    "evaluar_mercado_decision": {"ajuste": 0, "motivos": []},
                    "evaluar_estrategia_decision": {"ajuste": 0, "motivos": []},
                    "_evaluar_legacy_opcional": legacy,
                    "clasificar_decision_estadistica_oficial": {"decision": "NO_OPERAR_SOMBRA"},
                    "convertir_decision_v3_a_oficial": oficial,
                    "construir_auditoria_separacion_v3": {},
                }
                for nombre, respuesta in simulaciones.items():
                    pila.enter_context(patch.object(motor, nombre, return_value=respuesta))
                pila.enter_context(patch.object(motor, "AUDITORIA_LEGACY_ACTIVA", False))
                resultado = motor.evaluar_decision_cerebro_unico({"direccion": "call"})

                self.assertEqual(resultado["confianza"], 58.25)
                self.assertEqual(resultado["confianza_legacy"], 80)
                self.assertEqual(resultado["ajuste_evidencias"], float(ajuste_pa))
                self.assertEqual(resultado["decision"], "NO_OPERAR")
                self.assertFalse(resultado["operar"])
                self.assertEqual(resultado["probabilidad_v3"], 58.25)
                self.assertTrue(resultado["sistemas_decision_separados"])


if __name__ == "__main__":
    unittest.main()
