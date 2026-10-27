import csv
import tempfile
import unittest
from pathlib import Path

from auditoria_hipotesis_fase32 import CORTE_PROSPECTIVO_UTC
from auditar_fase3_prospectiva_offline import (
    evaluar_archivos,
    evaluar_ventanas_prospectivas,
)


def muestra(primero, n=40, activo="EURUSD-OTC", resultado="WIN"):
    return [
        {
            "fecha_senal": str(primero + 60*i),
            "activo": activo,
            "patron": "PATRON", "direccion": "call",
            "pa_fuerza": "0.3", "rsi": "45", "puntaje": "18",
            "resultado_hipotetico": resultado,
        }
        for i in range(n)
    ]


class AuditoriaFase3ProspectivaOfflineTests(unittest.TestCase):
    def test_tres_ventanas_futuras_no_operan_automaticamente(self):
        inicio = int(CORTE_PROSPECTIVO_UTC) + 86400
        ventanas = [
            (nombre, muestra(inicio + dia*86400))
            for dia, nombre in enumerate(("v1", "v2", "v3"))
        ]
        r = evaluar_ventanas_prospectivas(ventanas, ("v1", "v2", "v3"))
        self.assertEqual(r["hipotesis"]["A"]["n_prospectivo"], 120)
        self.assertTrue(r["hipotesis"]["A"]["evidencia_59_transferible"])
        self.assertFalse(r["hipotesis"]["A"]["autoriza_operacion"])
        self.assertEqual(r["economia_observada"]["operaciones_cerradas"], 0)
        self.assertIsNone(r["economia_observada"]["pnl_real_cerrado"])
        self.assertFalse(r["autoriza_operaciones"])

    def test_tres_ventanas_mismo_dia_no_demuestran_estabilidad(self):
        inicio = int(CORTE_PROSPECTIVO_UTC) + 86400
        ventanas = [
            ("v1", muestra(inicio, n=30)),
            ("v2", muestra(inicio + 3*3600, n=30, activo="USDJPY-OTC")),
            ("v3", muestra(inicio + 6*3600, n=30, activo="GBPUSD-OTC")),
        ]
        with self.assertRaisesRegex(ValueError, "comparten día UTC"):
            evaluar_ventanas_prospectivas(ventanas, ("v1", "v2", "v3"))

    def test_mismo_dia_en_activos_distintos_no_es_ventana_independiente(self):
        inicio = int(CORTE_PROSPECTIVO_UTC) + 86400
        ventanas = [
            ("v1", muestra(inicio, n=2)),
            ("v2", muestra(inicio + 3600, n=2, activo="USDJPY-OTC")),
        ]
        with self.assertRaisesRegex(ValueError, "comparten día UTC"):
            evaluar_ventanas_prospectivas(ventanas, ("v1", "v2"))

    def test_no_acepta_datos_anteriores_al_corte(self):
        antiguo = muestra(int(CORTE_PROSPECTIVO_UTC) - 60, n=1)
        with self.assertRaisesRegex(ValueError, "anteriores"):
            evaluar_ventanas_prospectivas([("vieja", antiguo)], ("vieja",))

    def test_no_acepta_ventanas_superpuestas_aunque_activos_difieran(self):
        inicio = int(CORTE_PROSPECTIVO_UTC) + 86400
        ventanas = [
            ("v1", muestra(inicio, 3, activo="EURUSD-OTC")),
            ("v2", muestra(inicio + 120, 3, activo="USDJPY-OTC")),
        ]
        with self.assertRaisesRegex(ValueError, "solapadas"):
            evaluar_ventanas_prospectivas(ventanas, ("v1", "v2"))

    def test_no_infiere_prospectividad_ni_fechas_faltantes(self):
        futuro = muestra(int(CORTE_PROSPECTIVO_UTC) + 86400, 1)
        with self.assertRaisesRegex(ValueError, "explícitos"):
            evaluar_ventanas_prospectivas([("v1", futuro)], ())
        futuro[0]["fecha_senal"] = ""
        with self.assertRaisesRegex(ValueError, "Fecha ausente"):
            evaluar_ventanas_prospectivas([("v1", futuro)], ("v1",))

    def test_no_acepta_nombres_duplicados_o_desconocidos(self):
        futuro = muestra(int(CORTE_PROSPECTIVO_UTC) + 86400, 1)
        with self.assertRaisesRegex(ValueError, "repetidos"):
            evaluar_ventanas_prospectivas(
                [("v1", futuro), ("v1", futuro)], ("v1",)
            )
        with self.assertRaisesRegex(ValueError, "sin archivo"):
            evaluar_ventanas_prospectivas([("v1", futuro)], ("v2",))

    def test_csv_broker_free_sin_escritura_de_resultados(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "futura.csv"
            filas = muestra(int(CORTE_PROSPECTIVO_UTC) + 86400, 2)
            with ruta.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(filas[0]))
                writer.writeheader()
                writer.writerows(filas)
            r = evaluar_archivos([("v1", ruta)], ("v1",))
            self.assertEqual(r["hipotesis"]["A"]["n_prospectivo"], 2)
            self.assertFalse(r["hipotesis"]["A"]["evidencia_59_transferible"])
            self.assertFalse(r["autoriza_operaciones"])

    def test_economia_y_frecuencia_exigen_cierres_explicitos(self):
        futuro = muestra(int(CORTE_PROSPECTIVO_UTC) + 86400, 2)
        futuro[0].update({
            "estado_operacion": "OPERADA_DIRECTA", "resultado": "WIN",
            "pnl_real_cerrado": "7",
        })
        futuro[1].update({
            "estado_operacion": "OPERADA_DIRECTA", "resultado": "LOSS",
            "pnl_real_cerrado": "-5",
        })
        r = evaluar_ventanas_prospectivas([("v1", futuro)], ("v1",), payout_neto=.70)
        self.assertEqual(r["economia_observada"]["operaciones_cerradas"], 2)
        self.assertEqual(r["economia_observada"]["pnl_real_cerrado"], 2.0)
        self.assertAlmostEqual(r["economia_observada"]["break_even_teorico"], 58.8235, places=4)
        dia = next(iter(r["frecuencia_backtest_por_dia"].values()))
        self.assertEqual(dia["operadas_backtest"], 2)
        self.assertFalse(r["autoriza_operaciones"])



if __name__ == "__main__":
    unittest.main()
