"""Pruebas para hipotesis de filtros sombra, sin ejecucion de broker."""
import json
import unittest

from comparar_filtros_sombra_fase5_practice import evaluar_filtros_sombra


def fila(i, dia, pnl, direccion="CALL", pa="CALL", riesgo="BAJO"):
    return {
        "estado": "CERRADA",
        "order_id": str(i),
        "fecha": f"{dia}T12:{i % 60:02d}:00",
        "resultado": str(pnl),
        "direccion": direccion,
        "pa_direccion": pa,
        "auditoria_riesgo_compuesto_json": json.dumps({"riesgo_nivel": riesgo}),
        "patron": "CHOCH",
    }


class CompararFiltrosSombraTests(unittest.TestCase):
    def test_pa_contraria_se_excluye_solo_de_filtros_de_pa(self):
        filas = [
            fila(1, "2026-11-10", 20.75, pa="CALL"),
            fila(2, "2026-11-11", -25, pa="PUT"),
            fila(3, "2026-11-11", 20.75, pa="NEUTRA"),
        ]
        r = evaluar_filtros_sombra(filas, minimo_validacion=1)
        grupos = {x["hipotesis"]: x for x in r["hipotesis_predefinidas"]}
        self.assertEqual(grupos["BASELINE_TODAS"]["total"]["n"], 3)
        self.assertEqual(grupos["PA_ALINEADA"]["total"]["n"], 1)
        self.assertEqual(grupos["PA_NO_CONTRARIA_CONOCIDA"]["total"]["n"], 2)
        self.assertFalse(r["cambios_operativos_autorizados"])

    def test_riesgo_ausente_no_equivale_a_bajo(self):
        datos = [fila(1, "2026-11-10", 20.75),
                 fila(2, "2026-11-11", -25)]
        datos[1]["auditoria_riesgo_compuesto_json"] = ""
        r = evaluar_filtros_sombra(datos)
        grupos = {x["hipotesis"]: x for x in r["hipotesis_predefinidas"]}
        self.assertEqual(grupos["RIESGO_BAJO_CONOCIDO"]["total"]["n"], 1)

    def test_cobertura_riesgo_expone_ausentes_por_fecha(self):
        datos = [fila(1, "2026-11-10", 20.75),
                 fila(2, "2026-11-11", -25)]
        datos[0]["auditoria_riesgo_compuesto_json"] = ""
        r = evaluar_filtros_sombra(datos)
        cobertura = r["cobertura_riesgo"]
        self.assertEqual(cobertura["total_evaluables"], 2)
        self.assertEqual(cobertura["sin_snapshot_riesgo"], 1)
        self.assertEqual(cobertura["con_snapshot_riesgo"], 1)
        self.assertEqual(cobertura["por_dia"]["2026-11-10"]["sin_snapshot_riesgo"], 1)
        self.assertEqual(cobertura["por_dia"]["2026-11-11"]["con_snapshot_riesgo"], 1)
        self.assertFalse(r["cambios_operativos_autorizados"])

    def test_no_confunde_menos_de_20_con_constancia(self):
        rows = [fila(i, "2026-11-10", 20.75) for i in range(10)] + [
            fila(i + 20, "2026-11-11", 20.75) for i in range(10)]
        r = evaluar_filtros_sombra(rows)
        baseline = r["hipotesis_predefinidas"][0]
        self.assertEqual(baseline["ventanas_20_ultimo_dia"], 0)
        self.assertFalse(baseline["evaluacion_con_muestra_suficiente"])

    def test_compara_retencion_y_neto_en_ultimo_dia(self):
        rows = [
            fila(i, "2026-11-10", 20.75) for i in range(20)
        ] + [
            fila(i + 20, "2026-11-11", 20.75 if i < 12 else -25,
                 pa="CALL" if i < 12 else "PUT")
            for i in range(20)
        ]
        r = evaluar_filtros_sombra(rows)
        grupos = {x["hipotesis"]: x for x in r["hipotesis_predefinidas"]}
        base = grupos["BASELINE_TODAS"]
        alineada = grupos["PA_ALINEADA"]
        self.assertEqual(base["ultimo_dia_no_usado_para_ajustar_regla"]["n"], 20)
        self.assertEqual(base["ventanas_20_ultimo_dia"], 1)
        self.assertEqual(alineada["ultimo_dia_no_usado_para_ajustar_regla"]["n"], 12)
        self.assertFalse(alineada["evaluacion_con_muestra_suficiente"])
        self.assertFalse(r["cambios_operativos_autorizados"])

    def test_duplicados_y_empates_excluidos(self):
        rows = [fila(1, "2026-11-10", 20.75),
                fila(1, "2026-11-11", 20.75),
                fila(2, "2026-11-11", 0)]
        r = evaluar_filtros_sombra(rows)
        self.assertEqual(r["descartes"]["ID_DUPLICADO"], 1)
        self.assertEqual(r["descartes"]["NO_EVALUABLE"], 1)
        self.assertEqual(r["hipotesis_predefinidas"][0]["total"]["n"], 1)


if __name__ == "__main__":
    unittest.main()
