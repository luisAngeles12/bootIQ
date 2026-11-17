"""R9-04: correlación sombra de cierre persistido y balance observado."""
import unittest
from pathlib import Path

from riesgo_sesion import secuencia_balance_tras_cierre


class SecuenciaBalanceCierreFase9Tests(unittest.TestCase):
    def test_orden_temporal_y_faltantes(self):
        self.assertEqual(
            secuencia_balance_tras_cierre(None, 100),
            "SIN_CIERRE_CONCILIADO",
        )
        self.assertEqual(
            secuencia_balance_tras_cierre(100, None),
            "SIN_LECTURA_BALANCE",
        )
        self.assertEqual(
            secuencia_balance_tras_cierre(101, 100),
            "BALANCE_ANTERIOR_AL_CIERRE",
        )
        self.assertEqual(
            secuencia_balance_tras_cierre(100, 101),
            "RESPUESTA_BALANCE_POSTERIOR_AL_CIERRE",
        )

    def test_marcas_invalidas_no_producen_falso_orden(self):
        for c, b in [
            (float("nan"), 100),
            (100, float("inf")),
            (-1, 100),
            ("invalida", 101),
        ]:
            with self.subTest(cierre=c, balance=b):
                self.assertEqual(
                    secuencia_balance_tras_cierre(c, b),
                    "MARCAS_INVALIDAS",
                )

    def test_marca_cierre_solo_despues_persistencia(self):
        archivo = (Path(__file__).resolve().parents[1] / "operaciones.py").read_text(
            encoding="utf-8"
        )
        cuerpo = archivo[archivo.index("def revisar_operaciones_abiertas():"):]
        self.assertLess(
            cuerpo.index("if not cierre_persistido:"),
            cuerpo.index("ultima_conciliacion_cierre_monotonic = time.monotonic()"),
        )

    def test_telemetria_no_modifica_timing_ni_autorizacion(self):
        archivo = (Path(__file__).resolve().parents[1] / "bot.py").read_text(
            encoding="utf-8"
        )
        main = archivo[archivo.index("def main():"):]
        self.assertLess(
            main.index("R9-04 SOMBRA SECUENCIA CIERRE BALANCE:"),
            main.index("procesar_senales_pendientes("),
        )
        self.assertIn("ultimo_bucket_telemetria_balance", main)
        self.assertNotIn("if secuencia_balance_tras_cierre(", main)


if __name__ == "__main__":
    unittest.main()
