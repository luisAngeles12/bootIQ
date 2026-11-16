"""Contrato de indicadores tecnicos: transporte causal sin veto ni bonos."""
import unittest

from constructor_evidencia import construir_evidencia_operacion


class TransporteIndicadoresTest(unittest.TestCase):
    def test_valores_senal_prioritarios(self):
        contexto = {
            "ema9": 20, "ema21": 19,
            "bb_superior": 25, "bb_media": 20, "bb_inferior": 15,
        }
        senal = {
            "patron": "CHOCH alcista",
            "ema9": 101.1, "ema21": 100.5,
            "bb_superior": 102.0, "bb_media": 100.0, "bb_inferior": 98.0,
        }
        evidencia = construir_evidencia_operacion(senal, contexto)
        self.assertEqual(evidencia["indicadores_tecnicos"], {
            "ema9": 101.1, "ema21": 100.5,
            "bb_superior": 102.0, "bb_media": 100.0, "bb_inferior": 98.0,
        })
        self.assertNotIn("ajuste_indicadores", evidencia)

    def test_contexto_es_respaldo_no_recalculo(self):
        evidencia = construir_evidencia_operacion({}, {
            "ema9": 10, "ema21": 9, "bb_media": 9.5,
        })
        self.assertEqual(evidencia["indicadores_tecnicos"]["ema9"], 10)
        self.assertEqual(evidencia["indicadores_tecnicos"]["bb_media"], 9.5)
        self.assertIsNone(evidencia["indicadores_tecnicos"]["bb_inferior"])

    def test_ausentes_o_no_finitos_no_son_precios_cero(self):
        evidencia = construir_evidencia_operacion({
            "ema9": None, "ema21": "NaN",
            "bb_superior": float("inf"), "bb_media": "",
            "bb_inferior": False,
        })
        self.assertTrue(all(
            valor is None for valor in evidencia["indicadores_tecnicos"].values()
        ))

    def test_evidencia_no_propaga_nan_o_infinito_a_ponderaciones(self):
        senal = {
            "pa_evidencias": [{
                "tipo": "rechazo",
                "direccion": "CALL",
                "peso": float("nan"),
                "confianza": float("inf"),
                "fuerza": float("-inf"),
                "confirmada": True,
            }],
        }
        e = construir_evidencia_operacion(senal, {})
        pa = e["pa_evidencias"][0]
        self.assertEqual(pa["peso"], 0)
        self.assertEqual(pa["confianza"], 50)
        self.assertEqual(pa["fuerza"], 0)
        self.assertTrue(pa["confirmada"])

    def test_confirmacion_textual_false_no_se_convierte_en_true(self):
        senal = {
            "pa_evidencias": [{
                "tipo": "rechazo", "direccion": "CALL",
                "peso": 5, "confirmada": "False",
            }],
            "estrategia_evidencias": [{
                "tipo": "patron", "confirmada": "true",
            }],
        }
        e = construir_evidencia_operacion(senal, {})
        self.assertFalse(e["pa_evidencias"][0]["confirmada"])
        self.assertTrue(e["estrategia_evidencias"][0]["confirmada"])

    def test_confirmacion_invalida_no_equivale_a_confirmada(self):
        e = construir_evidencia_operacion({
            "pa_evidencias": [{
                "tipo": "impulso", "confirmada": "no",
            }],
        }, {})
        self.assertFalse(e["pa_evidencias"][0]["confirmada"])

    def test_evidencia_tecnica_no_reescribe_decision(self):
        senal = {
            "cerebro_unico_decision": "OPERAR_CON_PROTOCOLO",
            "puntaje": 9,
            "ema9": 10, "ema21": 11,
        }
        copia = dict(senal)
        evidencia = construir_evidencia_operacion(senal, {})
        self.assertEqual(senal, copia)
        self.assertNotIn("decision", evidencia["indicadores_tecnicos"])
        self.assertEqual(evidencia["indicadores_tecnicos"]["ema9"], 10)


if __name__ == "__main__":
    unittest.main()
