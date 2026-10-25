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


    def test_r1_solo_protocol_shadow_is_reported_eligible(self):
        evidencia = {
            "direccion": "CALL",
            "calidad_mercado": "NORMAL",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "modo_entrada_setup": "DIRECTA",
            "tipo_setup": "INDEFINIDO",
            "calidad_setup": "PREMIUM",
        }
        resultado = convertir_decision_v3_a_oficial(
            {
                "decision": "OPERAR_CON_PROTOCOLO_SOMBRA",
                "motivo": "Prueba R1 autonoma",
                "muestra": 30,
                "confiabilidad": "ALTA",
            },
            evidencia,
        )
        diagnostico = evidencia["_core4_diagnostico_previo"]
        self.assertIs(diagnostico["core4_elegible_estructural_previo"], True)
        self.assertIs(diagnostico["core4_elegible_rescate_previo"], True)
        self.assertIs(resultado["core4_rescate"], True)
        self.assertEqual(resultado["origen_autoridad"], "D6_6_CORE4_OOS")

    def test_r1_r6_combination_is_not_relabelled_eligible(self):
        evidencia = {
            "direccion": "PUT",
            "calidad_mercado": "NORMAL",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "modo_entrada_setup": "DIRECTA",
            "tipo_setup": "INDEFINIDO",
            "calidad_setup": "PREMIUM",
            "patron": "CONTINUACION BAJISTA CON TENDENCIA",
            "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
        }
        resultado = convertir_decision_v3_a_oficial(
            {
                "decision": "OPERAR_CON_PROTOCOLO_SOMBRA",
                "motivo": "Prueba R1 combinado",
                "muestra": 30,
                "confiabilidad": "ALTA",
            },
            evidencia,
        )
        diagnostico = evidencia["_core4_diagnostico_previo"]
        self.assertIs(diagnostico["core4_elegible_rescate_previo"], False)
        self.assertIs(resultado.get("core4_rescate", False), False)


    def test_r1_never_overrides_market_or_direct_entry_guards(self):
        escenarios = (
            ("MERCADO_SUCIO", {"calidad_mercado": "SUCIO"}),
            ("MERCADO_CAOTICO", {"calidad_mercado": "CAOTICO"}),
            ("ENTRADA_NO_DIRECTA", {"modo_entrada_setup": "PROTOCOLO"}),
            ("MEMORIA_VETA", {"memoria_permite": False}),
            ("ACTIVO_VETADO", {"activo_bloqueable_historico": True}),
        )
        for nombre, campos in escenarios:
            with self.subTest(escenario=nombre):
                resultado, diagnostico = self.evaluar(
                    tipo_setup="INDEFINIDO",
                    calidad_setup="PREMIUM",
                    **campos,
                )
                self.assertEqual(resultado["decision"], "NO_OPERAR")
                self.assertIs(resultado["operar"], False)
                self.assertIs(diagnostico["core4_elegible_rescate_previo"], False)
                self.assertIs(resultado.get("core4_rescate", False), False)



    def test_r1_r2_requiere_ruptura_y_no_se_convierte_en_directa(self):
        evidencia = {
            "direccion": "CALL",
            "calidad_mercado": "NORMAL",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "modo_entrada_setup": "DIRECTA",
            "tipo_setup": "INDEFINIDO",
            "calidad_setup": "PREMIUM",
            "pa_tipo": "RECHAZO_COMPRADOR_CONFIRMADO",
            "protocolo_sugerido": "PROTOCOLO_RUPTURA_RESISTENCIA",
        }
        resultado = convertir_decision_v3_a_oficial(
            {
                "decision": "NO_OPERAR_SOMBRA",
                "motivo": "caso R1+R2 con resistencia",
                "muestra": 30,
                "confiabilidad": "ALTA",
            },
            evidencia,
        )
        diag = evidencia["_core4_diagnostico_previo"]
        self.assertIs(diag["core4_elegible_rescate_previo"], True)
        self.assertIs(resultado["core4_rescate"], True)
        self.assertEqual(resultado["decision"], "OPERAR_CON_PROTOCOLO")
        self.assertIs(resultado["requiere_protocolo"], True)
        self.assertEqual(resultado["modo_ejecucion"], "PROTOCOLO")



if __name__ == "__main__":
    unittest.main()
