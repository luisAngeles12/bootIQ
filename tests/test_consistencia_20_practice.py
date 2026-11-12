"""Regresiones del diagnostico de consistencia, sin depender del broker."""
import unittest

from auditar_consistencia_20_practice import evaluar_filas


def fila(i, pnl, fecha="2026-11-10 10:00:00", patron="CHOCH bajista"):
    return {
        "fecha": fecha,
        "order_id": str(i),
        "estado": "CERRADA",
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
