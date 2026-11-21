"""No contaminar una hipotesis futura con datos del descubrimiento."""
import unittest
from datetime import datetime, timezone
from seguir_hipotesis_choch_prospectivas_practice import evaluar


def fila(dia, minuto, tendencia, gana):
    ts = int(datetime(2026, 11, dia, 12, minuto, tzinfo=timezone.utc).timestamp())
    return {
        "id": f"{dia}-{minuto}-{tendencia}", "decision": "NO_OPERAR",
        "resultado_hipotetico": "WIN" if gana else "LOSS",
        "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
        "vela_entrada_from": str(ts), "direccion": "put",
        "patron": "CHOCH BAJISTA", "estado_tendencia": tendencia,
    }


class HipotesisChochProspectivasTests(unittest.TestCase):
    def test_nunca_incluye_train_ni_test_del_descubrimiento(self):
        filas = [
            fila(17, 1, "BAJISTA_NORMAL", True),
            fila(21, 2, "BAJISTA_NORMAL", True),
            fila(22, 3, "BAJISTA_NORMAL", False),
            fila(22, 4, "INDEFINIDA", True),
        ]
        result = evaluar(filas)
        self.assertEqual(result["filas_elegibles_posteriores"], 2)
        a, b = result["hipotesis_congeladas"]
        self.assertEqual(a["resumen_hipotetico"]["n"], 1)
        self.assertEqual(a["resumen_hipotetico"]["wr_pct"], 0.0)
        self.assertEqual(b["resumen_hipotetico"]["n"], 1)
        self.assertEqual(b["resumen_hipotetico"]["wr_pct"], 100.0)
        self.assertFalse(a["cobertura_minima_de_observacion"])
        self.assertFalse(b["cobertura_minima_de_observacion"])
        self.assertFalse(result["autoriza_operaciones"])
        self.assertFalse(result["puede_promover_memoria_oficial"])
        self.assertIsNone(a["pnl_broker"])

    def test_otro_patron_no_entra_en_hipotesis(self):
        rows = [fila(22, 1, "BAJISTA_NORMAL", True)]
        rows[0]["patron"] = "LIQUIDITY SWEEP"
        r = evaluar(rows)
        self.assertEqual(r["filas_elegibles_posteriores"], 1)
        self.assertTrue(all(x["resumen_hipotetico"]["n"] == 0
                            for x in r["hipotesis_congeladas"]))


if __name__ == "__main__":
    unittest.main()
