import unittest
from datetime import datetime, timezone
from auditoria_meta_sostenida_fase3 import evaluar_meta_sostenida


def ventanas(wins=(34, 34, 34), n=40, pnl_win=0.8, pnl_loss=-1):
    salida = []
    for i, w in enumerate(wins):
        dia = 27 + i
        marca = datetime(2026, 10, dia, tzinfo=timezone.utc).timestamp()
        filas = []
        for j in range(n):
            ganada = j < w
            filas.append({
                "fecha_senal": marca + j, "activo": "X",
                "patron": "P", "direccion": "call",
                "estado_operacion": "CERRADA", "tipo_cuenta": "PRACTICE",
                "resultado": "WIN" if ganada else "LOSS",
                "pnl_real_cerrado": pnl_win if ganada else pnl_loss,
            })
        salida.append(("D" + str(dia), filas))
    return salida


class MetaSostenidaF3Tests(unittest.TestCase):
    def test_exige_consistencia_wilson_y_pnl(self):
        r = evaluar_meta_sostenida(ventanas(), payout_neto=0.8)
        self.assertTrue(r["objetivo_57_sostenido_verificado"])
        self.assertGreater(r["wilson_inferior_95"], 57)
        self.assertFalse(r["autoriza_real"])

    def test_no_promueve_un_dia_excelente(self):
        r = evaluar_meta_sostenida(ventanas(wins=(40, 20, 40)), payout_neto=0.8)
        self.assertFalse(r["objetivo_57_sostenido_verificado"])

    def test_no_promueve_pnl_negativo(self):
        r = evaluar_meta_sostenida(ventanas(pnl_win=0.1), payout_neto=0.1)
        self.assertTrue(r["estabilidad_estadistica"])
        self.assertFalse(r["objetivo_57_sostenido_verificado"])

    def test_no_confunde_canceladas_con_ejecutadas(self):
        w = ventanas()
        w[0][1][0]["estado_operacion"] = "CANCELADA_CEREBRO"
        with self.assertRaises(ValueError):
            evaluar_meta_sostenida(w, payout_neto=0.8)

    def test_rechaza_dias_duplicados_y_real(self):
        w = ventanas()
        w[1][1][0]["tipo_cuenta"] = "REAL"
        with self.assertRaises(ValueError):
            evaluar_meta_sostenida(w, payout_neto=0.8)
        w = ventanas()
        w[1] = ("OTRO", w[0][1].copy())
        with self.assertRaises(ValueError):
            evaluar_meta_sostenida(w, payout_neto=0.8)

    def test_rechaza_fechas_antiguas_y_payout_faltante(self):
        with self.assertRaises(ValueError):
            evaluar_meta_sostenida(ventanas(), payout_neto=None)
        w = ventanas()
        w[0][1][0]["fecha_senal"] = datetime(2026, 10, 25,
                                            tzinfo=timezone.utc).timestamp()
        with self.assertRaises(ValueError):
            evaluar_meta_sostenida(w, payout_neto=0.8)


if __name__ == "__main__":
    unittest.main()
