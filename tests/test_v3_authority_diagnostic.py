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


    def test_conserva_validaciones_estrategia_sin_inferir_valores_ausentes(self):
        from constructor_evidencia import construir_evidencia_operacion

        senal = {
            "activo": "AAA",
            "direccion": "put",
            "patron": "reaccion vendedora en resistencia",
            "validacion_zona_sr_ok": False,
            "validacion_ubicacion_ok": False,
            "razon_ubicacion": "fatiga detectada",
            "zona_operada": True,
            "razon_zona_operada": "zona repetida",
            "vela_contraria_reciente": True,
            "razon_vela_contraria": "vela fuerte contraria",
            "razon_ruptura": "sin ruptura",
            "razon_accion_precio": "soporte cercano",
        }
        evidencia = construir_evidencia_operacion(senal)
        for campo in (
            "validacion_zona_sr_ok",
            "validacion_ubicacion_ok",
            "razon_ubicacion",
            "zona_operada",
            "razon_zona_operada",
            "vela_contraria_reciente",
            "razon_vela_contraria",
            "razon_ruptura",
            "razon_accion_precio",
        ):
            with self.subTest(campo=campo):
                self.assertEqual(evidencia[campo], senal[campo])

        sin_datos = construir_evidencia_operacion({})
        self.assertIsNone(sin_datos["validacion_zona_sr_ok"])
        self.assertIsNone(sin_datos["zona_operada"])
        self.assertEqual(sin_datos["razon_ubicacion"], "")



if __name__ == "__main__":
    unittest.main()
