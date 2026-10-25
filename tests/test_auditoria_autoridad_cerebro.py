import unittest

from auditoria_autoridad_cerebro import resumir_autoridad


class AuditoriaAutoridadCerebroTests(unittest.TestCase):
    def test_vetos_superpuestos_y_riesgo_bajo_sin_autorizar(self):
        filas = [{
            "estado_operacion": "CANCELADA_CEREBRO",
            "cerebro_unico_decision": "NO_OPERAR",
            "cerebro_unico_riesgo": "BAJO",
            "resultado_hipotetico": "WIN",
            "decision_sombra_origen": "OPERAR_SOMBRA",
            "core4_match_previo": "True",
            "core4_invalidacion_dura_previa": "True",
            "core4_invalidacion_selectiva_previa": "True",
            "core4_motivos_selectivos_previos": "R2_SOLO|R6_SOLO|R2_SOLO",
            "core4_rescate": "False",
        }]
        conteos, resultados = resumir_autoridad(filas)
        self.assertEqual(conteos["total"], 1)
        self.assertEqual(conteos["canceladas_riesgo_BAJO"], 1)
        self.assertEqual(conteos["core4_invalidacion_dura"], 1)
        self.assertEqual(conteos["core4_invalidacion_selectiva"], 1)
        self.assertEqual(conteos["core4_match_invalidado"], 1)
        self.assertEqual(conteos["veto_selectivo_R2_SOLO"], 1)
        self.assertEqual(conteos["sombra_favorable_rechazada"], 1)
        self.assertEqual(conteos.get("core4_rescate", 0), 0)
        self.assertEqual(resultados[("BAJO", "WIN")], 1)

    def test_particion_core4_sin_match_invalidado_y_elegible_cancelado(self):
        filas = [
            {"estado_operacion": "CANCELADA_CEREBRO", "core4_match_previo": False},
            {"estado_operacion": "CANCELADA_CEREBRO", "core4_match_previo": True,
             "core4_invalidacion_selectiva_previa": True},
            {"estado_operacion": "CANCELADA_CEREBRO", "core4_match_previo": True,
             "core4_elegible_estructural_previo": True,
             "core4_elegible_rescate_previo": True},
            {"estado_operacion": "CANCELADA_CEREBRO", "core4_match_previo": True,
             "core4_elegible_estructural_previo": True,
             "core4_elegible_rescate_previo": False},
        ]
        conteos, _ = resumir_autoridad(filas)
        self.assertEqual(conteos["core4_sin_match"], 1)
        self.assertEqual(conteos["core4_match_invalidado"], 1)
        self.assertEqual(conteos["core4_match_elegible"], 1)
        self.assertEqual(conteos["core4_elegible_cancelada"], 1)
        self.assertEqual(conteos["core4_estructural_sin_selector_v3"], 1)
        self.assertEqual(
            sum(conteos.get(clave, 0) for clave in (
                "core4_sin_match",
                "core4_match_invalidado",
                "core4_match_elegible",
                "core4_estructural_sin_selector_v3",
                "core4_match_no_elegible_sin_veto",
            )),
            conteos["total"],
        )

    def test_no_inventa_resultado_hipotetico_ni_clasifica_operada_cancelada(self):
        filas = [{"estado_operacion": "OPERADA_DIRECTA", "resultado": "WIN", "core4_rescate": True},
                 {"estado_operacion": "CANCELADA_CEREBRO", "resultado": "WIN", "resultado_hipotetico": ""}]
        conteos, resultados = resumir_autoridad(filas)
        self.assertEqual(conteos["no_canceladas"], 1)
        self.assertEqual(conteos["canceladas"], 1)
        self.assertEqual(conteos["core4_rescate"], 1)
        self.assertEqual(resultados, {})


if __name__ == "__main__":
    unittest.main()
