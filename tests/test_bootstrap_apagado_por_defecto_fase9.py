"""R9-25.20: invariantes PRACTICE de la configuracion versionada.

Sin cuenta, sin broker, sin bot.py: impide reactivar bootstrap por accidente.
"""
import ast
import unittest
from pathlib import Path

import bootstrap_practice
import config


class BootstrapDefaultPracticeTests(unittest.TestCase):
    def test_configuracion_oficial_solo_practice_y_sin_bootstrap(self):
        self.assertEqual(config.MODO_CUENTA, "PRACTICE")
        self.assertIs(config.PERMITIR_BOOTSTRAP_SIN_MEMORIA, False)

    def test_bootstrap_inutilizable_ante_decision_sin_memoria(self):
        # No necesitamos construir una señal para demostrar el veto;
        # la excepción apagada tiene precedencia absoluta.
        evidencia = {
            "calidad_mercado": "NORMAL",
            "validacion_mercado_ok": True,
            "validacion_accion_precio_ok": True,
            "validacion_zona_sr_ok": True,
            "accion_precio": "CALL_ZONA_NEUTRA",
            "modo_entrada_setup": "DIRECTA",
            "prioridad": 999,
        }
        decision = {
            "decision": "NO_OPERAR",
            "bloquear_por_riesgo": False,
            "riesgo_compuesto": {"bloquear_por_riesgo": False},
            "resultado_decision_estadistica_sombra":
                {"decision": "SIN_DATOS_ESTADISTICOS"},
            "resultado_decision_oficial":
                {"motivo": "Sin fuente histórica principal utilizable."},
        }
        self.assertFalse(bootstrap_practice.habilitable_sin_memoria(
            evidencia, decision
        ))

    def test_archivo_config_versionado_no_redefine_modo_ni_permiso(self):
        arbol = ast.parse((Path(__file__).resolve().parents[1] / "config.py")
                          .read_text(encoding="utf-8"))
        asignaciones = {}
        for nodo in arbol.body:
            if isinstance(nodo, ast.Assign):
                for destino in nodo.targets:
                    if isinstance(destino, ast.Name):
                        asignaciones.setdefault(destino.id, []).append(nodo.value)
        for nombre, literal in (
            ("MODO_CUENTA", "PRACTICE"),
            ("PERMITIR_BOOTSTRAP_SIN_MEMORIA", False),
        ):
            asignadas = asignaciones.get(nombre, [])
            self.assertEqual(len(asignadas), 1, nombre)
            self.assertEqual(ast.literal_eval(asignadas[0]), literal)


if __name__ == "__main__":
    unittest.main()
