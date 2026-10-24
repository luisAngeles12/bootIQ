import unittest

from motor_decision import convertir_decision_v3_a_oficial


class Core4SelectiveDiagnosticTests(unittest.TestCase):
    @staticmethod
    def evaluar(**campos):
        evidencia = {
            "direccion": "CALL",
            "calidad_mercado": "NORMAL",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "modo_entrada_setup": "directa",
            **campos,
        }
        resultado = convertir_decision_v3_a_oficial(
            {
                "decision": "NO_OPERAR_SOMBRA",
                "motivo": "Prueba controlada",
                "muestra": 30,
                "confiabilidad": "ALTA",
            },
            evidencia,
        )
        return resultado, evidencia["_core4_diagnostico_previo"]

    def test_r2_solo_remains_rejected_and_identifies_cause(self):
        resultado, diagnostico = self.evaluar(
            pa_tipo="RECHAZO_COMPRADOR_CONFIRMADO",
        )
        self.assertEqual(resultado["decision"], "NO_OPERAR")
        self.assertIs(resultado["operar"], False)
        self.assertIs(diagnostico["core4_invalidacion_selectiva_previa"], True)
        self.assertEqual(diagnostico["core4_motivos_selectivos_previos"], "R2_SOLO")

    def test_multiple_causes_preserved_without_changing_rejection(self):
        resultado, diagnostico = self.evaluar(
            tipo_setup="INDEFINIDO",
            calidad_setup="PREMIUM",
            pa_tipo="RECHAZO_COMPRADOR_CONFIRMADO",
            nombre_patron_vela="ENVOLVENTE_ALCISTA",
            estado_tendencia="BAJISTA_DEBIL",
        )
        self.assertEqual(resultado["decision"], "NO_OPERAR")
        self.assertIs(resultado["operar"], False)
        self.assertEqual(
            diagnostico["core4_motivos_selectivos_previos"],
            "R1_R2_ENVOLVENTE|R1_R2_BAJISTA_DEBIL",
        )

    def test_no_invalidations_remains_eligible(self):
        resultado, diagnostico = self.evaluar(
            tipo_setup="INDEFINIDO",
            calidad_setup="PREMIUM",
        )
        self.assertEqual(resultado["decision"], "OPERAR")
        self.assertIs(resultado["operar"], True)
        self.assertIs(diagnostico["core4_invalidacion_selectiva_previa"], False)
        self.assertEqual(diagnostico["core4_motivos_selectivos_previos"], "")


if __name__ == "__main__":
    unittest.main()
