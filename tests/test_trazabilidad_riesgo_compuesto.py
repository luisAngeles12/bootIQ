"""Fase 4.10: persistencia prospectiva del riesgo original, solo telemetria."""
import ast
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import historial

ROOT = Path(__file__).resolve().parents[1]
CAMPO = "auditoria_riesgo_compuesto_json"


def arbol(nombre):
    return ast.parse((ROOT / nombre).read_text(encoding="utf-8-sig"))


class TrazabilidadRiesgoCompuestoTests(unittest.TestCase):
    def test_esquema_incluye_snapshot(self):
        self.assertIn(CAMPO, historial.COLUMNAS_HISTORIAL)

    def test_migracion_historica_no_inventa_riesgo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "historial.csv"
            with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
                writer = csv.DictWriter(archivo, fieldnames=["order_id", "resultado"])
                writer.writeheader()
                writer.writerow({"order_id": "antigua", "resultado": "-25"})
            with patch.object(historial, "HISTORIAL_CSV", str(ruta)):
                historial.asegurar_historial_csv()
            with ruta.open(newline="", encoding="utf-8-sig") as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertEqual(filas[0]["order_id"], "antigua")
            self.assertEqual(filas[0]["resultado"], "-25")
            self.assertEqual(filas[0][CAMPO], "")

    def test_snapshot_original_se_registra_sin_recalcularlo(self):
        ar = arbol("decision_bootiq.py")
        asignaciones = [
            node for node in ast.walk(ar)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Subscript)
                and isinstance(t.value, ast.Name)
                and t.value.id == "senal"
                and isinstance(t.slice, ast.Constant)
                and t.slice.value == "auditoria_riesgo_compuesto"
                for t in node.targets
            )
        ]
        self.assertEqual(len(asignaciones), 1)
        asignacion = asignaciones[0].value
        self.assertIsInstance(asignacion, ast.Call)
        self.assertIsInstance(asignacion.func, ast.Name)
        self.assertEqual(asignacion.func.id, "dict")
        self.assertEqual(asignacion.args[0].id, "riesgo_compuesto")

        op = arbol("operaciones.py")
        registros = [
            node.args[0] for node in ast.walk(op)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "guardar_historial"
            and node.args and isinstance(node.args[0], ast.Dict)
        ]
        self.assertTrue(registros)
        campos = {
            k.value: v for k, v in zip(registros[0].keys, registros[0].values)
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        }
        self.assertIn(CAMPO, campos)
        self.assertTrue(any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "dumps"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "json"
            for n in ast.walk(campos[CAMPO])
        ))

    def test_json_original_puede_guardarse_y_leerse(self):
        esperado = {
            "riesgo_puntos": 2,
            "riesgo_nivel": "BAJO",
            "bloquear_por_riesgo": False,
            "motivos_riesgo": ["cerca de soporte"],
            "categorias_riesgo": ["entrada_contra_nivel"],
        }
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "historial.csv"
            with patch.object(historial, "HISTORIAL_CSV", str(ruta)):
                historial.guardar_historial({
                    "order_id": "prueba",
                    CAMPO: json.dumps(esperado, ensure_ascii=False, sort_keys=True),
                })
            with ruta.open(newline="", encoding="utf-8-sig") as archivo:
                fila = next(csv.DictReader(archivo))
            self.assertEqual(json.loads(fila[CAMPO]), esperado)


if __name__ == "__main__":
    unittest.main()
