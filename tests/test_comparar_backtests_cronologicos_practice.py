"""Comparador de backtests F5.9: todos los datos son artificiales."""
import ast
import copy
import csv
import io
from pathlib import Path
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
            "fecha_senal": instante.isoformat(),
            "fecha": (instante+timedelta(minutes=1)).isoformat(),
            "direccion": "CALL" if i % 2 else "PUT",
            "patron": "CHOCH alcista" if i % 2 else "CHOCH bajista",
            "estado_operacion": "OPERADA_DIRECTA",
            "resultado_hipotetico": "WIN" if i % 5 < 3 else "LOSS",
            "resultado": "WIN" if i % 4 == 0 else "LOSS",
            "idx_entrada": str(i + 181),
            "precio_entrada": str(100 + i / 100),
            "precio_cierre": str(100 + i / 100 + 0.01),
        })
    return filas


class ComparadorBacktestTest(unittest.TestCase):
    def test_contrato_campos_backtest_canonico_con_comparador(self):
        # La identidad se ancla a la vela senal y la metrica de una
        # orden ejecutada al resultado real simulado, nunca al contrafactual.
        origen = Path(__file__).resolve().parents[1] / "backtest_bot_real.py"
        arbol = ast.parse(origen.read_text(encoding="utf-8"))
        registros = [
            n for n in ast.walk(arbol)
            if isinstance(n, ast.Dict)
            and any(
                isinstance(k, ast.Constant) and k.value == "fecha_senal"
                for k in n.keys
            )
            and any(
                isinstance(k, ast.Constant) and k.value == "resultado_hipotetico"
                for k in n.keys
            )
        ]
        self.assertTrue(registros, "backtest oficial debe conservar snapshot causal")
        representacion = ast.unparse(registros[0])
        self.assertIn("velas[idx]['from']", representacion)
        self.assertIn("velas[idx_entrada]['from']", representacion)
        self.assertIn("info_resultado['resultado']", representacion)
        self.assertIn("info_hipotetico['resultado']", representacion)

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
        self.assertEqual(r["estado"], "NO_COMPARABLE_UNIVERSO_ETIQUETAS_O_EJECUCION")
        self.assertEqual(r["universo"]["solo_antes"], 1)
        self.assertNotIn("antes", r)
        self.assertFalse(r["autoriza_operaciones"])

    def test_universos_distintos_muestran_estadisticas_sin_afirmar_mejora(self):
        a = registros(40)
        b = copy.deepcopy(a)
        b.pop()
        for i in (0, 1, 2):
            b[i]["estado_operacion"] = "CANCELADA_CEREBRO"
        r = comparar(a, b, 20.75, 25)
        self.assertEqual(r["estado"], "NO_COMPARABLE_UNIVERSO_ETIQUETAS_O_EJECUCION")
        self.assertNotIn("antes", r)
        self.assertEqual(r["descriptivo_no_pareado"]["antes"]["operaciones"]["n"], 40)
        self.assertEqual(r["descriptivo_no_pareado"]["despues"]["operaciones"]["n"], 36)
        self.assertEqual(r["descriptivo_no_pareado"]["antes"]["ventanas_20"]["total"], 21)
        self.assertEqual(r["descriptivo_no_pareado"]["despues"]["ventanas_20"]["total"], 17)
        self.assertFalse(r["descriptivo_no_pareado"]["comparacion_causal_permitida"])
        self.assertFalse(r["validacion_rentabilidad_futura"])
        self.assertFalse(r["autoriza_operaciones"])

    def test_precios_divergentes_siguen_mostrando_solo_descriptivos(self):
        a = registros(20)
        b = copy.deepcopy(a)
        b[0]["precio_entrada"] = "999"
        r = comparar(a, b)
        self.assertEqual(r["universo"]["entradas_operadas_divergentes"], 1)
        self.assertEqual(r["descriptivo_no_pareado"]["antes"]["operaciones"]["n"], 20)
        self.assertEqual(r["descriptivo_no_pareado"]["despues"]["operaciones"]["n"], 20)
        self.assertNotIn("neto_teorico", r["descriptivo_no_pareado"]["antes"]["operaciones"])

    def test_etiquetas_hipoteticas_distintas_bloquean_conclusion(self):
        a = registros()
        b = copy.deepcopy(a)
        b[0]["resultado_hipotetico"] = "LOSS"
        r = comparar(a, b)
        self.assertEqual(r["universo"]["etiquetas_distintas_en_comunes"], 1)
        self.assertNotIn("despues", r)

    def test_mismo_win_pero_otro_precio_no_demuestra_mejora(self):
        a = registros()
        b = copy.deepcopy(a)
        b[0]["precio_entrada"] = "999.5"
        r = comparar(a, b)
        self.assertEqual(r["universo"]["entradas_operadas_divergentes"], 1)
        self.assertEqual(r["estado"], "NO_COMPARABLE_UNIVERSO_ETIQUETAS_O_EJECUCION")
        self.assertNotIn("antes", r)
        self.assertFalse(r["autoriza_operaciones"])

    def test_falta_precio_de_entrada_no_se_asume_paridad(self):
        a = registros()
        b = copy.deepcopy(a)
        b[0]["idx_entrada"] = ""
        r = comparar(a, b)
        self.assertEqual(
            r["universo"]["entradas_operadas_sin_precio_o_indice_verificable"], 1
        )
        self.assertFalse(r["universo"]["comparable_estrictamente"])

    def test_no_acepta_identidad_repetida_ni_fecha_sin_zona(self):
        a = registros()
        b = copy.deepcopy(a)
        b.append(dict(b[0]))
        with self.assertRaisesRegex(ValueError, "SENAL_DUPLICADA"):
            comparar(a, b)
        b = copy.deepcopy(a)
        b[0]["fecha_senal"] = "2026-11-10 00:00:00"
        with self.assertRaisesRegex(ValueError, "FECHA_INVALIDA_O_SIN_ZONA"):
            comparar(a, b)

    def test_rechaza_filas_posteriores_con_columnas_incompletas(self):
        a = registros(3)
        b = copy.deepcopy(a)
        # La primera fila es valida; no se debe omitir la verificacion
        # del esquema en las siguientes filas.
        del b[1]["resultado"]
        with self.assertRaisesRegex(ValueError, "COLUMNAS_INSUFICIENTES"):
            comparar(a, b)
        b = copy.deepcopy(a)
        del b[2]["fecha_senal"]
        with self.assertRaisesRegex(ValueError, "COLUMNAS_INSUFICIENTES"):
            comparar(a, b)

    def test_csv_truncado_dictreader_no_se_acepta_como_paridad(self):
        a = registros(2)
        columnas = list(a[0])
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columnas, lineterminator="\\n")
        writer.writeheader()
        writer.writerow(a[0])
        # Emular un registro CSV truncado: DictReader asigna None
        # a los campos del encabezado sin valor en esa fila.
        buffer.write(",".join(str(a[1][k]) for k in columnas[:7]) + "\\n")
        buffer.seek(0)
        b = list(csv.DictReader(buffer))
        self.assertIsNone(b[1]["resultado"])
        with self.assertRaisesRegex(ValueError, "COLUMNAS_INSUFICIENTES"):
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

    def test_resumen_operado_usa_resultado_no_resultado_hipotetico(self):
        a = registros(20)
        r = comparar(a, copy.deepcopy(a))
        wins_reales = sum(x["resultado"] == "WIN" for x in a)
        wins_hipoteticos = sum(x["resultado_hipotetico"] == "WIN" for x in a)
        self.assertNotEqual(wins_reales, wins_hipoteticos)
        self.assertEqual(r["antes"]["wins"], wins_reales)
        self.assertEqual(r["despues"]["wins"], wins_reales)

    def test_fechas_de_entrada_diferentes_no_rompen_identidad_causal(self):
        a = registros()
        b = copy.deepcopy(a)
        b[0]["fecha"] = (BASE+timedelta(minutes=2)).isoformat()
        r = comparar(a, b)
        self.assertEqual(r["universo"]["comunes"], len(a))
        self.assertEqual(r["universo"]["solo_antes"], 0)
        self.assertEqual(r["universo"]["solo_despues"], 0)
        self.assertEqual(r["universo"]["entradas_operadas_divergentes"], 1)
        self.assertFalse(r["universo"]["comparable_estrictamente"])

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
        b.append(dict(b[0], fecha_senal="2026-11-09T20:00:00-04:00"))
        with self.assertRaisesRegex(ValueError, "SENAL_DUPLICADA"):
            comparar(a, b)


if __name__ == "__main__":
    unittest.main()
