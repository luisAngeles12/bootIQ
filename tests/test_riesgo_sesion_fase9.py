"""Regresiones F9: stops anteriores a pendientes, sin red ni trading."""
import unittest
from pathlib import Path

from riesgo_sesion import motivo_bloqueo_sesion


class RiesgoSesionFase9Tests(unittest.TestCase):
    def test_stop_loss_con_ultimo_balance_conocido(self):
        self.assertEqual(
            motivo_bloqueo_sesion(1000, 0, -1000, 3000),
            "STOP_LOSS",
        )
        self.assertIsNone(motivo_bloqueo_sesion(1000, 1, -1000, 3000))

    def test_stop_win_con_ultimo_balance_conocido(self):
        self.assertEqual(
            motivo_bloqueo_sesion(1000, 4000, -1000, 3000),
            "STOP_WIN",
        )
        self.assertIsNone(motivo_bloqueo_sesion(1000, 3999.99, -1000, 3000))

    def test_sin_balance_y_no_finito_no_se_interpreta_como_cero(self):
        for inicial, actual in (
            (None, 1000), (1000, None),
            (float("nan"), 1000), (1000, float("inf")),
            (1000, -1),
        ):
            with self.subTest(inicial=inicial, actual=actual):
                self.assertIsNotNone(
                    motivo_bloqueo_sesion(inicial, actual, -1000, 3000)
                )

    def test_guardia_no_invoca_broker(self):
        import inspect
        import riesgo_sesion

        codigo = inspect.getsource(riesgo_sesion.motivo_bloqueo_sesion)
        self.assertNotIn("get_balance(", codigo)
        self.assertNotIn("estado.Iq", codigo)

    def test_revision_previa_a_procesar_pendientes(self):
        # Contrato de orden de ejecución: parada antes de pendientes.
        codigo = (Path(__file__).resolve().parents[1] / "bot.py").read_text(
            encoding="utf-8"
        )
        main = codigo[codigo.index("def main():"):]
        inicio = main.index("while True:")
        cuerpo = main[inicio:]
        self.assertLess(
            cuerpo.index("bloqueo_previo_sesion = motivo_bloqueo_sesion("),
            cuerpo.index("procesar_senales_pendientes("),
        )
        self.assertLess(
            cuerpo.index("if bloqueo_previo_sesion is not None:"),
            cuerpo.index("procesar_senales_pendientes("),
        )


if __name__ == "__main__":
    unittest.main()
