"""Regresiones del diagnostico no operativo de sombras pendientes."""
import unittest
from datetime import datetime, timezone
from diagnosticar_pendientes_sombra_practice import diagnosticar


def fila(estado, ts, activo="EURUSD", resultado=""):
    return {"decision": "NO_OPERAR", "calidad_tiempo": estado,
            "vela_senal_from": str(ts), "activo": activo,
            "resultado_hipotetico": resultado}


class DiagnosticoPendientesTests(unittest.TestCase):
    def test_separa_pendientes_rezagadas_y_fuera_de_buffer(self):
        ref = datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc)
        t = int(ref.timestamp())
        filas = [
            fila("PENDIENTE_VELA_POSTERIOR", t - 7200),
            fila("PENDIENTE_VELA_POSTERIOR", t - 120, "PLTR-OTC"),
            fila("PENDIENTE_VELA_POSTERIOR", t + 60, "PLTR-OTC"),
            fila("SIN_VELA_POSTERIOR_EN_BUFFER", t - 3600),
            fila("PENDIENTE_VELA_POSTERIOR", t - 7200, resultado="WIN"),
        ]
        r = diagnosticar(filas, ref)
        self.assertEqual(r["total_sin_resultado"], 4)
        self.assertEqual(r["pendientes_mas_de_una_hora"], 1)
        self.assertEqual(r["pendientes_ultima_hora"], 1)
        self.assertEqual(r["pendientes_en_futuro"], 1)
        self.assertEqual(r["por_estado"]["SIN_VELA_POSTERIOR_EN_BUFFER"], 1)
        self.assertFalse(r["genera_resultados"])
        self.assertFalse(r["autoriza_operaciones"])
        self.assertFalse(r["altera_historial"])

    def test_fechas_invalidas_y_ordenes_ajenas(self):
        ref = datetime(2026, 11, 21, tzinfo=timezone.utc)
        invalida = fila("PENDIENTE_VELA_POSTERIOR", "error")
        descartada = fila("PENDIENTE_VELA_POSTERIOR", 100)
        descartada["decision"] = "OPERAR"
        r = diagnosticar([invalida, descartada], ref)
        self.assertEqual(r["total_sin_resultado"], 1)
        self.assertEqual(r["sin_timestamp_senal"], 1)
        self.assertEqual(r["pendientes_mas_de_una_hora"], 0)

    def test_referencia_debe_ser_timezone_aware(self):
        with self.assertRaises(ValueError):
            diagnosticar([], datetime(2026, 11, 21))


if __name__ == "__main__":
    unittest.main()
