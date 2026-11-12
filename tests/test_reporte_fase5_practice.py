"""Regresiones del resumen fase 5 sin modificar decisiones oficiales."""
import unittest
from reporte_fase5_practice import generar_informe


def fila(i, dia, resultado, patron="CHOCH", pa="CALL"):
    return {
        "order_id": str(i),
        "estado": "CERRADA",
        "fecha": dia + " 10:00:00",
        "resultado": str(resultado),
        "patron": patron,
        "direccion": "CALL",
        "pa_direccion": pa,
    }


class InformeFase5Tests(unittest.TestCase):
    def test_informe_incluye_tres_diagnosticos_y_no_autoriza(self):
        rows = [
            fila(i, "2026-11-10", 20.75 if i < 15 else -25)
            for i in range(20)
        ] + [
            fila(i + 20, "2026-11-11", -25 if i < 12 else 20.75)
            for i in range(20)
        ]
        r = generar_informe(rows)
        self.assertEqual(r["operaciones_evaluables"], 40)
        self.assertEqual(r["bloques_completos"], 2)
        self.assertEqual(r["bloques_bajo_objetivo"], 1)
        self.assertEqual(r["diagnostico_temporal"], "DIAGNOSTICO_RETROSPECTIVO_NO_AUTORIZANTE")
        self.assertTrue(r["universos_diagnosticos_coinciden"])
        self.assertFalse(r["cambios_operativos_autorizados"])
        self.assertFalse(r["evidencia_suficiente_para_cambio_operativo"])

    def test_sin_20_operaciones_no_certifica_constancia(self):
        r = generar_informe([fila(i, "2026-11-11", 20.75) for i in range(10)])
        self.assertEqual(r["ventanas_moviles"], 0)
        self.assertFalse(r["consistencia_20_observada"])
        self.assertEqual(r["diagnostico_temporal"], "SIN_SEPARACION_TEMPORAL")
        self.assertEqual(r["estrategias_con_test_favorable"], 0)

    def test_duplicados_y_empates_no_se_cuentan_como_wins(self):
        rows = [fila(1, "2026-11-10", 20.75),
                fila(1, "2026-11-10", 20.75),
                fila(2, "2026-11-10", 0)]
        r = generar_informe(rows)
        self.assertEqual(r["operaciones_evaluables"], 1)
        self.assertTrue(r["universos_diagnosticos_coinciden"])
        self.assertEqual(r["winrate_global_pct"], 100.0)
        self.assertFalse(r["cambios_operativos_autorizados"])


if __name__ == "__main__":
    unittest.main()
