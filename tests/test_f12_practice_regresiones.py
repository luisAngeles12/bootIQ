"""Incluye regresiones F12 en el comando oficial de pruebas local.

El proyecto ejecuta habitualmente:
    python -m unittest discover -s tests -q
Los tests F12 viven en la raiz por compatibilidad con CI, por lo que
sin este puente aquel comando los omitia completamente.
"""
import importlib
import unittest


MODULOS_F12 = (
    "test_auditar_calidad_setup_practice",
    "test_latencia_practice",
    "test_entrada_reaccion_tilde_practice",
    "test_setup_mercado_sucio_practice",
    "test_regimen_mercado_sucio_practice",
    "test_diagnostico_inactividad_practice",
    "test_validar_hipotesis_sombra_oos_practice",
    "test_preparacion_practice_v3",
    "test_evaluar_evidencia_inicio_practice",
    "test_sombra_contexto_rechazadas_practice",
    "test_muestra_independiente_practice",
    "test_ventaja_oos_baseline_practice",
    "test_sombra_timestamp_corrupto_practice",
)


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for nombre in MODULOS_F12:
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(nombre)))
    return suite
