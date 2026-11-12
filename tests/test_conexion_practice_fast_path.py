"""Regresiones del fast path de reconexion PRACTICE sin red."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def cargar_conexion_aislada(iq, modo="PRACTICE"):
    estado = types.ModuleType("estado")
    estado.Iq = iq
    config = types.ModuleType("config")
    config.EMAIL = "sin_uso"
    config.PASSWORD = "sin_uso"
    config.MODO_CUENTA = modo
    paquete = types.ModuleType("iqoptionapi")
    paquete.__path__ = []
    estable = types.ModuleType("iqoptionapi.stable_api")
    estable.IQ_Option = Mock()
    spec = importlib.util.spec_from_file_location(
        "conexion_aislada_para_test",
        Path(__file__).resolve().parents[1] / "conexion.py",
    )
    modulo = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        "estado": estado,
        "config": config,
        "iqoptionapi": paquete,
        "iqoptionapi.stable_api": estable,
    }):
        spec.loader.exec_module(modulo)
    return modulo


class ReconectarPracticeTests(unittest.TestCase):
    def test_fast_path_solo_acepta_practice_confirmado(self):
        iq = Mock()
        iq.check_connect.return_value = True
        iq.get_balance_mode.return_value = "PRACTICE"
        conexion = cargar_conexion_aislada(iq)
        self.assertTrue(conexion.reconectar_iq())
        iq.connect.assert_not_called()

    def test_websocket_vivo_en_real_no_se_acepta_como_practice(self):
        iq = Mock()
        iq.check_connect.return_value = True
        iq.get_balance_mode.return_value = "REAL"
        iq.connect.return_value = (False, "WEBSOCKET_OPEN_TIMEOUT")
        conexion = cargar_conexion_aislada(iq)
        with patch.object(conexion.time, "sleep"):
            self.assertFalse(conexion.reconectar_iq(intentos=1))
        iq.connect.assert_called_once()
        iq.change_balance.assert_not_called()

    def test_configuracion_real_bloqueada_antes_de_conectar(self):
        iq = Mock()
        conexion = cargar_conexion_aislada(iq, modo="REAL")
        self.assertFalse(conexion.reconectar_iq())
        iq.connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
