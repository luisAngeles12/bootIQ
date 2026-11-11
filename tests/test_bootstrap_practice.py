"""Pruebas de permiso bootstrap PRACTICE (sin ordenes ni red)."""
import unittest
from unittest.mock import Mock, patch

import bootstrap_practice as b


def decision_sin_datos():
    return {
        "decision": "NO_OPERAR",
        "bloquear_por_riesgo": False,
        "resultado_decision_estadistica_sombra": {
            "decision": "SIN_DATOS_ESTADISTICOS",
        },
        "resultado_decision_oficial": {
            "motivo": "V3 estadistico no autorizo operacion. Sin fuente histórica principal utilizable."
        },
    }


def evidencia():
    return {
        "calidad_mercado": "NORMAL",
        "validacion_mercado_ok": True,
        "riesgo_estructural_critico_setup": False,
        "requiere_confirmacion_setup": False,
        "requiere_ruptura_setup": False,
        "modo_entrada_setup": "DIRECTA",
        "prioridad": 3,
    }


class BootstrapPracticeTest(unittest.TestCase):
    def test_autoriza_solo_si_es_unicamente_falta_de_memoria(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            self.assertTrue(b.habilitable_sin_memoria(evidencia(), decision_sin_datos()))

    def test_no_puede_usarse_en_real(self):
        with patch.object(b, "MODO_CUENTA", "REAL"):
            self.assertFalse(b.habilitable_sin_memoria(evidencia(), decision_sin_datos()))
            self.assertFalse(b.cuenta_practice_verificada(Mock()))

    def test_rechazos_tecnicos_siguen_bloqueados(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            for cambio in (
                {"calidad_mercado": "SUCIO"},
                {"calidad_mercado": "CAOTICO"},
                {"validacion_mercado_ok": False},
                {"riesgo_estructural_critico_setup": True},
                {"requiere_confirmacion_setup": True},
                {"requiere_ruptura_setup": True},
                {"modo_entrada_setup": "PROTOCOLO"},
                {"prioridad": 1},
            ):
                with self.subTest(cambio=cambio):
                    datos = evidencia()
                    datos.update(cambio)
                    self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))

    def test_otros_motivos_no_se_saltan(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            for cambio in (
                {"bloquear_por_riesgo": True},
                {"riesgo_compuesto": {"bloquear_por_riesgo": True, "riesgo_nivel": "ALTO"}},
                {"riesgo_compuesto": {"bloquear_por_riesgo": True, "riesgo_nivel": "EXTREMO"}},
                {"decision": "ERROR"},
                {"resultado_decision_estadistica_sombra": {"decision": "NO_OPERAR_SOMBRA"}},
                {"resultado_decision_oficial": {"motivo": "riesgo tecnico"}},
            ):
                with self.subTest(cambio=cambio):
                    decision = decision_sin_datos()
                    decision.update(cambio)
                    self.assertFalse(b.habilitable_sin_memoria(evidencia(), decision))

    def test_bootstrap_no_puede_saltarse_veto_estructural(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            for nivel in ("ALTO", "EXTREMO"):
                with self.subTest(nivel=nivel):
                    decision = decision_sin_datos()
                    decision["riesgo_compuesto"] = {
                        "bloquear_por_riesgo": True,
                        "riesgo_nivel": nivel,
                    }
                    # El V3 oficial no propaga el veto estructural.
                    self.assertFalse(decision["bloquear_por_riesgo"])
                    self.assertFalse(b.habilitable_sin_memoria(evidencia(), decision))

    def test_validacion_cuenta_justo_antes_de_compra(self):
        iq = Mock()
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            iq.get_balance_mode.return_value = "PRACTICE"
            self.assertTrue(b.cuenta_practice_verificada(iq))
            iq.get_balance_mode.return_value = "REAL"
            self.assertFalse(b.cuenta_practice_verificada(iq))
            iq.get_balance_mode.side_effect = RuntimeError("offline")
            self.assertFalse(b.cuenta_practice_verificada(iq))


if __name__ == "__main__":
    unittest.main()
