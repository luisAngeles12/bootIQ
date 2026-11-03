"""Regresiones del auditor CSV causal, sin conexiones ni operaciones."""
import csv
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from auditar_paridad_decisiones_practice import (
    COLUMNAS, cargar_captura, auditar_decisiones, resumir_contexto_temporal,
    resumir_arbitro_flujo, evaluar_candidatos_causales,
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

    def test_ventanas_validas_no_se_convierten_en_senales(self):
        velas = muestra(26)
        latencias = {t: 0 for t in velas}
        reporte = resumir_arbitro_flujo(velas, latencias)
        self.assertEqual(reporte["cierres_flujo"], 26)
        self.assertEqual(reporte["ventanas_contexto_verificadas"], 3)
        self.assertEqual(sum(reporte["estados_arbitro"].values()), 26)
        self.assertEqual(sum(reporte["motivos_arbitro"].values()), 26)
        self.assertLessEqual(reporte["candidatos_con_contexto_temporal_verificado"],
                             reporte["ventanas_contexto_verificadas"])
        self.assertIsNone(reporte["resultados_win_loss_verificados"])
        self.assertIsNone(reporte["payouts_preentrada_verificados"])
        self.assertFalse(reporte["operaciones_autorizadas"])

    def test_recepcion_tardia_reinicia_contexto_del_arbitro(self):
        velas = muestra(26)
        latencias = {t: 0 for t in velas}
        latencias[20 * 60 + 59] = 2
        reporte = resumir_arbitro_flujo(velas, latencias)
        self.assertEqual(reporte["cierres_flujo"], 25)
        self.assertEqual(reporte["ventanas_contexto_verificadas"], 0)
        self.assertFalse(reporte["operaciones_autorizadas"])

    def test_candidato_causal_con_futuro_es_solo_hipotetico(self):
        velas = muestra(27)
        diagnosticos = [
            (fin, {"arbitraje": {
                "operable": False,
                "estado": "CANDIDATO_SOMBRA_NO_OPERABLE"
                if fin in (24 * 60, 25 * 60) else "NO_OPERAR",
                "direccion": "call" if fin in (24 * 60, 25 * 60) else None,
                "estrategias": ["RUPTURA_RETEST"] if fin in (24 * 60, 25 * 60) else [],
            }})
            for fin in range(60, 27 * 60 + 1, 60)
        ]
        with patch("auditar_paridad_decisiones_practice.evaluar_flujo",
                   return_value=diagnosticos):
            reporte = evaluar_candidatos_causales(
                velas, {t: 0 for t in velas}
            )
        self.assertEqual(reporte["eventos_sombra_no_solapados"], 2)
        self.assertEqual(reporte["outcomes_hipoteticos_evaluables"], 2)
        self.assertEqual(reporte["wins_hipoteticos"], 2)
        self.assertFalse(reporte["payout_verificado"])
        self.assertFalse(reporte["evidencia_estadistica_validada"])
        self.assertFalse(reporte["operaciones_autorizadas"])
        self.assertTrue(all(not e["operable"] and
                            e["payout_neto"] is None for e in reporte["eventos"]))

    def test_candidato_sin_24_cierres_o_futuro_se_rechaza(self):
        velas = muestra(24)
        diag = [(60, {"arbitraje": {
            "operable": False, "estado": "CANDIDATO_SOMBRA_NO_OPERABLE",
            "direccion": "call", "estrategias": ["RECHAZO_ZONA"],
        }})]
        with patch("auditar_paridad_decisiones_practice.evaluar_flujo",
                   return_value=diag):
            r = evaluar_candidatos_causales(velas, {t: 0 for t in velas})
        self.assertEqual(r["candidatos_con_contexto_insuficiente"], 1)
        self.assertEqual(r["eventos_sombra_no_solapados"], 0)
        diag = [(fin, {"arbitraje": {
            "operable": False,
            "estado": "CANDIDATO_SOMBRA_NO_OPERABLE" if fin == 24 * 60 else "NO_OPERAR",
            "direccion": "call" if fin == 24 * 60 else None,
            "estrategias": ["RECHAZO_ZONA"] if fin == 24 * 60 else [],
        }}) for fin in range(60, 24 * 60 + 1, 60)]
        with patch("auditar_paridad_decisiones_practice.evaluar_flujo",
                   return_value=diag):
            r = evaluar_candidatos_causales(velas, {t: 0 for t in velas})
        self.assertEqual(r["sin_futuro"], 1)
        self.assertEqual(r["outcomes_hipoteticos_evaluables"], 0)
        self.assertIsNone(r["wr_hipotetico_pct"])

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
