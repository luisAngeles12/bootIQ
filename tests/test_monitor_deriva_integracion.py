"""Contrato de transporte de cooldown; nunca implica veto operativo."""
import unittest

from constructor_evidencia import construir_evidencia_operacion
from motor_decision import evaluar_veto_tecnico_sombra


class CooldownIntegracionTest(unittest.TestCase):
    def test_cooldown_llega_como_evidencia(self):
        evidencia = construir_evidencia_operacion(
            {"patron": "CHOCH alcista", "estrategia_en_cooldown": True},
            {},
        )
        self.assertIs(evidencia["estrategia_en_cooldown"], True)

    def test_sin_cooldown_no_inventa_evidencia(self):
        evidencia = construir_evidencia_operacion({"patron": "CHOCH"}, {})
        self.assertIs(evidencia["estrategia_en_cooldown"], False)

    def test_diagnostico_cooldown_solo_sombra(self):
        r = evaluar_veto_tecnico_sombra({
            "estrategia_en_cooldown": True,
            "riesgos_base": "",
        })
        self.assertIn("ESTRATEGIA_EN_COOLDOWN", r["vetos_tecnicos_sombra"])
        self.assertEqual(r["modo_veto_tecnico"], "DIAGNOSTICO")


if __name__ == "__main__":
    unittest.main()
