"""Pruebas integradas F11/F12 sin broker ni datos del usuario."""
import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from informe_integral_fases11_12_practice import informe

COLUMNAS = ["order_id", "fecha_cierre", "resultado", "neto",
            "familia", "tipo_cuenta", "estado"]


def crear(d, n=40, losses=8):
    ruta = Path(d) / "ledger.csv"
    inicio = datetime(2026, 11, 18, tzinfo=timezone.utc)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for i in range(n):
            win = i % 20 >= losses
            w.writerow({
                "order_id": str(i + 1),
                "fecha_cierre": (inicio + timedelta(minutes=i)).isoformat(),
                "resultado": "WIN" if win else "LOSS",
                "neto": "20.75" if win else "-25",
                "familia": "resistencia",
                "tipo_cuenta": "PRACTICE", "estado": "CERRADA",
            })
    return ruta


class InformeIntegralTest(unittest.TestCase):
    def test_sin_archivo_no_crea_certificacion(self):
        with tempfile.TemporaryDirectory() as d:
            r = informe(Path(d) / "falta.csv")
        self.assertEqual(r["estado"], "EVIDENCIA_INSUFICIENTE")
        self.assertFalse(r["evaluacion_posible"])
        self.assertFalse(r["certificacion_fases_5_a_12"])

    def test_40_trades_sinteticos_positivos_no_certifican_broker(self):
        with tempfile.TemporaryDirectory() as d:
            r = informe(crear(d))
        self.assertEqual(r["estado"], "OBJETIVO_OBSERVADO_SIN_CERTIFICACION")
        self.assertEqual(r["consistencia"]["ventanas_moviles_20"], 21)
        self.assertEqual(r["robustez"]["operaciones"], 40)
        self.assertEqual(r["robustez"]["dias_utc_distintos"], 1)
        self.assertFalse(r["conciliacion_broker_confirmada"])
        self.assertFalse(r["certificacion_fases_5_a_12"])
        self.assertFalse(r["autoriza_real"])

    def test_perdidas_no_se_descartan_para_mejorar_winrate(self):
        with tempfile.TemporaryDirectory() as d:
            r = informe(crear(d, losses=11))
        self.assertEqual(r["estado"], "OBJETIVO_NO_DEMOSTRADO")
        self.assertEqual(r["robustez"]["wins"], 18)
        self.assertEqual(r["consistencia"]["total"]["losses"], 22)

    def test_fila_que_no_esta_cerrada_bloquea_todo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = crear(d)
            texto = ruta.read_text(encoding="utf-8")
            ruta.write_text(texto.replace("CERRADA", "ABIERTA", 1), encoding="utf-8")
            r = informe(ruta)
        self.assertEqual(r["estado"], "EVIDENCIA_INSUFICIENTE")
        self.assertFalse(r["evaluacion_posible"])

    def test_resultado_invalido_no_genera_estadisticas_parciales(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = crear(d)
            texto = ruta.read_text(encoding="utf-8")
            ruta.write_text(texto.replace("LOSS", "PENDIENTE", 1), encoding="utf-8")
            r = informe(ruta)
        self.assertEqual(r["estado"], "EVIDENCIA_INVALIDA")
        self.assertIsNone(r["consistencia"])
        self.assertIsNone(r["robustez"])


if __name__ == "__main__":
    unittest.main()
