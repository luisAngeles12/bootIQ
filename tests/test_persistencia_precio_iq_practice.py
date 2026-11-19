"""Persistencia de metadatos IQ a cierre: aislamiento por order_id.

Carga solo la funcion de cierre desde AST; no importa pandas ni broker.
"""
import ast
import csv
import math
import os
import tempfile
import unittest
from pathlib import Path

import auditoria_precio_iq_practice as audit


def cargar_cierre(ruta_csv):
    origen = Path(__file__).resolve().parents[1] / "historial.py"
    arbol = ast.parse(origen.read_text(encoding="utf-8"))
    fn = next(n for n in arbol.body if isinstance(n, ast.FunctionDef)
              and n.name == "actualizar_historial_cierre")
    env = {
        "os": os, "csv": csv, "math": math, "tempfile": tempfile,
        "HISTORIAL_CSV": str(ruta_csv),
        "asegurar_historial_csv": lambda: (_ for _ in ()).throw(
            AssertionError("No debe reconstruir historial existente")
        ),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[fn], type_ignores=[]
    )), str(origen), "exec"), env)
    return env["actualizar_historial_cierre"]


class PersistenciaPrecioTest(unittest.TestCase):
    def crear(self, ruta):
        with ruta.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "order_id", "estado", "resultado",
                "auditoria_orden_iq_json", "modo_cuenta_configurado",
                "fecha_conciliacion_local_utc",
            ])
            w.writeheader()
            w.writerows([
                {"order_id": "100", "estado": "ABIERTA", "resultado": "",
                 "auditoria_orden_iq_json": "", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "101", "estado": "ABIERTA", "resultado": "",
                 "auditoria_orden_iq_json": "", "modo_cuenta_configurado": "PRACTICE"},
            ])

    def leer(self, ruta):
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def test_cierre_anade_solo_a_orden_correspondiente(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial.csv"
            self.crear(ruta)
            cierre = cargar_cierre(ruta)
            payload = audit.extraer_precios_eventos("100", {
                "option-opened": {"msg": {"option_id": 100, "open_price": 1.23}},
                "option-closed": {"msg": {"option_id": 100, "close_price": 1.24}},
            })
            self.assertTrue(cierre("100", -25, auditoria_orden_iq_json=payload))
            filas = self.leer(ruta)
            self.assertEqual(filas[0]["resultado"], "-25.0")
            self.assertEqual(filas[0]["estado"], "CERRADA")
            self.assertEqual(filas[0]["auditoria_orden_iq_json"], payload)
            self.assertEqual(filas[1]["estado"], "ABIERTA")
            self.assertEqual(filas[1]["resultado"], "")
            self.assertEqual(filas[1]["auditoria_orden_iq_json"], "")
            # El cierre siguiente sin payload no inventa datos.
            self.assertTrue(cierre("101", 20.75))
            self.assertEqual(self.leer(ruta)[1]["auditoria_orden_iq_json"], "")

    def test_no_altera_csv_si_order_id_no_existe(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial.csv"
            self.crear(ruta)
            antes = ruta.read_bytes()
            cierre = cargar_cierre(ruta)
            self.assertFalse(cierre("999", -25, auditoria_orden_iq_json="{}"))
            self.assertEqual(ruta.read_bytes(), antes)

    def test_no_altera_csv_si_resultado_no_es_finito(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial.csv"
            self.crear(ruta)
            antes = ruta.read_bytes()
            cierre = cargar_cierre(ruta)
            self.assertFalse(cierre("100", math.nan))
            self.assertEqual(ruta.read_bytes(), antes)


    def test_marca_utc_se_persiste_solo_en_order_id_cerrada(self):
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial.csv"
            self.crear(ruta)
            cierre = cargar_cierre(ruta)
            self.assertTrue(cierre("100", -25))
            filas = self.leer(ruta)
            marca = filas[0]["fecha_conciliacion_local_utc"]
            fecha = datetime.fromisoformat(marca)
            self.assertIsNotNone(fecha.utcoffset())
            self.assertEqual(fecha.utcoffset().total_seconds(), 0)
            self.assertEqual(filas[1]["fecha_conciliacion_local_utc"], "")
            self.assertEqual(filas[1]["estado"], "ABIERTA")
            # Una segunda persistencia no reescribe la marca original.
            self.assertTrue(cierre("100", -25))
            self.assertEqual(self.leer(ruta)[0]["fecha_conciliacion_local_utc"], marca)

    def test_fallo_reemplazo_no_publica_marca_utc(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial.csv"
            self.crear(ruta)
            antes = ruta.read_bytes()
            cierre = cargar_cierre(ruta)
            with patch("os.replace", side_effect=OSError("interrumpido")):
                self.assertFalse(cierre("100", 20.75))
            self.assertEqual(ruta.read_bytes(), antes)
            self.assertEqual(self.leer(ruta)[0]["fecha_conciliacion_local_utc"], "")

    def test_historico_sin_nueva_columna_conserva_compatibilidad(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial_legacy.csv"
            with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
                writer = csv.DictWriter(archivo, fieldnames=[
                    "order_id", "estado", "resultado",
                ])
                writer.writeheader()
                writer.writerow({"order_id": "001", "estado": "ABIERTA", "resultado": ""})
            cierre = cargar_cierre(ruta)
            self.assertTrue(cierre("001", 21.25))
            self.assertEqual(self.leer(ruta)[0]["estado"], "CERRADA")
            self.assertEqual(self.leer(ruta)[0]["resultado"], "21.25")
            self.assertNotIn("fecha_conciliacion_local_utc", self.leer(ruta)[0])


if __name__ == "__main__":
    unittest.main()
