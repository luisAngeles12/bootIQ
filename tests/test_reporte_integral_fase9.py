"""R9-21: informe unificado conserva seguridad y archivos originales."""
import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.reporte_integral_fase9 import reporte_integral

CAMPOS = [
    "order_id", "modo_cuenta_configurado", "estado", "resultado", "fecha",
    "fecha_apertura_registro_local_utc", "fecha_conciliacion_local_utc",
    "origen_autoridad", "familia_setup",
]


def datos_validos():
    base = datetime(2026, 11, 19, tzinfo=timezone.utc)
    datos = []
    for i in range(50):
        apertura = base + timedelta(minutes=i * 3)
        datos.append({
            "order_id": str(i).zfill(5),
            "modo_cuenta_configurado": "PRACTICE",
            "estado": "CERRADA",
            "resultado": "20.75" if i % 2 else "-25",
            "fecha": apertura.isoformat(),
            "fecha_apertura_registro_local_utc": apertura.isoformat(),
            "fecha_conciliacion_local_utc": (
                apertura + timedelta(minutes=1)
            ).isoformat(),
            "origen_autoridad": "BOOTSTRAP_PRACTICE_SIN_HISTORIAL",
            "familia_setup": "RUPTURA" if i % 2 else "REVERSAL",
        })
    return datos


class ReporteIntegralFase9Tests(unittest.TestCase):
    def crear(self, tmp, filas):
        ruta = Path(tmp) / "historial.csv"
        with ruta.open("w", newline="", encoding="utf-8") as a:
            writer = csv.DictWriter(a, fieldnames=CAMPOS)
            writer.writeheader()
            writer.writerows(filas)
        return ruta

    def test_reporta_integridad_descriptiva_sin_certificar_rentabilidad(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = self.crear(tmp, datos_validos())
            antes = ruta.read_bytes()
            r = reporte_integral(ruta)
            self.assertEqual(r["estado"], "DIAGNOSTICO_COMPLETO_SIN_CERTIFICACION")
            self.assertEqual(r["evaluacion_descriptiva"]["oos_operaciones"], 20)
            self.assertEqual(r["particion"]["train"], 30)
            self.assertTrue(r["clasificacion"]["integridad_conteo"])
            self.assertFalse(r["evidencia_rentabilidad_sostenida"])
            self.assertFalse(r["memoria_generada"])
            self.assertFalse(r["habilita_trading"])
            self.assertIn("SIN_EXPORTACION_BROKER", r["motivos_no_certificacion"])
            self.assertEqual(antes, ruta.read_bytes())

    def test_cuenta_desconocida_bloquea_reportar_oos(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = datos_validos()
            filas[1]["modo_cuenta_configurado"] = ""
            r = reporte_integral(self.crear(tmp, filas))
            self.assertEqual(r["estado"], "NO_APTO_PARA_VALIDACION")
            self.assertIn("UNIVERSO_PRACTICE_INCOMPLETO",
                          r["motivos_no_certificacion"])
            self.assertEqual(r["clasificacion"]["grupos_excluyentes"][
                "CUENTA_DESCONOCIDA"], 1)
            self.assertNotIn("resumen_oos_descriptivo", r["evaluacion_descriptiva"])

    def test_empate_no_se_borra_del_universo(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = datos_validos()
            filas[2]["resultado"] = "0.0"
            r = reporte_integral(self.crear(tmp, filas))
            self.assertEqual(r["estado"], "NO_APTO_PARA_VALIDACION")
            self.assertEqual(r["particion"]["filas_practice_no_admisibles"], 1)
            self.assertFalse(r["evidencia_rentabilidad_sostenida"])

    def test_sin_columnas_requeridas_no_puede_avanzar(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "incompleto.csv"
            ruta.write_text("order_id\n001\n", encoding="utf-8")
            r = reporte_integral(ruta)
            self.assertEqual(r["estado"], "NO_APTO_PARA_VALIDACION")
            self.assertFalse(r["habilita_trading"])
            self.assertFalse(r["memoria_generada"])


if __name__ == "__main__":
    unittest.main()
