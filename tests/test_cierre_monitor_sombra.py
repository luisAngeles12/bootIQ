"""Prueba de integración del cierre sin importar módulos de bróker."""

import ast
import types
import unittest
from pathlib import Path

from monitor_pausas_contextuales import registrar_cierre_sombra


def preparar_revisor(*, persistir, registrar=registrar_cierre_sombra):
    fuente = Path(__file__).resolve().parents[1] / "operaciones.py"
    arbol = ast.parse(fuente.read_text(encoding="utf-8"), filename=str(fuente))
    funcion = next(
        nodo for nodo in arbol.body
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "revisar_operaciones_abiertas"
    )
    compilado = compile(ast.Module(body=[funcion], type_ignores=[]), str(fuente), "exec")
    estado = types.SimpleNamespace(operaciones_abiertas=[], cooldown_activos={})
    guardados = []
    ambiente = {
        "estado": estado,
        "time": types.SimpleNamespace(time=lambda: 1000),
        "TIEMPO_EXPIRACION": 1,
        "obtener_resultado_operacion": lambda op: None,
        "actualizar_historial_cierre": persistir,
        "registrar_cierre_sombra": registrar,
        "guardar_operaciones_pendientes": lambda: guardados.append(True),
    }
    exec(compilado, ambiente)
    return ambiente["revisar_operaciones_abiertas"], estado, guardados


def operacion():
    return {
        "hora_apertura": 0, "order_id": "id-7", "activo": "AAA",
        "tipo": "turbo", "direccion": "call", "patron": "reaccion",
        "tipo_mercado": "TENDENCIA_ALCISTA", "resultado_pendiente_csv": -25,
    }


class CierreMonitorSombraTests(unittest.TestCase):
    def test_registra_una_vez_tras_persistencia_confirmada(self):
        persistidos = []
        def persistir(identificador, resultado):
            persistidos.append((identificador, resultado))
            return True
        revisar, estado, guardados = preparar_revisor(persistir=persistir)
        estado.operaciones_abiertas = [operacion()]
        revisar()
        self.assertEqual(persistidos, [("id-7", -25)])
        self.assertEqual(estado.operaciones_abiertas, [])
        self.assertEqual(list(estado.cierres_contextuales_sombra[("REACCION", "TENDENCIA_ALCISTA", "CALL")]), [-25])
        self.assertEqual(estado.cooldown_activos, {"AAA": 1000})
        self.assertEqual(len(guardados), 1)

    def test_persistencia_fallida_no_registra_ni_descarta(self):
        revisar, estado, _ = preparar_revisor(persistir=lambda *_: False)
        op = operacion()
        estado.operaciones_abiertas = [op]
        revisar()
        self.assertEqual(estado.operaciones_abiertas, [op])
        self.assertFalse(hasattr(estado, "cierres_contextuales_sombra"))
        self.assertEqual(estado.cooldown_activos, {})

    def test_error_telemetria_no_reabre_operacion(self):
        def fallar(*_, **__):
            raise RuntimeError("telemetria no disponible")
        revisar, estado, _ = preparar_revisor(persistir=lambda *_: True, registrar=fallar)
        estado.operaciones_abiertas = [operacion()]
        revisar()
        self.assertEqual(estado.operaciones_abiertas, [])
        self.assertEqual(estado.cooldown_activos, {"AAA": 1000})


if __name__ == "__main__":
    unittest.main()
