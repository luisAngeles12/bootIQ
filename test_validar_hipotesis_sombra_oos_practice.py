"""Pruebas aisladas de selección temporal de rechazadas PRACTICE."""
import unittest
from datetime import datetime, timezone, timedelta
from validar_hipotesis_sombra_oos_practice import validar, CALIDAD


class ShadowOOSTests(unittest.TestCase):
    def fila(self, dia, n, patron, win, oid=None):
        t = datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=dia, seconds=n)
        return {
            "id": oid or f"{dia}-{n}-{patron}",
            "decision": "NO_OPERAR",
            "vela_entrada_from": str(int(t.timestamp())),
            "resultado_hipotetico": "WIN" if win else "LOSS",
            "calidad_tiempo": CALIDAD,
            "direccion": "call", "patron": patron,
        }

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
