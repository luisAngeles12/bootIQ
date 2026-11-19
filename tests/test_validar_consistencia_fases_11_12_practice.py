"""Regresiones sintéticas del criterio PRACTICE por ventanas de 20."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from validar_consistencia_fases_11_12_practice import evaluar

BASE = datetime(2026, 10, 1, tzinfo=timezone.utc)

def filas(n=40, losses=0, familia="resistencia"):
    out = []
    for i in range(n):
        es_loss = (i % 20) < losses
        out.append({
            "order_id": str(i + 1),
            "fecha_cierre": (BASE + timedelta(minutes=i)).isoformat(),
            "resultado": "LOSS" if es_loss else "WIN",
            "neto": "-25" if es_loss else "20.75",
            "familia": familia, "tipo_cuenta": "PRACTICE",
        })
    return out

class ConsistenciaTest(unittest.TestCase):
    def test_no_certifica_menos_de_20(self):
        r = evaluar(filas(19))
        self.assertFalse(r["cumple_muestra_observada"])
        self.assertEqual(r["ventanas_moviles_20"], 0)

    def test_12_de_20_y_neto_positivo(self):
        r = evaluar(filas(40, 8))
        self.assertEqual(r["total"]["acierto_pct"], 60)
        self.assertTrue(r["cumple_muestra_observada"])
        self.assertEqual(r["ventanas_moviles_20"], 21)
        self.assertEqual(r["ventanas_bajo_objetivo"], 0)
        self.assertEqual(r["bloques_no_solapados_20"], 2)
        self.assertTrue(r["cumple_conjunto_y_familias"])
        self.assertFalse(r["autoriza_real"])
        self.assertFalse(r["validacion_prospectiva_confirmada"])

    def test_60pct_sin_neto_positivo_rechaza(self):
        a = filas(20, 8)
        for f in a:
            if f["resultado"] == "WIN":
                f["neto"] = "5"
        self.assertFalse(evaluar(a)["cumple_muestra_observada"])

    def test_una_ventana_mala_invalida_total(self):
        a = filas(40, 8)
        a[8]["resultado"] = "LOSS"
        a[8]["neto"] = "-25"
        r = evaluar(a)
        self.assertFalse(r["cumple_muestra_observada"])
        self.assertGreater(r["ventanas_bajo_objetivo"], 0)

    def test_11_wins_y_empates_no_sustituyen_12_de_20(self):
        a = filas(20, 8)
        a[8]["resultado"] = "EMPATE"
        a[8]["neto"] = "0"
        r = evaluar(a)
        self.assertEqual(r["total"]["wins"], 11)
        self.assertEqual(r["total"]["acierto_pct"], 55)
        self.assertFalse(r["cumple_muestra_observada"])

    def test_rechaza_real(self):
        a = filas(20)
        a[0]["tipo_cuenta"] = "REAL"
        with self.assertRaisesRegex(ValueError, "SOLO_PRACTICE"):
            evaluar(a)

    def test_rechaza_duplicados(self):
        a = filas(20)
        a[1]["order_id"] = "1"
        with self.assertRaisesRegex(ValueError, "ORDEN_DUPLICADA"):
            evaluar(a)

    def test_rechaza_resultado_y_neto_incoherentes(self):
        a = filas(20)
        a[1]["neto"] = "-25"
        with self.assertRaisesRegex(ValueError, "RESULTADO_NETO_CONTRADICTORIO"):
            evaluar(a)

    def test_orden_temporal_y_sin_mutacion(self):
        a = filas(40, 8)
        a.reverse()
        original = copy.deepcopy(a)
        r = evaluar(a)
        self.assertTrue(r["cumple_muestra_observada"])
        self.assertEqual(a, original)

    def test_familia_relevante_con_ventana_mala_impide_certificacion_conjunta(self):
        a = filas(40, 8)
        for i, f in enumerate(a):
            f["familia"] = "a" if (i % 20) < 10 else "b"
        r = evaluar(a)
        self.assertTrue(r["cumple_muestra_observada"])
        self.assertFalse(r["cumple_conjunto_y_familias"])

    def test_familia_en_blanco_no_valida_consistencia(self):
        a = filas(20, 8)
        for f in a:
            f["familia"] = "   "
        with self.assertRaisesRegex(ValueError, "FAMILIA_VACIA"):
            evaluar(a)

    def test_familia_pequena_no_certificada(self):
        a = filas(40, 8)
        for f in a[:19]:
            f["familia"] = "familia_pequena"
        r = evaluar(a)
        self.assertFalse(r["familias"]["familia_pequena"]["todas_ventanas_cumplen"])

if __name__ == "__main__":
    unittest.main()
