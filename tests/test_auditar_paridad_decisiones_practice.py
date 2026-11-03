"""Regresiones del auditor CSV causal, sin conexiones ni operaciones."""
import csv
import tempfile
import unittest
from pathlib import Path

from auditar_paridad_decisiones_practice import (
    COLUMNAS, cargar_captura, auditar_decisiones, resumir_contexto_temporal,
)


def muestra(minutos=26):
    velas = {}
    for t in range(minutos * 60):
        precio = 100 + 0.0001 * t + 0.0002 * (t % 13)
        velas[t] = {
            "from": t, "open": precio, "max": precio + 0.00002,
            "min": precio - 0.00001, "close": precio + 0.00001,
        }
    return velas


class AuditorParidadDecisionesTests(unittest.TestCase):
    def test_sin_retrasos_las_decisiones_coinciden(self):
        velas = muestra()
        datos = auditar_decisiones(velas, {t: 0 for t in velas})
        self.assertEqual(datos["estado"], "PARIDAD_DECISIONES_COMPLETA")
        self.assertEqual(datos["decisiones_iguales_sobre_flujo"], 26)
        self.assertEqual(datos["decisiones_diferentes_sobre_flujo"], 0)
        self.assertTrue(datos["coincidencia_cierres_elegibles"])
        self.assertFalse(datos["operaciones_autorizadas"])

    def test_cierre_tardio_se_excluye_y_contexto_no_se_inventa(self):
        velas = muestra()
        latencias = {t: 0 for t in velas}
        latencias[20 * 60 + 59] = 2
        datos = auditar_decisiones(velas, latencias)
        self.assertEqual(datos["estado"], "PARIDAD_DECISIONES_NO_DEMOSTRADA")
        self.assertEqual(datos["cierres_replay_excluidos"], [21 * 60])
        self.assertEqual(datos["cierres_flujo"], 25)
        self.assertTrue(datos["coincidencia_cierres_elegibles"])
        self.assertGreater(datos["contextos_diferentes"], 0)
        self.assertFalse(datos["operaciones_autorizadas"])

    def test_contexto_temporal_exige_24_minutos_contiguos(self):
        velas = muestra(26)
        latencias = {t: 0 for t in velas}
        completo = resumir_contexto_temporal(velas, latencias)
        self.assertEqual(completo["cierres_temporalmente_elegibles"], 26)
        self.assertEqual(completo["racha_maxima_cierres_elegibles"], 26)
        self.assertEqual(completo["cierres_con_contexto_temporal_verificado"], 3)
        latencias[20 * 60 + 59] = 2
        incompleto = resumir_contexto_temporal(velas, latencias)
        self.assertEqual(incompleto["cierres_temporalmente_elegibles"], 25)
        self.assertEqual(incompleto["racha_maxima_cierres_elegibles"], 20)
        self.assertEqual(incompleto["cierres_con_contexto_temporal_verificado"], 0)
        self.assertFalse(incompleto["operaciones_autorizadas"])

    def test_csv_valida_campos_y_rechaza_duplicados(self):
        with tempfile.TemporaryDirectory() as temp:
            archivo = Path(temp) / "practice.csv"
            with archivo.open("w", encoding="utf-8", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=COLUMNAS)
                writer.writeheader()
                for t in range(60):
                    writer.writerow({
                        "activo": "USDINR-OTC", "timestamp_utc": t,
                        "open": 100, "high": 101, "low": 99,
                        "close": 100, "latencia_primera_recepcion_s": 0,
                    })
            velas, latencias = cargar_captura(archivo)
            self.assertEqual(len(velas), 60)
            self.assertEqual(len(latencias), 60)
            with archivo.open("a", encoding="utf-8", newline="") as out:
                out.write("USDINR-OTC,59,100,101,99,100,0\n")
            with self.assertRaisesRegex(ValueError, "TIMESTAMP_DUPLICADO"):
                cargar_captura(archivo)


if __name__ == "__main__":
    unittest.main()
