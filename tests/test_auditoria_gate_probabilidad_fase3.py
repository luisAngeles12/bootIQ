import unittest
from datetime import datetime, timezone
from auditoria_gate_probabilidad_fase3 import evaluar_gate_probabilidad


def fila(dia, p, resultado):
    fecha = datetime(2026, 9, dia, tzinfo=timezone.utc).timestamp()
    return {"fecha_senal": str(fecha), "probabilidad_estimada": str(p),
            "resultado_hipotetico": resultado}


class GateProbabilidadF3Tests(unittest.TestCase):
    def test_gate_fijo_por_dia_y_totales(self):
        r = evaluar_gate_probabilidad([
            fila(15, 57, "WIN"), fila(15, 56.9, "LOSS"),
            fila(16, 60, "LOSS"), fila(16, 61, "WIN"),
        ])
        self.assertEqual(r["gate_57"]["n"], 3)
        self.assertEqual(r["gate_57"]["win"], 2)
        self.assertEqual(r["dias"]["2026-09-15"]["gate_57"]["n"], 1)
        self.assertFalse(r["autoriza_operacion"])

    def test_p90_del_dia_anterior_sin_fuga_de_etiquetas(self):
        filas = [
            fila(15, 40, "WIN"), fila(15, 50, "LOSS"),
            fila(15, 60, "LOSS"), fila(16, 45, "WIN"),
            fila(16, 52, "WIN"), fila(16, 61, "LOSS"),
        ]
        r = evaluar_gate_probabilidad(filas)
        self.assertNotIn("2026-09-15", r["detalle_p90_temporal"])
        self.assertEqual(r["detalle_p90_temporal"]["2026-09-16"]["corte_previo_p90"], 50.0)
        self.assertEqual(r["seleccion_p90_dia_anterior"]["n"], 2)
        self.assertEqual(r["seleccion_p90_dia_anterior"]["win"], 1)

    def test_rechaza_ajustes_del_umbral_y_malos_registros(self):
        with self.assertRaises(ValueError):
            evaluar_gate_probabilidad([], umbral=50)
        r = evaluar_gate_probabilidad([{"fecha_senal":"x", "probabilidad_estimada":"60",
                                         "resultado_hipotetico":"WIN"}])
        self.assertEqual(r["filas_invalidas"], 1)
        self.assertIsNone(r["gate_57"]["wr_hipotetico"])


if __name__ == "__main__":
    unittest.main()
