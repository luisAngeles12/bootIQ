"""Contrato de persistencia Fase 5, solo lectura, sin broker.

Se verifica el codigo real mediante AST para evitar importar IQ Option,
iniciar el bot o escribir historial de usuario durante las pruebas.
"""
import ast
from pathlib import Path
import unittest

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
