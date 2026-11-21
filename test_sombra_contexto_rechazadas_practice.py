"""Regresion F12: nuevos campos no destruyen CSV sombra legacy.

Extrae solo constantes y funciones IO para evitar cualquier acceso a IQ.
"""
import ast
import csv
import os
import tempfile
import unittest
from pathlib import Path


def _aislar_io():
    ruta = Path(__file__).with_name("auditoria_candidatas_sombra_practice.py")
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    elegidos = []
    for node in arbol.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in {"COLUMNAS_BASE", "COLUMNAS"}
            for t in node.targets
        ):
            elegidos.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {"_leer", "_guardar"}:
            elegidos.append(node)
    espacio = {"csv": csv, "Path": Path, "os": os}
    exec(compile(ast.fix_missing_locations(ast.Module(body=elegidos, type_ignores=[])),
                 str(ruta), "exec"), espacio)
    return espacio


class RechazadasContextoTests(unittest.TestCase):
    def test_csv_legacy_se_migra_sin_borrar_resultados(self):
        api = _aislar_io()
        self.assertIn("regimen_mercado", api["COLUMNAS"])
        self.assertIn("calidad_setup", api["COLUMNAS"])
        self.assertIn("tipo_setup", api["COLUMNAS"])
        self.assertIn("origen_autoridad", api["COLUMNAS"])
        with tempfile.TemporaryDirectory() as temp:
            ruta = Path(temp) / "sombra.csv"
            with ruta.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=api["COLUMNAS_BASE"])
                writer.writeheader()
                writer.writerow({
                    "id": "antiguo-001", "activo": "EURUSD-OTC",
                    "patron": "CHOCH bajista", "direccion": "put",
                    "decision": "NO_OPERAR", "vela_senal_from": "1730000000",
                    "resultado_hipotetico": "LOSS",
                    "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
                })
            datos = api["_leer"](ruta)
            self.assertEqual(len(datos), 1)
            self.assertEqual(datos[0]["resultado_hipotetico"], "LOSS")
            self.assertEqual(datos[0]["regimen_mercado"], "")
            self.assertEqual(datos[0]["calidad_setup"], "")
            datos[0]["regimen_mercado"] = "TENDENCIA_LIMPIA"
            datos[0]["calidad_setup"] = "BUENA"
            api["_guardar"](ruta, datos)
            restaurado = api["_leer"](ruta)
            self.assertEqual(restaurado[0]["id"], "antiguo-001")
            self.assertEqual(restaurado[0]["resultado_hipotetico"], "LOSS")
            self.assertEqual(restaurado[0]["regimen_mercado"], "TENDENCIA_LIMPIA")
            self.assertEqual(restaurado[0]["calidad_setup"], "BUENA")

    def test_campos_no_autorizan_operaciones(self):
        api = _aislar_io()
        self.assertNotIn("PERMITIR_BOOTSTRAP_SIN_MEMORIA", api["COLUMNAS"])
        self.assertNotIn("autoriza_operaciones", api["COLUMNAS"])


if __name__ == "__main__":
    unittest.main()
