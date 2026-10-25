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



    def test_campos_pasivos_no_cambian_autorizacion_core4(self):
        from constructor_evidencia import construir_evidencia_operacion

        senal = {
            "activo": "AAA",
            "direccion": "call",
            "patron": "reaccion compradora en soporte",
            "tipo_setup": "INDEFINIDO",
            "calidad_setup": "PREMIUM",
            "modo_entrada_setup": "DIRECTA",
            "calidad_mercado": "NORMAL",
            "tipo_mercado": "TENDENCIA_ALCISTA",
        }
        extras = {
            "validacion_zona_sr_ok": True,
            "validacion_ubicacion_ok": True,
            "zona_operada": False,
            "vela_contraria_reciente": False,
            "razon_ruptura": "sin ruptura",
            "razon_accion_precio": "zona sin conflicto",
        }
        sombra = {
            "decision": "NO_OPERAR_SOMBRA",
            "motivo": "prueba comparativa",
            "muestra": 30,
            "confiabilidad": "ALTA",
        }
        origen = construir_evidencia_operacion(senal)
        enriquecida = construir_evidencia_operacion({**senal, **extras})
        a = convertir_decision_v3_a_oficial(sombra, origen)
        b = convertir_decision_v3_a_oficial(sombra, enriquecida)
        for clave in ("decision", "operar", "requiere_protocolo",
                      "modo_ejecucion", "core4_rescate", "origen_autoridad"):
            with self.subTest(clave=clave):
                self.assertEqual(a.get(clave), b.get(clave))



if __name__ == "__main__":
    unittest.main()
