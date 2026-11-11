"""Fase 4.9: trazabilidad prospectiva PA, sin broker ni ordenes."""
import ast
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import historial


CAMPOS_PA = (
    "validacion_accion_precio_ok",
    "razon_validacion_accion_precio",
    "riesgos_base",
)


class TrazabilidadPAHistorialTests(unittest.TestCase):
    def test_esquema_incluye_campos_pa(self):
        for campo in CAMPOS_PA:
            with self.subTest(campo=campo):
                self.assertIn(campo, historial.COLUMNAS_HISTORIAL)

    def test_migracion_conserva_historico_y_deja_pa_desconocido(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "historial.csv"
            with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
                escritor = csv.DictWriter(
                    archivo, fieldnames=["order_id", "estado", "resultado"]
                )
                escritor.writeheader()
                escritor.writerow({
                    "order_id": "orden_antigua",
                    "estado": "CERRADA",
                    "resultado": "-25",
                })
            with patch.object(historial, "HISTORIAL_CSV", str(ruta)):
                historial.asegurar_historial_csv()
            with ruta.open(newline="", encoding="utf-8-sig") as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertEqual(len(filas), 1)
            self.assertEqual(filas[0]["order_id"], "orden_antigua")
            self.assertEqual(filas[0]["resultado"], "-25")
            for campo in CAMPOS_PA:
                self.assertEqual(filas[0][campo], "")

    def test_guardado_nuevo_preserva_validacion_negativa(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "historial.csv"
            with patch.object(historial, "HISTORIAL_CSV", str(ruta)):
                historial.guardar_historial({
                    "order_id": "orden_prueba",
                    "validacion_accion_precio_ok": False,
                    "razon_validacion_accion_precio": "rechazo explicito",
                    "riesgos_base": "ACCION_PRECIO_NO_VALIDADA",
                })
            with ruta.open(newline="", encoding="utf-8-sig") as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertEqual(len(filas), 1)
            self.assertEqual(filas[0]["validacion_accion_precio_ok"], "False")
            self.assertEqual(
                filas[0]["razon_validacion_accion_precio"],
                "rechazo explicito",
            )
            self.assertEqual(filas[0]["riesgos_base"], "ACCION_PRECIO_NO_VALIDADA")

    def test_operaciones_transfiere_campos_pa_desde_senal(self):
        arbol = ast.parse(
            (Path(__file__).resolve().parents[1] / "operaciones.py").read_text(
                encoding="utf-8-sig"
            )
        )
        registros = [
            nodo.args[0]
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Name)
            and nodo.func.id == "guardar_historial"
            and nodo.args
            and isinstance(nodo.args[0], ast.Dict)
        ]
        self.assertTrue(registros)
        claves = {
            clave.value: valor
            for clave, valor in zip(registros[0].keys, registros[0].values)
            if isinstance(clave, ast.Constant) and isinstance(clave.value, str)
        }
        for campo in CAMPOS_PA:
            with self.subTest(campo=campo):
                self.assertIn(campo, claves)
                valor = claves[campo]
                self.assertIsInstance(valor, ast.Call)
                self.assertIsInstance(valor.func, ast.Attribute)
                self.assertEqual(valor.func.attr, "get")
                self.assertIsInstance(valor.func.value, ast.Name)
                self.assertEqual(valor.func.value.id, "senal")
                self.assertEqual(valor.args[0].value, campo)


if __name__ == "__main__":
    unittest.main()
