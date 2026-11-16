"""Contrato de persistencia Fase 5, solo lectura, sin broker.

Se verifica el codigo real mediante AST para evitar importar IQ Option,
iniciar el bot o escribir historial de usuario durante las pruebas.
"""
import ast
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import historial
from historial import COLUMNAS_HISTORIAL
from comparar_confluencia_indicadores_fase5_practice import evaluar_confluencia


ROOT = Path(__file__).resolve().parents[1]
NOMBRES = (
    "ema9", "ema21", "bb_superior", "bb_media", "bb_inferior",
)
CAMPOS = NOMBRES + ("precio_cierre_indicadores",)


def extraer_asignacion_snapshot():
    arbol = ast.parse((ROOT / "estrategia.py").read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if (isinstance(destino, ast.Subscript)
                    and isinstance(destino.value, ast.Name)
                    and destino.value.id == "senal"
                    and isinstance(destino.slice, ast.Constant)
                    and destino.slice.value == "indicadores_tecnicos_snapshot_fase5"):
                return compile(ast.Expression(nodo.value), "snapshot", "eval")
    raise AssertionError("Snapshot no producido en estrategia.py")


def extraer_columnas_writer():
    arbol = ast.parse((ROOT / "operaciones.py").read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        if not isinstance(nodo.func, ast.Name) or nodo.func.id != "guardar_historial":
            continue
        if not nodo.args or not isinstance(nodo.args[0], ast.Dict):
            continue
        dic = nodo.args[0]
        return {
            clave.value: valor
            for clave, valor in zip(dic.keys, dic.values)
            if isinstance(clave, ast.Constant) and isinstance(clave.value, str)
        }
    raise AssertionError("No se encontro dict para guardar_historial")


class SnapshotPersistenciaFase5Tests(unittest.TestCase):
    def test_esquema_y_escritor_cubren_mismos_campos(self):
        writer = extraer_columnas_writer()
        for nombre in CAMPOS:
            with self.subTest(campo=nombre):
                self.assertIn(nombre, COLUMNAS_HISTORIAL)
                self.assertIn(nombre, writer)

    def test_snapshot_no_inventa_indicadores_faltantes(self):
        expresion = extraer_asignacion_snapshot()
        ctx = {"ema9": 101, "ema21": 100, "ultima_close": 101.3}
        inicial = dict(ctx)
        snapshot = eval(expresion, {"ctx": ctx})
        self.assertEqual(ctx, inicial)
        self.assertEqual(snapshot["ema9"], 101)
        self.assertEqual(snapshot["ultima_close"], 101.3)
        self.assertIsNone(snapshot["bb_superior"])
        self.assertIsNone(snapshot["rsi"])

    def test_escritor_usa_snapshot_no_recalcula_futuro(self):
        writer = extraer_columnas_writer()
        snapshot = {"ema9": 101, "ema21": 100, "ultima_close": 101.3}
        for campo, esperado in (
            ("ema9", 101), ("ema21", 100),
            ("bb_superior", ""), ("precio_cierre_indicadores", 101.3),
        ):
            with self.subTest(campo=campo):
                valor = eval(
                    compile(ast.Expression(writer[campo]), "writer", "eval"),
                    {"indicadores_fase5": snapshot},
                )
                self.assertEqual(valor, esperado)

    def test_rsi_historial_prioriza_senal_y_recupera_snapshot(self):
        writer = extraer_columnas_writer()
        expr = compile(
            ast.Expression(writer["rsi"]), "rsi_writer", "eval"
        )
        self.assertEqual(
            eval(expr, {"rsi": "", "indicadores_fase5": {"rsi": 48}}),
            48,
        )
        self.assertEqual(
            eval(expr, {"rsi": 53, "indicadores_fase5": {"rsi": 48}}),
            53,
        )
        self.assertEqual(
            eval(expr, {"rsi": "", "indicadores_fase5": {}}),
            "",
        )

    def test_migracion_y_cierre_preservan_order_id_con_ceros(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "historico.csv"
            with ruta.open("w", encoding="utf-8", newline="") as archivo:
                writer = csv.DictWriter(
                    archivo,
                    fieldnames=["fecha", "estado", "order_id", "resultado"],
                )
                writer.writeheader()
                writer.writerow({
                    "fecha": "2026-11-16 10:00:00", "estado": "ABIERTA",
                    "order_id": "000123", "resultado": "",
                })
            with patch.object(historial, "HISTORIAL_CSV", str(ruta)):
                historial.asegurar_historial_csv()
                self.assertTrue(historial.actualizar_historial_cierre("000123", 20.75))
            with ruta.open(encoding="utf-8-sig", newline="") as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertEqual(len(filas), 1)
            self.assertEqual(filas[0]["order_id"], "000123")
            self.assertEqual(filas[0]["estado"], "CERRADA")
            self.assertEqual(float(filas[0]["resultado"]), 20.75)
            self.assertIn("ema9", filas[0])
            self.assertEqual(filas[0]["ema9"], "")

    def test_comparador_reconoce_columnas_futuras(self):
        filas = [{
            "estado": "CERRADA", "order_id": "1",
            "fecha": "2026-11-16T10:00:00",
            "resultado": "20.75", "direccion": "CALL",
            "pa_direccion": "CALL", "patron": "CHOCH",
            "rsi": "50",
            "ema9": "101", "ema21": "100",
            "bb_superior": "105", "bb_media": "100",
            "bb_inferior": "95",
            "precio_cierre_indicadores": "101.3",
        }]
        salida = evaluar_confluencia(filas)
        self.assertEqual(salida["cobertura"]["ema_disponible"], 1)
        self.assertEqual(salida["cobertura"]["rsi_disponible"], 1)
        self.assertEqual(salida["cobertura"]["bb_disponible"], 1)
        self.assertFalse(salida["operaciones_autorizadas"])


if __name__ == "__main__":
    unittest.main()
