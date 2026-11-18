"""Integración F8: bootstrap PRACTICE conserva ausencia de estadística real.

Solo pruebas con Cerebro y constructor simulados; nunca compra ni conecta.
"""
import unittest
from unittest.mock import patch

import bootstrap_practice
from decision_bootiq import aplicar_decision_unificada_a_senal


def evidencia_valida():
    return {
        "calidad_mercado": "NORMAL",
        "direccion": "call",
        "validacion_mercado_ok": True,
        "validacion_zona_sr_ok": True,
        "validacion_accion_precio_ok": True,
        "accion_precio": "CALL_ZONA_NEUTRA",
        "riesgo_estructural_critico_setup": False,
        "requiere_confirmacion_setup": False,
        "requiere_ruptura_setup": False,
        "modo_entrada_setup": "DIRECTA",
        "prioridad": 3,
    }


def decision_sin_memoria():
    return {
        "decision": "NO_OPERAR",
        "operar": False,
        "confianza": 49.25,
        "requiere_protocolo": False,
        "modo_ejecucion": "BLOQUEADA",
        "bloquear_por_riesgo": False,
        "riesgo_compuesto": {"bloquear_por_riesgo": False},
        "resultado_decision_estadistica_sombra": {
            "decision": "SIN_DATOS_ESTADISTICOS",
        },
        "resultado_decision_oficial": {
            "motivo": "Sin fuente histórica principal utilizable."
        },
        "probabilidad_estimada": 49.25,
        "muestra_probabilidad": 0,
        "confiabilidad_probabilidad": "SIN_DATOS",
        "fuente_probabilidad_principal": None,
        "decision_estadistica_sombra": "SIN_DATOS_ESTADISTICOS",
        "operar_estadistico_sombra": False,
    }


class IntegracionBootstrapMemoriaFase8Tests(unittest.TestCase):
    def evaluar(self, evidencia):
        with patch("constructor_evidencia.construir_evidencia_operacion", return_value=evidencia), patch(
            "motor_decision.evaluar_decision_cerebro_unico", return_value=decision_sin_memoria()
        ) as cerebro:
            resultado = aplicar_decision_unificada_a_senal({"activo": "EURUSD"})
        cerebro.assert_called_once()
        return resultado

    def test_bootstrap_practice_no_convierte_prior_en_muestra(self):
        with patch.object(bootstrap_practice, "MODO_CUENTA", "PRACTICE"):
            r = self.evaluar(evidencia_valida())
        self.assertTrue(r["permitida"], r.get("razon"))
        self.assertEqual(r["senal"]["origen_autoridad"], "BOOTSTRAP_PRACTICE_SIN_HISTORIAL")
        self.assertTrue(r["senal"]["bootstrap_practice_sin_historial"])
        self.assertEqual(r["senal"]["muestra_probabilidad"], 0)
        self.assertEqual(r["senal"]["probabilidad_estimada"], 49.25)
        self.assertEqual(r["senal"]["decision_estadistica_sombra"], "SIN_DATOS_ESTADISTICOS")
        self.assertFalse(r["senal"]["operar_estadistico_sombra"])

    def test_put_a_soporte_sin_ruptura_permanece_rechazado_por_cerebro(self):
        datos = evidencia_valida()
        datos.update({
            "direccion": "put",
            "accion_precio": "PUT_SOPORTE_CERCA_SIN_RUPTURA",
        })
        with patch.object(bootstrap_practice, "MODO_CUENTA", "PRACTICE"):
            r = self.evaluar(datos)
        self.assertFalse(r["permitida"])
        self.assertEqual(r["senal"]["cerebro_unico_decision"], "NO_OPERAR")
        self.assertFalse(r["senal"].get("bootstrap_practice_sin_historial", False))
        # Caso de control: rechazo vendedor en resistencia no queda
        # bloqueado por esta condicion especifica.
        datos["accion_precio"] = "RECHAZO_VENDEDOR_RESISTENCIA"
        with patch.object(bootstrap_practice, "MODO_CUENTA", "PRACTICE"):
            control = self.evaluar(datos)
        self.assertTrue(control["permitida"])

    def test_sin_bootstrap_persiste_no_operar(self):
        datos = evidencia_valida()
        datos["validacion_mercado_ok"] = False
        with patch.object(bootstrap_practice, "MODO_CUENTA", "PRACTICE"):
            r = self.evaluar(datos)
        self.assertFalse(r["permitida"])
        self.assertEqual(r["senal"]["cerebro_unico_decision"], "NO_OPERAR")
        self.assertFalse(r["senal"].get("bootstrap_practice_sin_historial", False))

    def test_modo_real_no_aplica_excepcion(self):
        with patch.object(bootstrap_practice, "MODO_CUENTA", "REAL"):
            r = self.evaluar(evidencia_valida())
        self.assertFalse(r["permitida"])
        self.assertEqual(r["senal"]["cerebro_unico_decision"], "NO_OPERAR")
        self.assertFalse(r["senal"].get("bootstrap_practice_sin_historial", False))


if __name__ == "__main__":
    unittest.main()
