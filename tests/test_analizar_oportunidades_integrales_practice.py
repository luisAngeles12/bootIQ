import unittest
from datetime import datetime, timedelta

from analizar_oportunidades_integrales_practice import analizar, _features


def fila(i, day, pnl, patron="CHOCH bajista", modo="PRACTICE", estado="CERRADA"):
    return {
        "order_id": str(i),
        "fecha": f"2026-11-{day:02d} 12:00:00",
        "estado": estado,
        "estado_operacion": "OPERADA_DIRECTA",
        "modo_cuenta_configurado": modo,
        "resultado": str(pnl),
        "patron": patron,
        "direccion": "put",
        "direccion_tendencia": "BAJISTA",
        "rsi": "45", "ema9": "1", "ema21": "2",
        "bb_inferior": "1", "bb_media": "2", "bb_superior": "3",
        "precio_cierre_indicadores": "2.5",
        "precio_senal_open": "2", "precio_senal_close": "1.8",
        "precio_senal_high": "2.1", "precio_senal_low": "1.7",
    }


class OportunidadesIntegralesTest(unittest.TestCase):
    def test_no_confunde_abiertas_ni_real(self):
        rows = [fila(1, 12, 20), fila(2, 12, -25, modo="REAL"),
                fila(3, 12, 20, estado="ABIERTA")]
        r = analizar(rows, 2, 2)
        self.assertEqual(r["operaciones_validas"], 1)
        self.assertEqual(r["descartes"]["NO_PRACTICE"], 1)
        self.assertEqual(r["descartes"]["NO_CERRADA"], 1)

    def test_no_valida_si_no_hay_dias_separados(self):
        r = analizar([fila(i, 12, 20) for i in range(5)], 2, 2)
        self.assertEqual(r["estado"], "SIN_DIAS_INDEPENDIENTES")
        self.assertIsNone(r["candidato"])

    def test_features_mercado_indicadores_vela(self):
        f = _features(fila(1, 12, 20))
        self.assertEqual(f["rsi_zona"], "30_A_70")
        self.assertEqual(f["ema_direccion"], "BAJISTA")
        self.assertEqual(f["bb_ubicacion"], "MITAD_SUPERIOR")
        self.assertEqual(f["direccion_contra_tendencia"], "A_FAVOR")
        self.assertEqual(f["vela_senal_cuerpo"], "CUERPO_MEDIO")

    def test_holdout_no_se_utiliza_para_escoger_candidato(self):
        rows = []
        i = 0
        for day in range(10, 20):
            for k in range(10):
                i += 1
                # En TRAIN el patron A domina; en TEST se deteriora.
                a = k < 5
                train = day <= 15
                pnl = (20 if (a == train) else -25)
                rows.append(fila(i, day, pnl, "A" if a else "B"))
        r = analizar(rows, 15, 10)
        self.assertEqual(r["estado"], "ANALISIS_NO_OPERABLE")
        self.assertEqual(r["candidato"]["variable"], "patron")
        self.assertEqual(r["candidato"]["valor"], "A")
        self.assertLess(r["candidato"]["test_oos"]["neto"], 0)
        self.assertFalse(r["candidato"]["supera_objetivo_oos"])
        self.assertFalse(r["candidato"]["autoriza_operaciones"])


if __name__ == "__main__":
    unittest.main()
