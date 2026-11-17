"""Fase 9 R9-03: antigüedad de balance solo en telemetría sombra."""
import unittest
from pathlib import Path

from riesgo_sesion import antiguedad_observacion_balance


class AntiguedadBalanceFase9Tests(unittest.TestCase):
    def test_edad_monotonica_valida(self):
        self.assertEqual(antiguedad_observacion_balance(100.0, 117.125), 17.125)

    def test_sin_lectura_o_reloj_invalido(self):
        casos = [
            (None, 10),
            (float("nan"), 10),
            (10, float("inf")),
            (11, 10),
            (-1, 10),
        ]
        for ultima, ahora in casos:
            with self.subTest(ultima=ultima, ahora=ahora):
                self.assertIsNone(antiguedad_observacion_balance(ultima, ahora))

    def test_telemetria_antes_de_pendientes_y_sin_veto_por_edad(self):
        codigo = (Path(__file__).resolve().parents[1] / "bot.py").read_text(
            encoding="utf-8"
        )
        main = codigo[codigo.index("def main():"):]
        self.assertLess(
            main.index("R9-03 SOMBRA ANTIGUEDAD BALANCE"),
            main.index("procesar_senales_pendientes("),
        )
        self.assertIn("ultimo_bucket_telemetria_balance", main)
        self.assertNotIn("if edad_balance", main)

    def test_solo_lectura_correcta_actualiza_instante(self):
        codigo = (Path(__file__).resolve().parents[1] / "bot.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "if math.isfinite(nuevo_balance) and nuevo_balance >= 0:\n"
            "                        ultima_observacion_balance_monotonic = time.monotonic()",
            codigo,
        )
        self.assertIn(
            "ultima_observacion_balance_monotonic = (",
            codigo,
        )


if __name__ == "__main__":
    unittest.main()
