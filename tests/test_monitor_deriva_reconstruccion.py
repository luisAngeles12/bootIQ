"""Regresion de reconstruccion de memoria SHADOW, sin IQ ni operaciones."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import monitor_deriva_estrategias as m


class ReconstruccionMonitorTest(unittest.TestCase):
    def setUp(self):
        self.monitor_anterior = m._MONITOR
        m._MONITOR = m.MonitorDerivaSombra()

    def tearDown(self):
        m._MONITOR = self.monitor_anterior

    def escribir(self, ruta, filas):
        with ruta.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["order_id", "patron", "resultado", "estado"]
            )
            writer.writeheader()
            writer.writerows(filas)

    def test_restart_recupera_ventanas_cerradas(self):
        with TemporaryDirectory() as d:
            ruta = Path(d) / "historial.csv"
            filas = [
                {
                    "order_id": str(i),
                    "patron": "CHOCH",
                    "resultado": "20.75" if i < 8 else "-25",
                    "estado": "CERRADA",
                }
                for i in range(16)
            ]
            self.escribir(ruta, filas)
            self.assertEqual(m.reconstruir_monitor_desde_historial(ruta), 16)
            self.assertEqual(
                len(m._MONITOR._resultados["CHOCH"]), 16
            )
            self.assertIsNone(
                m.observar_cierre_sombra("CHOCH", 20.75, "15")
            )
            nuevo = m.observar_cierre_sombra("CHOCH", -25, "16")
            self.assertEqual(nuevo["estado"], "SIN_DETERIORO_DETECTADO")
            self.assertFalse(nuevo["cooldown_activado"])

    def test_abiertas_invalidas_y_duplicadas_no_entran(self):
        with TemporaryDirectory() as d:
            ruta = Path(d) / "historial.csv"
            self.escribir(ruta, [
                {"order_id": "1", "patron": "EMA", "resultado": "20", "estado": "CERRADA"},
                {"order_id": "2", "patron": "EMA", "resultado": "-25", "estado": "ABIERTA"},
                {"order_id": "1", "patron": "EMA", "resultado": "-25", "estado": "CERRADA"},
                {"order_id": "3", "patron": "EMA", "resultado": "NaN", "estado": "CERRADA"},
            ])
            self.assertEqual(m.reconstruir_monitor_desde_historial(ruta), 1)
            self.assertEqual(len(m._MONITOR._resultados["EMA"]), 1)

    def test_archivo_ausente_no_pierde_memoria_actual(self):
        with TemporaryDirectory() as d:
            anterior = m._MONITOR
            m.observar_cierre_sombra("EMA", 20.75, "persistido")
            with self.assertRaises(FileNotFoundError):
                m.reconstruir_monitor_desde_historial(Path(d) / "inexistente.csv")
            self.assertIs(m._MONITOR, anterior)
            self.assertEqual(len(m._MONITOR._resultados["EMA"]), 1)


if __name__ == "__main__":
    unittest.main()
