"""Reproduccion OOS de octubre 2, aislada y sin credenciales reales."""
import collections
import contextlib
import csv
import io
import os
import sys
import tempfile
import types
import unittest


class ReplayOct02Tests(unittest.TestCase):
    def test_replay_congelado_no_conecta_broker(self):
        # La prueba nunca importa las credenciales privadas.
        credenciales = types.ModuleType("credenciales_local")
        credenciales.EMAIL = ""
        credenciales.PASSWORD = ""
        anterior = sys.modules.get("credenciales_local")
        sys.modules["credenciales_local"] = credenciales
        try:
            import config
            import backtest_bot_real as bt
        finally:
            if anterior is None:
                sys.modules.pop("credenciales_local", None)
            else:
                sys.modules["credenciales_local"] = anterior

        self.assertEqual(config.MODO_CUENTA, "PRACTICE")
        self.assertEqual(bt.MODO_EXPERIMENTO, "OUT_OF_SAMPLE")
        self.assertEqual(bt.MODO_BACKTEST, "FILTRADO")
        self.assertFalse(bt.ACTUALIZAR_APRENDIZAJE)
        self.assertFalse(bt.ACTUALIZAR_APRENDIZAJE_PROTOCOLO)
        self.assertEqual(len(bt.cargar_datasets()), 17)

        original_salida = bt.SALIDA
        try:
            with tempfile.TemporaryDirectory(prefix="fase2_oos_oct02_") as temporal:
                bt.SALIDA = os.path.join(temporal, "replay.csv")
                with contextlib.redirect_stdout(io.StringIO()):
                    bt.main()
                with open(bt.SALIDA, encoding="utf-8-sig", newline="") as archivo:
                    filas = list(csv.DictReader(archivo))
        finally:
            bt.SALIDA = original_salida

        self.assertEqual(len(filas), 39)
        self.assertEqual(
            collections.Counter(f.get("estado_operacion") for f in filas),
            {"CANCELADA_CEREBRO": 39},
        )
        fuente = (
            "CONTEXTO_SETUP|CALL|REVERSIÓN_ESTRUCTURAL|CHOCH_ALCISTA"
            "|CHOCH_CON_PA_A_FAVOR|TENDENCIA"
        )
        candidatos = [
            f for f in filas
            if f.get("decision_estadistica_sombra") == "OPERAR_SOMBRA"
            and f.get("clave_probabilidad_principal") == fuente
        ]
        self.assertEqual(len(candidatos), 5)
        self.assertEqual(
            collections.Counter(f.get("resultado_hipotetico") for f in candidatos),
            {"WIN": 1, "LOSS": 4},
        )


if __name__ == "__main__":
    unittest.main()
