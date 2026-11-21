"""Pruebas aisladas de selección temporal de rechazadas PRACTICE."""
import unittest
from datetime import datetime, timezone, timedelta
from validar_hipotesis_sombra_oos_practice import validar, CALIDAD, _metrica


class ShadowOOSTests(unittest.TestCase):
    def fila(self, dia, n, patron, win, oid=None):
        t = datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=dia, minutes=n)
        return {
            "id": oid or f"{dia}-{n}-{patron}",
            "decision": "NO_OPERAR",
            "vela_entrada_from": str(int(t.timestamp())),
            "resultado_hipotetico": "WIN" if win else "LOSS",
            "calidad_tiempo": CALIDAD,
            "direccion": "call", "patron": patron,
        }

    def test_confianza_de_sombra_usa_minutos_no_operaciones(self):
        items = []
        for minuto in range(60):
            for idx, win in enumerate((0, 1, 1, 1)):
                items.append({
                    "ts": 1800000000 + minuto*60,
                    "id": f"{minuto:03d}-{idx}",
                    "dia": "2026-11-18",
                    "win": win,
                })
        salida = _metrica(items)
        self.assertEqual(salida["wr_pct"], 75.0)
        self.assertEqual(salida["minutos_distintos"], 60)
        self.assertEqual(salida["winrate_por_minuto_pct"], 0.0)
        self.assertEqual(salida["wilson_minutos_inferior_95_pct"], 0.0)

    def test_entrenamiento_favorable_no_cambia_resultado_test(self):
        rows = []
        for dia in range(10):
            for n in range(30):
                # TRAIN dias 0..6 favorecen A; TEST dias 7..9 pierde.
                rows.append(self.fila(dia, n, "A", dia < 7 or n < 5))
                rows.append(self.fila(dia, n+30, "B", n < 12))
        reporte = validar(rows, minimo_train=40, minimo_test=30)
        c = reporte["candidato"]
        self.assertEqual(reporte["corte_train"], "2026-11-07")
        self.assertEqual(c["campo"], "patron")
        self.assertEqual(c["valor"], "A")
        self.assertLess(c["test"]["wr_pct"], 60)
        self.assertFalse(c["constancia_hipotetica"])
        self.assertFalse(c["apto_para_promocion"])
        self.assertFalse(reporte["autoriza_operaciones"])
        self.assertIsNone(reporte["pnl_broker"])

    def test_top_diagnostico_no_reordena_por_test(self):
        base, invertido = [], []
        for dia in range(10):
            for minuto in range(60):
                patron = "A" if minuto < 30 else "B"
                favorable_train = patron == "A" or minuto < 38
                a = favorable_train if dia < 7 else patron == "B"
                b = favorable_train if dia < 7 else patron == "A"
                base.append(self.fila(dia, minuto, patron, a))
                invertido.append(self.fila(dia, minuto, patron, b))
        x = validar(base, minimo_train=40, minimo_test=30)
        y = validar(invertido, minimo_train=40, minimo_test=30)
        tabla_x = [(v["campo"], v["valor"]) for v in x["tabla_candidatos_train_con_test"]]
        tabla_y = [(v["campo"], v["valor"]) for v in y["tabla_candidatos_train_con_test"]]
        self.assertTrue(tabla_x)
        self.assertEqual(tabla_x, tabla_y)
        self.assertEqual(tabla_x[0], ("patron", "A"))
        self.assertEqual((x["candidato"]["campo"], x["candidato"]["valor"]), tabla_x[0])
        self.assertTrue(x["seleccion_por_test_prohibida"])
        self.assertFalse(x["autoriza_operaciones"])

    def test_test_no_puede_cambiar_la_seleccion_train(self):
        base, variante = [], []
        for dia in range(10):
            for n in range(20):
                for patron in ("A", "B"):
                    # Entrenamiento idéntico en ambos universos.
                    train_gana = patron == "A" or n < 6
                    # TEST cambia por completo pero no puede seleccionar.
                    win_base = train_gana if dia < 7 else patron == "B"
                    win_variante = train_gana if dia < 7 else patron == "A"
                    base.append(self.fila(dia, n + (100 if patron == "B" else 0),
                                          patron, win_base))
                    variante.append(self.fila(dia, n + (100 if patron == "B" else 0),
                                              patron, win_variante))
        a = validar(base)["candidato"]
        b = validar(variante)["candidato"]
        self.assertEqual((a["campo"], a["valor"]), (b["campo"], b["valor"]))
        self.assertEqual((a["campo"], a["valor"]), ("patron", "A"))
        self.assertNotEqual(a["test"]["wr_pct"], b["test"]["wr_pct"])

    def test_simultaneas_no_inflan_muestra_independiente(self):
        rows = []
        for dia in range(10):
            for minuto in range(3):
                for k in range(50):
                    # Mismo minuto, señales distintas con IDs diferentes.
                    fila = self.fila(dia, minuto, "A", True,
                                     oid=f"{dia}-{minuto}-{k}")
                    rows.append(fila)
        resultado = validar(rows, minimo_train=40, minimo_test=30)
        self.assertEqual(resultado["estado"], "SIN_CANDIDATOS_TRAIN")
        self.assertEqual(resultado["baseline_train"]["minutos_distintos"], 21)
        self.assertFalse(resultado["autoriza_operaciones"])

    def test_duplicados_y_real_no_se_convierten_en_datos(self):
        rows = [self.fila(0, 1, "A", True, "DUP"),
                self.fila(0, 2, "A", False, "DUP")]
        informe = validar(rows)
        self.assertEqual(informe["resueltos"], 0)
        self.assertEqual(informe["descartes"]["ID_REPETIDO_O_VACIO"], 2)

    def test_historico_de_un_dia_no_declara_ventaja(self):
        rows = [self.fila(0, n, "A", True) for n in range(100)]
        informe = validar(rows)
        self.assertEqual(informe["estado"], "DIAS_INSUFICIENTES")
        self.assertIsNone(informe["candidato"])

    def test_resultado_hipotetico_no_es_fill(self):
        rows = [self.fila(d, n, "A", True) for d in range(10) for n in range(50)]
        informe = validar(rows)
        self.assertFalse(informe["rentabilidad_demostrada"])
        self.assertFalse(informe["autoriza_operaciones"])


if __name__ == "__main__":
    unittest.main()
