"""Regresion: el CSV sombra se lee una vez por version del archivo.

Se ejecutan funciones reales extraidas por AST; sin importar IQ ni bot.py.
"""
import ast
import csv
import os
import tempfile
import unittest
from pathlib import Path


def _io_real():
    ruta = Path(__file__).with_name("auditoria_candidatas_sombra_practice.py")
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    nodos = []
    for n in arbol.body:
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in {"COLUMNAS_BASE", "COLUMNAS"}
            for t in n.targets
        ):
            nodos.append(n)
        elif isinstance(n, ast.FunctionDef) and n.name in {"_leer", "_guardar"}:
            nodos.append(n)
    entorno = {"csv": csv, "os": os, "Path": Path, "_CACHE_EVENTOS": {}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodos, type_ignores=[])),
                 str(ruta), "exec"), entorno)
    return entorno


class CacheSombraPracticeTests(unittest.TestCase):
    def test_relectura_reutiliza_cache_y_registro_guardado(self):
        io = _io_real()
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "sombra.csv"
            original = [{"id": "A", "activo": "EURUSD-OTC", "decision": "NO_OPERAR"}]
            io["_guardar"](archivo, original)
            primero = io["_leer"](archivo)
            segundo = io["_leer"](archivo)
            self.assertIs(primero, segundo)
            self.assertEqual(primero[0]["id"], "A")
            primero.append({"id": "B", "activo": "AUDCAD-OTC", "decision": "NO_OPERAR"})
            io["_guardar"](archivo, primero)
            self.assertEqual([r["id"] for r in io["_leer"](archivo)], ["A", "B"])

    def test_modificacion_externa_invalida_cache(self):
        io = _io_real()
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "sombra.csv"
            io["_guardar"](archivo, [{"id": "A", "decision": "NO_OPERAR"}])
            antes = io["_leer"](archivo)
            with archivo.open("a", encoding="utf-8") as f:
                f.write("otro-registro,EURUSD-OTC\n")
            despues = io["_leer"](archivo)
            self.assertIsNot(antes, despues)
            self.assertEqual(len(despues), 2)

    def test_archivo_borrado_no_devuelve_datos_obsoletos(self):
        io = _io_real()
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "sombra.csv"
            io["_guardar"](archivo, [{"id": "A"}])
            self.assertEqual(len(io["_leer"](archivo)), 1)
            archivo.unlink()
            self.assertEqual(io["_leer"](archivo), [])


if __name__ == "__main__":
    unittest.main()
