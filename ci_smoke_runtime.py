"""Smoke import sin credenciales reales ni conexión al bróker."""
import sys
from pathlib import Path
from types import ModuleType

# Archivo confidencial ausente en CI, sustitución únicamente en memoria.
credenciales = ModuleType("credenciales_local")
credenciales.EMAIL = ""
credenciales.PASSWORD = ""
sys.modules["credenciales_local"] = credenciales

import config
assert config.MODO_CUENTA == "PRACTICE"

import bot
assert callable(bot.main)

import backtest_bot_real as backtest
assert backtest.CARPETA_DATA == "data_backtest_actual"
assert not Path(backtest.CARPETA_DATA).exists()
try:
    backtest.cargar_datasets()
except FileNotFoundError as exc:
    assert "SIN_DATOS_ACTUALES" in str(exc)
else:
    raise AssertionError("El backtest no rechazó la carpeta ausente")

from historial import cargar_historial
assert cargar_historial() is None
print("RUNTIME_IMPORT_OK", "cuenta=PRACTICE", "sin credenciales/datos/broker")
