"""Comparador de backtests F5.9: todos los datos son artificiales."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from comparar_backtests_cronologicos_practice import comparar


BASE = datetime(2026, 11, 10, tzinfo=timezone.utc)


def registros(n=60):
    filas = []
    for i in range(n):
        instante = BASE+timedelta(minutes=60*i)
        filas.append({
            "activo": "EURUSD-OTC" if i % 2 else "GBPUSD-OTC",
            "fecha": instante.isoformat(),
            "direccion": "CALL" if i % 2 else "PUT",
            "patron": "CHOCH alcista" if i % 2 else "CHOCH bajista",
            "estado_operacion": "OPERADA_DIRECTA",
            "resultado_hipotetico": "WIN" if i % 5 < 3 else "LOSS",
        })
    return filas


class ComparadorBacktestTest(unittest.TestCase):
    def test_mismo_universo_descartes_y_ventanas_20(self):
        a = registros()
        b = copy.deepcopy(a)
        # Nuevo candidato no opera en 10 señales que antes se operaban.
        for i in range(0, 60, 6):
            b[i]["estado_operacion"] = "NO_OPERADA"
        previo = copy.deepcopy((a, b))
        r = comparar(a, b, 20.75, 25)
        self.assertEqual((a, b), previo)
        self.assertEqual(r["estado"], "COMPARABLE_DESCRIPTIVO")
        self.assertEqual(r["universo"]["comunes"], 60)
        self.assertEqual(r["antes"]["n"], 60)
        self.assertEqual(r["despues"]["n"], 50)
        self.assertEqual(r["transiciones"]["OPERADA_A_NO_OPERADA"], 10)
        self.assertEqual(r["ventanas_20_antes"]["total"], 41)
        self.assertEqual(r["ventanas_20_despues"]["total"], 31)
        self.assertTrue(r["por_dia"])
        self.assertEqual(r["supuestos_pnl"]["tipo"], "HIPOTETICOS_NO_PNL_BROKER")
        self.assertFalse(r["autoriza_operaciones"])
        self.assertFalse(r["validacion_rentabilidad_futura"])

    def test_muestra_distinta_es_no_comparable(self):
        a = registros()
        b = copy.deepcopy(a)
        b.pop()
        r = comparar(a, b)
        self.assertEqual(r["estado"], "NO_COMPARABLE_UNIVERSO_O_ETIQUETAS")
        self.assertEqual(r["universo"]["solo_antes"], 1)
        self.assertNotIn("antes", r)
        self.assertFalse(r["autoriza_operaciones"])

    def test_etiquetas_hipoteticas_distintas_bloquean_conclusion(self):
        a = registros()
        b = copy.deepcopy(a)
        b[0]["resultado_hipotetico"] = "LOSS"
        r = comparar(a, b)
        self.assertEqual(r["universo"]["etiquetas_distintas_en_comunes"], 1)
        self.assertNotIn("despues", r)

    def test_no_acepta_identidad_repetida_ni_fecha_sin_zona(self):
        a = registros()
        b = copy.deepcopy(a)
        b.append(dict(b[0]))
        with self.assertRaisesRegex(ValueError, "SENAL_DUPLICADA"):
            comparar(a, b)
        b = copy.deepcopy(a)
        b[0]["fecha"] = "2026-11-10 00:00:00"
        with self.assertRaisesRegex(ValueError, "FECHA_INVALIDA_O_SIN_ZONA"):
            comparar(a, b)

    def test_no_acepta_orden_sin_clasificacion_ni_etiqueta(self):
        a = registros()
        b = copy.deepcopy(a)
        b[0]["estado_operacion"] = ""
        with self.assertRaisesRegex(ValueError, "ESTADO_OPERACION_NO_RECONOCIDO"):
            comparar(a, b)
        b = copy.deepcopy(a)
        b[0]["resultado_hipotetico"] = ""
        with self.assertRaisesRegex(ValueError, "RESULTADO_HIPOTETICO"):
            comparar(a, b)

    def test_no_inventa_neto_sin_supuestos_explicitos(self):
        a = registros()
        r = comparar(a, copy.deepcopy(a))
        self.assertNotIn("neto_teorico", r["antes"])
        self.assertIsNone(r["supuestos_pnl"])
        with self.assertRaisesRegex(ValueError, "SUPUESTOS_PNL_INCOMPLETOS"):
            comparar(a, a, 20.75)
        with self.assertRaisesRegex(ValueError, "SUPUESTOS_PNL_INVALIDOS"):
            comparar(a, a, float("nan"), 25)

    def test_rechaza_universo_vacio_y_fechas_equivalentes_duplicadas(self):
        with self.assertRaisesRegex(ValueError, "BACKTEST_VACIO"):
            comparar([], [])
        a = registros(1)
        b = copy.deepcopy(a)
        b.append(dict(b[0], fecha="2026-11-09T20:00:00-04:00"))
        with self.assertRaisesRegex(ValueError, "SENAL_DUPLICADA"):
            comparar(a, b)


if __name__ == "__main__":
    unittest.main()
