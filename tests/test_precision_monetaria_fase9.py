"""R9-25.13: admisión monetaria coherente sin modificar trading ni historial."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.clasificar_historial_fase9 import clasificar_historial
from scripts.auditar_particion_temporal_fase9 import auditar_particion
from scripts.conciliar_exportacion_iq_fase9 import _monto

CAMPOS = [
    "order_id", "modo_cuenta_configurado", "estado", "resultado", "fecha",
    "fecha_apertura_registro_local_utc", "fecha_conciliacion_local_utc",
]


class PrecisionMonetariaFase9Tests(unittest.TestCase):
    def comprobar(self, pnl, admitida):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial.csv"
            with ruta.open("w", encoding="utf-8", newline="") as archivo:
                escritor = csv.DictWriter(archivo, fieldnames=CAMPOS)
                escritor.writeheader()
                escritor.writerow({
                    "order_id": "0001",
                    "modo_cuenta_configurado": "PRACTICE",
                    "estado": "CERRADA",
                    "resultado": pnl,
                    "fecha": "2026-11-19T12:00:00-04:00",
                    "fecha_apertura_registro_local_utc": "2026-11-19T16:00:00+00:00",
                    "fecha_conciliacion_local_utc": "2026-11-19T16:01:00+00:00",
                })
            antes = ruta.read_bytes()
            clasificacion = clasificar_historial(ruta)
            particion = auditar_particion(ruta)
            self.assertEqual(
                clasificacion["grupos_excluyentes"].get(
                    "PRACTICE_CANDIDATA_NO_CERTIFICADA", 0
                ), int(admitida)
            )
            self.assertEqual(particion["candidatas_tras_filtros"], int(admitida))
            self.assertEqual(antes, ruta.read_bytes())

    def test_importes_de_centavos_normales_se_admiten(self):
        for pnl in ("20.75", "-25.0", "0.01", "-0.01", "1e-2"):
            with self.subTest(pnl=pnl):
                self.assertIsNotNone(_monto(pnl))
                self.comprobar(pnl, True)

    def test_importes_con_fracciones_de_centavo_no_se_admiten(self):
        for pnl in ("20.755", "-25.001", "0.001", "-0.0001"):
            with self.subTest(pnl=pnl):
                self.assertIsNone(_monto(pnl))
                self.comprobar(pnl, False)

    def test_no_finitos_y_empates_no_se_admiten(self):
        for pnl in ("nan", "Infinity", "-Infinity", "", "0", "-0.00"):
            with self.subTest(pnl=pnl):
                self.comprobar(pnl, False)


if __name__ == "__main__":
    unittest.main()
