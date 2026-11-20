"""Regresiones del diagnostico de consistencia, sin depender del broker."""
import unittest

from auditar_consistencia_20_practice import evaluar_filas


def fila(i, pnl, fecha="2026-11-10 10:00:00", patron="CHOCH bajista"):
    return {
        "fecha": fecha,
        "order_id": str(i),
        "estado": "CERRADA",
        "modo_cuenta_configurado": "PRACTICE",
        "resultado": str(pnl),
        "patron": patron,
    }


class Consistencia20PracticeTests(unittest.TestCase):
    def test_docek_de_veinte_es_el_minimo_inclusivo(self):
        filas = [fila(i, 20.75 if i < 12 else -25) for i in range(20)]
        r = evaluar_filas(filas)
        self.assertTrue(r["consistencia_20_observada"])
        self.assertEqual(r["bloques_completos_bajo_objetivo"], 0)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_once_de_veinte_falla(self):
        filas = [fila(i, 20.75 if i < 11 else -25) for i in range(20)]
        r = evaluar_filas(filas)
        self.assertEqual(r["bloques_completos_bajo_objetivo"], 1)
        self.assertFalse(r["consistencia_20_observada"])

    def test_ventana_movil_detecta_caida_entre_bloques(self):
        # Cada bloque de 20 es favorable, pero existen ventanas intermedias malas.
        pnls = [20.75] * 12 + [-25] * 8 + [-25] * 8 + [20.75] * 12
        r = evaluar_filas([fila(i, v) for i, v in enumerate(pnls)])
        self.assertEqual(r["bloques_completos_bajo_objetivo"], 0)
        self.assertGreater(r["ventanas_moviles_bajo_objetivo"], 0)
        self.assertFalse(r["consistencia_20_observada"])

    def test_empate_timestamp_no_ordena_ids_lexicograficamente(self):
        # ID 10 se ordena antes que 2 como texto, aunque entro despues.
        # La auditoria debe conservar la secuencia CSV ante fechas iguales.
        pnls = [20.75] * 12 + [-25] * 8 + [-25] * 8 + [20.75] * 12
        filas = [fila(i, p) for i, p in enumerate(pnls)]
        r = evaluar_filas(filas)
        self.assertEqual([x["wins"] for x in r["bloques_no_solapados"]], [12, 12])
        self.assertEqual(r["bloques_completos_bajo_objetivo"], 0)
        self.assertGreater(r["ventanas_moviles_bajo_objetivo"], 0)

    def test_no_inventa_prueba_con_menos_de_20(self):
        r = evaluar_filas([fila(i, 20.75) for i in range(19)])
        self.assertEqual(r["ventanas_moviles"], 0)
        self.assertFalse(r["consistencia_20_observada"])
        self.assertIsNone(r["bloques_no_solapados"][0]["cumple_60"])

    def test_duplicado_empate_y_no_cerrada_no_inflan(self):
        filas = [fila(1, 20.75), fila(1, 20.75), fila(2, 0), fila(3, -25)]
        filas[-1]["estado"] = "ABIERTA"
        r = evaluar_filas(filas)
        self.assertEqual(r["total_filas_validas_win_loss"], 1)
        self.assertEqual(r["descartes"]["ORDER_ID_DUPLICADO"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)
        self.assertEqual(r["descartes"]["NO_CERRADA"], 1)

    def test_60_global_no_disfraza_familia_debajo_de_60(self):
        filas = (
            [fila(i, 20.75, patron="fuerte") for i in range(20)]
            + [fila(20 + i, 20.75 if i < 8 else -25, patron="debil")
               for i in range(20)]
        )
        r = evaluar_filas(filas)
        self.assertTrue(r["consistencia_20_por_estrategia"]["fuerte"]["consistencia_observada"])
        self.assertFalse(r["consistencia_20_por_estrategia"]["debil"]["consistencia_observada"])
        self.assertEqual(r["consistencia_20_por_estrategia"]["debil"]["ventanas_bajo_objetivo"], 1)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_familia_con_menos_de_20_no_se_declara_constante(self):
        filas = [fila(i, 20.75, patron="escasa") for i in range(19)]
        r = evaluar_filas(filas)
        d = r["consistencia_20_por_estrategia"]["escasa"]
        self.assertEqual(d["ventanas_moviles"], 0)
        self.assertFalse(d["consistencia_observada"])
        self.assertFalse(d["evidencia_prospectiva_suficiente"])

    def test_rechaza_real_y_modo_ausente_sin_inflar_60(self):
        filas = [fila(i, 20.75) for i in range(20)]
        filas[0]["modo_cuenta_configurado"] = "REAL"
        filas[1]["modo_cuenta_configurado"] = ""
        r = evaluar_filas(filas)
        self.assertEqual(r["total_filas_validas_win_loss"], 18)
        self.assertEqual(r["descartes"]["MODO_NO_VERIFICADO_PRACTICE"], 2)
        self.assertFalse(r["consistencia_20_observada"])
        self.assertFalse(r["procedencia_broker_certificada"])

    def test_docek_wins_con_neto_negativo_no_es_consistencia_economica(self):
        # 12x +0.01 y 8x -25: 60% de acierto pero perdida enorme.
        filas = [fila(i, "0.01" if i < 12 else "-25.00")
                 for i in range(20)]
        r = evaluar_filas(filas)
        self.assertTrue(r["bloques_no_solapados"][0]["cumple_60"])
        self.assertFalse(
            r["bloques_no_solapados"][0]["cumple_objetivo_economico"])
        self.assertEqual(r["bloques_completos_bajo_objetivo"], 1)
        self.assertFalse(r["consistencia_20_observada"])

    def test_subcentavos_no_se_admiten_para_certificacion(self):
        filas = [fila(i, 20.75) for i in range(20)]
        filas[0]["resultado"] = "20.755"
        r = evaluar_filas(filas)
        self.assertEqual(r["descartes"]["RESULTADO_INVALIDO"], 1)
        self.assertEqual(r["total_filas_validas_win_loss"], 19)
        self.assertFalse(r["consistencia_20_observada"])

    def test_bootstrap_no_se_confunde_con_rentabilidad_cerebro_v3(self):
        filas = [fila(i, "20.75") for i in range(20)]
        for registro in filas:
            registro["origen_autoridad"] = "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"
        r = evaluar_filas(filas)
        self.assertTrue(r["consistencia_20_observada"])
        self.assertEqual(r["operaciones_bootstrap"], 20)
        self.assertEqual(r["operaciones_no_bootstrap"], 0)
        self.assertFalse(r["valida_rentabilidad_cerebro_v3"])
        self.assertFalse(r["procedencia_broker_certificada"])

    def test_autoridades_ausentes_y_mixtas_se_reportan_sin_inferir_v3(self):
        filas = [fila(1, "20.75"), fila(2, "-25"), fila(3, "20.75")]
        filas[0]["origen_autoridad"] = "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"
        filas[1]["origen_autoridad"] = "V3_AUTORIDAD_EXPERIMENTAL"
        r = evaluar_filas(filas)
        self.assertEqual(r["operaciones_bootstrap"], 1)
        self.assertEqual(r["operaciones_no_bootstrap"], 1)
        self.assertEqual(
            r["operaciones_por_origen_autoridad"]["SIN_AUTORIDAD_DECLARADA"], 1
        )
        self.assertFalse(r["valida_rentabilidad_cerebro_v3"])

    def test_orden_temporal_y_estrategias_sin_autorizacion(self):
        filas = [
            fila(2, -25, "2026-11-11 10:00:00", "sweep"),
            fila(1, 20.75, "2026-11-10 10:00:00", "choch"),
        ]
        r = evaluar_filas(filas)
        self.assertEqual(list(r["dias"]), ["2026-11-10", "2026-11-11"])
        self.assertEqual(r["estrategias"]["sweep"]["losses"], 1)
        self.assertFalse(r["evidencia_prospectiva_suficiente"])


if __name__ == "__main__":
    unittest.main()
