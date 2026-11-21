"""Ejecuta la funcion real de clasificacion de pendientes sin importar broker.

Extrae AST de entrada.py: las dependencias LIVE de importacion no participan
en esta funcion pura de clasificacion. No manda ordenes ni lee cuentas.
"""
import ast
import unittest
from pathlib import Path


def _cargar_clasificador_real():
    ruta = Path(__file__).with_name("entrada.py")
    modulo = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    funcion = next(
        nodo for nodo in modulo.body
        if isinstance(nodo, ast.FunctionDef)
        and nodo.name == "motivo_pendiente_por_accion_precio"
    )
    aislado = ast.fix_missing_locations(ast.Module(body=[funcion], type_ignores=[]))
    entorno = {
        "_bool": lambda v, default=False: default if v is None else bool(v),
    }
    exec(compile(aislado, str(ruta), "exec"), entorno)
    return entorno[funcion.name]


motivo = _cargar_clasificador_real()


class ReaccionTildeTests(unittest.TestCase):
    def base(self, patron):
        return {
            "direccion": "call", "patron": patron,
            "tipo_setup": "INDEFINIDO", "calidad_setup": "MEDIA",
            "pa_tipo": "SIN_CONTEXTO_CLARO", "pa_direccion": "NEUTRA",
        }

    def test_reaccion_con_y_sin_tilde_requiere_confirmacion(self):
        for patron in ("reaccion compradora en soporte",
                       "reacción compradora en soporte"):
            with self.subTest(patron=patron):
                self.assertEqual(motivo(self.base(patron)),
                                 "ESPERANDO_CONFIRMACION_RECHAZO")

    def test_premium_no_cambia_por_correccion_textual(self):
        for patron in ("reaccion compradora", "reacción compradora"):
            senal = self.base(patron)
            senal["calidad_setup"] = "PREMIUM"
            self.assertIsNone(motivo(senal))

    def test_veto_critico_y_ruptura_siguen_prioritarios(self):
        senal = self.base("reacción compradora")
        senal["riesgo_estructural_critico_setup"] = True
        self.assertEqual(motivo(senal), "CANCELAR_PROTOCOLO_RIESGO_CRITICO")
        senal = self.base("reacción compradora")
        senal["accion_precio"] = "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
        self.assertEqual(motivo(senal), "ESPERANDO_RUPTURA_RESISTENCIA")


if __name__ == "__main__":
    unittest.main()
