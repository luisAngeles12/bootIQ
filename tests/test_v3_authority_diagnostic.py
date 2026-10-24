import unittest

from motor_decision import convertir_decision_v3_a_oficial


class V3AuthorityDiagnosticTests(unittest.TestCase):
    @staticmethod
    def evaluar(decision):
        return convertir_decision_v3_a_oficial(
            {
                "decision": decision,
                "motivo": "Prueba controlada",
                "nivel": "CONTEXTO_SETUP",
                "clave": "TEST_AUTORIDAD",
                "muestra": 30,
                "confiabilidad": "ALTA",
            },
            {"patron": "continuacion alcista con tendencia", "direccion": "CALL"},
        )

    def test_favorable_shadow_does_not_enable_generic_authority(self):
        for decision in ("OPERAR_SOMBRA", "OPERAR_CON_PROTOCOLO_SOMBRA"):
            with self.subTest(decision=decision):
                resultado = self.evaluar(decision)
                self.assertEqual(resultado["decision"], "NO_OPERAR")
                self.assertIs(resultado["operar"], False)
                self.assertIn(
                    "V3_SOMBRA_FAVORABLE_SIN_AUTORIDAD_GENERICA",
                    resultado["motivo"],
                )

    def test_unfavorable_shadow_keeps_statistical_rejection(self):
        resultado = self.evaluar("NO_OPERAR_SOMBRA")
        self.assertEqual(resultado["decision"], "NO_OPERAR")
        self.assertIs(resultado["operar"], False)
        self.assertNotIn(
            "V3_SOMBRA_FAVORABLE_SIN_AUTORIDAD_GENERICA",
            resultado["motivo"],
        )


if __name__ == "__main__":
    unittest.main()
