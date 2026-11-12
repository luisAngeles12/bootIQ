"""Pruebas de separacion temporal sin cambio de decisiones LIVE."""
import unittest

from experimentos_fase5_practice import evaluar_separacion_temporal


def fila(i, dia, pnl, patron="CHOCH"):
    return {
        "order_id": str(i),
        "fecha": dia + " 10:00:00",
        "estado": "CERRADA",
        "resultado": str(pnl),
        "patron": patron,
    }


class ExperimentosFase5Tests(unittest.TestCase):
    def test_no_usa_test_para_seleccionar_estrategia(self):
        # Train malo; OOS excelente: nunca selecciona por conocer OOS.
        train = [fila(i, "2026-11-10", -25, "A") for i in range(20)]
        test = [fila(i + 20, "2026-11-11", 20.75, "A") for i in range(20)]
        r = evaluar_separacion_temporal(train + test)
        a = r["experimentos"][0]
        self.assertFalse(a["seleccion_train"])
        self.assertIsNone(a["test_cumple_objetivo"])
        self.assertFalse(r["cambios_live_autorizados"])

    def test_train_favorable_y_test_desfavorable(self):
        train = [fila(i, "2026-11-10", 20.75 if i < 15 else -25) for i in range(20)]
        test = [fila(i + 20, "2026-11-11", 20.75 if i < 10 else -25) for i in range(20)]
        r = evaluar_separacion_temporal(train + test)
        a = r["experimentos"][0]
        self.assertTrue(a["seleccion_train"])
        self.assertFalse(a["test_cumple_objetivo"])
        self.assertEqual(r["dia_test"], "2026-11-11")
        self.assertFalse(r["evidencia_prospectiva_suficiente"])

    def test_train_y_test_favorables_no_autorizan_live(self):
        train = [fila(i, "2026-11-10", 20.75 if i < 15 else -25) for i in range(20)]
        test = [fila(i + 20, "2026-11-11", 20.75 if i < 15 else -25) for i in range(20)]
        r = evaluar_separacion_temporal(train + test)
        self.assertTrue(r["experimentos"][0]["test_cumple_objetivo"])
        self.assertFalse(r["cambios_live_autorizados"])

    def test_una_fecha_no_crea_evidencia(self):
        r = evaluar_separacion_temporal([fila(i, "2026-11-10", 20.75) for i in range(20)])
        self.assertEqual(r["estado"], "SIN_SEPARACION_TEMPORAL")
        self.assertEqual(r["experimentos"], [])

    def test_empates_duplicados_abiertas_no_inflan(self):
        filas = [fila(1, "2026-11-10", 20.75),
                 fila(1, "2026-11-11", 20.75),
                 fila(2, "2026-11-11", 0),
                 fila(3, "2026-11-11", -25)]
        filas[-1]["estado"] = "ABIERTA"
        r = evaluar_separacion_temporal(filas)
        self.assertEqual(r["descartes"]["ID_AUSENTE_O_REPETIDO"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)
        self.assertEqual(r["descartes"]["NO_CERRADA"], 1)
        self.assertFalse(r["cambios_live_autorizados"])


if __name__ == "__main__":
    unittest.main()
