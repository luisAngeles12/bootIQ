"""Regresiones: CSV sombra defectuoso no detiene el scanner PRACTICE.

Ejecuta la función real aislada por AST. Nunca importa IQ Option.
"""
import ast
import unittest
from pathlib import Path


def _resolver_real(registros):
    path = Path(__file__).with_name("auditoria_candidatas_sombra_practice.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    f = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == "resolver_candidatas")
    guardados = []
    entorno = {
        "_leer": lambda _: registros,
        "_guardar": lambda _, filas: guardados.append([dict(x) for x in filas]),
        "RUTA_EVENTOS": "NO_USAR.csv",
    }
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[f], type_ignores=[])), str(path), "exec"), entorno)
    return entorno[f.name], guardados


class TimestampsSombraPracticeTests(unittest.TestCase):
    def test_fila_mala_no_impide_resolver_siguiente_fila(self):
        t = 1800000000
        filas = [
            {"activo": "EURUSD-OTC", "vela_senal_from": "INEXISTENTE",
             "resultado_hipotetico": "", "calidad_tiempo": "PENDIENTE_VELA_POSTERIOR"},
            {"activo": "EURUSD-OTC", "vela_senal_from": str(t - 60),
             "resultado_hipotetico": "", "direccion": "call",
             "calidad_tiempo": "PENDIENTE_VELA_POSTERIOR"},
        ]
        resolver, guardados = _resolver_real(filas)
        ctx = {
            "froms": [t - 120, t - 60, t],
            "opens": [1.0, 1.0, 1.0],
            "closes": [1.0, 1.0, 1.1],
            "vela_senal_from": t,
        }
        self.assertEqual(resolver("EURUSD-OTC", ctx), 2)
        self.assertEqual(filas[0]["calidad_tiempo"], "TIMESTAMP_SENAL_INVALIDO")
        self.assertEqual(filas[0]["resultado_hipotetico"], "")
        self.assertEqual(filas[1]["resultado_hipotetico"], "WIN")
        self.assertEqual(filas[1]["calidad_tiempo"],
                         "HIPOTETICO_VELA_COMPLETA_SIN_FILL")
        self.assertEqual(len(guardados), 1)

    def test_registro_invalido_no_interrumpe_ejecucion(self):
        ruta = Path(__file__).with_name("auditoria_candidatas_sombra_practice.py")
        modulo = ast.parse(ruta.read_text(encoding="utf-8"))
        funcion = next(n for n in modulo.body if isinstance(n, ast.FunctionDef)
                       and n.name == "registrar_candidata")
        entorno = {"RUTA_EVENTOS": "NO_USAR.csv"}
        exec(compile(ast.fix_missing_locations(ast.Module(
            body=[funcion], type_ignores=[])), str(ruta), "exec"), entorno)
        registrar = entorno["registrar_candidata"]
        senal = {
            "activo": "EURUSD-OTC", "patron": "RECHAZO",
            "direccion": "call", "vela_senal_from": "TIMESTAMP_CORRUPTO",
            "decision_unificada_accion": "NO_OPERAR",
        }
        self.assertFalse(registrar(senal, {"activo": "EURUSD-OTC"}))

    def test_buffer_con_timestamp_invalido_no_rompe_analisis(self):
        filas = [{"activo": "EURUSD-OTC", "vela_senal_from": "1800000000",
                  "resultado_hipotetico": ""}]
        resolver, guardados = _resolver_real(filas)
        ctx = {"froms": [1800000000, "MALO"], "opens": [1, 1],
               "closes": [1, 1], "vela_senal_from": 1800000060}
        self.assertEqual(resolver("EURUSD-OTC", ctx), 0)
        self.assertFalse(guardados)
        self.assertFalse(filas[0]["resultado_hipotetico"])


if __name__ == "__main__":
    unittest.main()
