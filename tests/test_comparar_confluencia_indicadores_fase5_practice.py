"""Pruebas de confluencia Fase 5 sin broker ni archivos productivos."""
import unittest

from comparar_confluencia_indicadores_fase5_practice import (
    evaluar_confluencia,
)


def fila(i, dia="2026-11-10", pnl=20.75, **extra):
    base = {
        "estado": "CERRADA", "order_id": str(i),
        "fecha": f"{dia}T10:{i % 60:02d}:00",
        "resultado": str(pnl), "direccion": "CALL",
        "pa_direccion": "CALL", "patron": "CHOCH",
        "ema9": "101", "ema21": "100", "rsi": "50",
        "bb_superior": "105", "bb_media": "100",
        "bb_inferior": "95", "ultima_close": "102",
    }
    base.update(extra)
    return base


class ConfluenciaFase5Tests(unittest.TestCase):
    def test_confluencias_y_cobertura_datos_conocidos(self):
        filas = [
            fila(1),
            fila(2, ema9="", ema21=""),
            fila(3, pa_direccion="PUT"),
            fila(4, rsi="NaN"),
            fila(5, bb_inferior="110"),
        ]
        r = evaluar_confluencia(filas)
        self.assertEqual(r["total_cerradas_evaluables"], 5)
        self.assertEqual(r["cobertura"]["ema_disponible"], 4)
        self.assertEqual(r["cobertura"]["rsi_disponible"], 4)
        self.assertEqual(r["cobertura"]["bb_disponible"], 4)
        grupos = {x["hipotesis_fija"]: x for x in r["escenarios"]}
        self.assertEqual(grupos["EMA_ALINEADA"]["ultimo_dia_oos_descriptivo"]["n"], 4)
        self.assertEqual(grupos["PA_Y_EMA_ALINEADAS"]["ultimo_dia_oos_descriptivo"]["n"], 3)
        self.assertEqual(grupos["PA_EMA_RSI_NEUTRO"]["ultimo_dia_oos_descriptivo"]["n"], 2)
        self.assertEqual(grupos["PA_EMA_BB_DENTRO"]["ultimo_dia_oos_descriptivo"]["n"], 2)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_sin_snapshots_no_inventa_confluencias(self):
        f = fila(1)
        for key in ("ema9", "ema21", "rsi", "bb_superior", "bb_media",
                    "bb_inferior", "ultima_close"):
            f.pop(key)
        r = evaluar_confluencia([f])
        self.assertEqual(r["cobertura"]["ema_disponible"], 0)
        self.assertEqual(r["cobertura"]["rsi_disponible"], 0)
        self.assertEqual(r["cobertura"]["bb_disponible"], 0)
        for escenario in r["escenarios"][1:]:
            self.assertEqual(escenario["ultimo_dia_oos_descriptivo"]["n"], 0)

    def test_solo_cierre_unico_no_empate_ni_invalidos(self):
        r = evaluar_confluencia([
            fila(1),
            fila(1),
            fila(2, pnl=0),
            fila(3, pnl=float("nan")),
            fila(4, estado="ABIERTA"),
            fila(5, direccion=""),
        ])
        self.assertEqual(r["total_cerradas_evaluables"], 1)
        self.assertEqual(r["descartes"]["ID_AUSENTE_O_DUPLICADO"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)
        self.assertEqual(r["descartes"]["FECHA_O_PNL_INVALIDO"], 1)
        self.assertEqual(r["descartes"]["NO_CERRADA"], 1)
        self.assertEqual(r["descartes"]["SIN_DIRECCION"], 1)

    def test_dos_bloques_buenos_pueden_ocultar_ventanas_malas(self):
        pnls = [20.75] * 12 + [-25] * 8 + [-25] * 8 + [20.75] * 12
        filas = [fila(i, "2026-11-10", 20.75) for i in range(20)]
        filas += [fila(i + 20, "2026-11-11", pnl)
                  for i, pnl in enumerate(pnls)]
        r = evaluar_confluencia(filas)
        test = r["escenarios"][0]["ultimo_dia_oos_descriptivo"]
        self.assertEqual(test["winrate_pct"], 60)
        self.assertEqual(test["ventanas_20"], 21)
        self.assertGreater(test["ventanas_20_bajo_60"], 0)
        self.assertFalse(test["consistencia_20_observada"])
        self.assertTrue(r["escenarios"][0]["muestra_test_suficiente"])

    def test_ventana_insuficiente_no_se_aprueba(self):
        r = evaluar_confluencia([fila(i) for i in range(19)])
        for escenario in r["escenarios"]:
            self.assertFalse(escenario["ultimo_dia_oos_descriptivo"]["consistencia_20_observada"])
            self.assertFalse(escenario["muestra_test_suficiente"])

    def test_snapshot_json_sin_columnas_reconocido(self):
        f = fila(1)
        for k in ("ema9", "ema21", "rsi", "bb_superior", "bb_media",
                  "bb_inferior", "ultima_close"):
            f.pop(k)
        f["indicadores_tecnicos_json"] = (
            '{"ema9":101,"ema21":100,"bb_superior":105,'
            '"bb_media":100,"bb_inferior":95}'
        )
        f["rsi_indicador"] = "50"
        f["precio_cierre_indicadores"] = "102"
        r = evaluar_confluencia([f])
        self.assertEqual(r["cobertura"]["ema_disponible"], 1)
        self.assertEqual(r["cobertura"]["rsi_disponible"], 1)
        self.assertEqual(r["cobertura"]["bb_disponible"], 1)

    def test_patron_perdedor_no_queda_oculto_por_agregado(self):
        # Dos familias: agregado de 60% con una familia en 20%.
        train = [
            fila(i, "2026-11-10", 20.75, patron="CHOCH")
            for i in range(20)
        ]
        test = [
            fila(i + 20, "2026-11-11", 20.75, patron="CHOCH")
            for i in range(20)
        ] + [
            fila(i + 40, "2026-11-11", 20.75 if i < 4 else -25,
                 patron="RETEST")
            for i in range(20)
        ]
        r = evaluar_confluencia(train + test)
        escenario = r["escenarios"][0]
        global_test = escenario["ultimo_dia_oos_descriptivo"]
        self.assertEqual(global_test["winrate_pct"], 60)
        familias = {p["patron"]: p for p in escenario["por_patron"]}
        self.assertEqual(set(familias), {"CHOCH", "RETEST"})
        self.assertEqual(
            familias["RETEST"]["ultimo_dia_oos_descriptivo"]["winrate_pct"],
            20,
        )
        self.assertFalse(
            familias["RETEST"]["ultimo_dia_oos_descriptivo"]["consistencia_20_observada"]
        )
        self.assertEqual(
            familias["RETEST"]["ultimo_dia_oos_descriptivo"]["ventanas_20_bajo_60"],
            1,
        )
        self.assertFalse(r["operaciones_autorizadas"])

    def test_filtro_no_desaparece_patron_sin_datos_ema(self):
        filas = [
            fila(1, "2026-11-10", patron="CHOCH"),
            fila(2, "2026-11-11", patron="CHOCH"),
            fila(3, "2026-11-11", patron="SWEEP", ema9="", ema21=""),
        ]
        r = evaluar_confluencia(filas)
        grupos = {e["hipotesis_fija"]: e for e in r["escenarios"]}
        patron = {p["patron"]: p for p in grupos["EMA_ALINEADA"]["por_patron"]}
        self.assertEqual(set(patron), {"CHOCH", "SWEEP"})
        sweep = patron["SWEEP"]["ultimo_dia_oos_descriptivo"]
        self.assertEqual(sweep["universo"], 1)
        self.assertEqual(sweep["n"], 0)
        self.assertFalse(sweep["consistencia_20_observada"])
        self.assertFalse(patron["SWEEP"]["muestra_test_suficiente"])

    def test_ventanas_entre_train_y_test_no_quedan_ocultas(self):
        # Cada dia por separado registra 12W/8L (60%) y neto positivo;
        # el cruce contiene 8L consecutivas a ambos lados.
        train = [20.75] * 12 + [-25] * 8
        test = [-25] * 8 + [20.75] * 12
        filas = [
            fila(i, "2026-11-10", pnl, patron="CHOCH")
            for i, pnl in enumerate(train)
        ] + [
            fila(i + 20, "2026-11-11", pnl, patron="CHOCH")
            for i, pnl in enumerate(test)
        ]
        resultado = evaluar_confluencia(filas)
        escenario = resultado["escenarios"][0]
        self.assertTrue(escenario["train"]["consistencia_20_observada"])
        self.assertTrue(
            escenario["ultimo_dia_oos_descriptivo"]["consistencia_20_observada"]
        )
        total = escenario["total_historico_ventanas_20"]
        self.assertEqual(total["winrate_pct"], 60)
        self.assertEqual(total["ventanas_20"], 21)
        self.assertGreater(total["ventanas_20_bajo_60"], 0)
        self.assertFalse(total["consistencia_20_observada"])
        patron = escenario["por_patron"][0]
        self.assertEqual(patron["patron"], "CHOCH")
        self.assertEqual(
            patron["total_historico_ventanas_20"]["ventanas_20_bajo_60"],
            total["ventanas_20_bajo_60"],
        )
        self.assertFalse(escenario["habilita_cambios"])

    def test_60_por_ciento_puede_tener_neto_negativo(self):
        # El porcentaje cumple, pero 12 ganancias pequenas no cubren 8 perdidas.
        train = [fila(i, "2026-11-10", 20.75) for i in range(20)]
        test = [
            fila(i + 20, "2026-11-11", 1 if i < 12 else -25)
            for i in range(20)
        ]
        reporte = evaluar_confluencia(train + test)
        resumen_test = reporte["escenarios"][0]["ultimo_dia_oos_descriptivo"]
        self.assertEqual(resumen_test["wins"], 12)
        self.assertEqual(resumen_test["winrate_pct"], 60)
        self.assertTrue(resumen_test["consistencia_20_observada"])
        self.assertEqual(resumen_test["ventanas_20_bajo_60"], 0)
        self.assertEqual(resumen_test["ventanas_20_neto_no_positivo"], 1)
        self.assertFalse(resumen_test["consistencia_20_y_neto_observada"])
        self.assertLess(resumen_test["neto"], 0)
        self.assertFalse(reporte["operaciones_autorizadas"])

    def test_muestra_menor_de_20_no_demuestra_neto_ni_consistencia(self):
        reporte = evaluar_confluencia([fila(i) for i in range(19)])
        resumen = reporte["escenarios"][0]["total_historico_ventanas_20"]
        self.assertEqual(resumen["ventanas_20"], 0)
        self.assertEqual(resumen["ventanas_20_neto_no_positivo"], 0)
        self.assertFalse(resumen["consistencia_20_y_neto_observada"])

    def test_no_acepta_test_menor_20(self):
        with self.assertRaises(ValueError):
            evaluar_confluencia([], minimo_test=19)


if __name__ == "__main__":
    unittest.main()
