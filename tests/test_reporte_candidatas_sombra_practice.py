"""Casos deterministas del resumen de candidatas: no aprueba trading."""
import csv
import tempfile
import unittest
from pathlib import Path
from reporte_candidatas_sombra_practice import resumen_eventos, generar_reporte
from auditoria_candidatas_sombra_practice import COLUMNAS


def evento(patron, resultado, ts, decision="NO_OPERAR", mercado="RANGO",
           calidad="NORMAL", accion="RECHAZO"):
    return {
        "patron": patron, "resultado_hipotetico": resultado,
        "vela_senal_from": str(ts), "decision": decision,
        "tipo_mercado": mercado, "calidad_mercado": calidad,
        "accion_precio": accion, "activo": "USDINR-OTC", "direccion": "call",
    }


class ReporteSombraPractice(unittest.TestCase):
    def test_sin_datos_no_inventa_winrate(self):
        self.assertEqual(resumen_eventos([], "patron"), [])

    def test_cuatro_win_un_loss_no_es_evidencia_validada(self):
        muestras = [evento("PULLBACK", "WIN", 86400 + i * 60) for i in range(4)]
        muestras.append(evento("PULLBACK", "LOSS", 86400 + 400))
        r = resumen_eventos(muestras)[0]
        self.assertEqual((r["win"], r["loss"]), (4, 1))
        self.assertEqual(r["winrate_hipotetico_pct"], 80.0)
        self.assertLess(r["limite_inferior_wilson_95_pct"], 60)
        self.assertEqual(r["validacion_60"], "NO_VALIDADA")
        self.assertFalse(r["operaciones_autorizadas"])

    def test_pendientes_y_empates_no_se_ocultan(self):
        muestras = [
            evento("CHOCH", "WIN", 86400),
            evento("CHOCH", "EMPATE", 86460),
            evento("CHOCH", "", 86520),
            evento("CHOCH", "LOSS", 86580),
        ]
        r = resumen_eventos(muestras)[0]
        self.assertEqual((r["win"], r["loss"], r["empates"], r["pendientes"]), (1, 1, 1, 1))
        self.assertEqual(r["winrate_hipotetico_pct"], 33.33)

    def test_descarta_registros_no_rechazados(self):
        r = resumen_eventos([
            evento("X", "WIN", 86400, decision="OPERAR"),
            evento("X", "LOSS", 86460),
        ])
        self.assertEqual((r[0]["candidatas"], r[0]["win"], r[0]["loss"]), (1, 0, 1))

    def test_reporte_por_contexto_sin_permiso(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sombra.csv"
            e = evento("PULLBACK", "WIN", 86400, mercado="TENDENCIA_ALCISTA",
                       accion="ABSORCION_COMPRADORA")
            with p.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLUMNAS)
                w.writeheader()
                w.writerow(e)
            r = generar_reporte(p)
            self.assertEqual(len(r["por_estrategia"]), 1)
            self.assertEqual(r["por_mercado"][0]["tipo_mercado"], "TENDENCIA_ALCISTA")
            self.assertEqual(r["por_accion_precio"][0]["accion_precio"], "ABSORCION_COMPRADORA")
            self.assertFalse(r["operaciones_autorizadas"])

if __name__ == "__main__":
    unittest.main()
