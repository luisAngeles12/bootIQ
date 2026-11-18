"""Pruebas aisladas del informe integral de memoria PRACTICE."""
import unittest
from unittest.mock import patch

import auditoria_integral_memoria_v3_practice as auditor


def registro(oid, dia, pnl, modo, autoridad="BOOTSTRAP_PRACTICE_SIN_HISTORIAL"):
    return {
        "order_id": str(oid),
        "fecha": f"2026-11-{dia:02d} 12:00:00",
        "estado": "CERRADA", "estado_operacion": "OPERADA_DIRECTA",
        "modo_cuenta_configurado": modo, "origen_autoridad": autoridad,
        "resultado": str(pnl), "direccion": "call",
        "patron": "CHOCH alcista", "familia_setup": "REVERSIÓN_ESTRUCTURAL",
        "tipo_mercado": "TENDENCIA_ALCISTA",
    }


class AuditoriaIntegralMemoriaTest(unittest.TestCase):
    def test_totales_procedencia_y_exclusion_real_sin_mutacion(self):
        filas = []
        for dia in (10, 11, 12, 13, 14, 16, 17, 18):
            for k in range(10):
                oid = 14400000000 + dia * 100 + k
                modo = "" if dia <= 14 else "PRACTICE"
                filas.append(registro(oid, dia, 20.75 if k % 2 else -25, modo))
        filas += [
            registro("14500000001", 18, -25, "REAL"),
            registro("14500000002", 14, 0, ""),
            registro("14500000003", 18, 20, "PRACTICE",
                     autoridad="SIN_AUTORIDAD",),
        ]
        filas[-1]["estado"] = "ABIERTA"
        antes = [dict(f) for f in filas]
        resultado = auditor.generar_informe(filas)
        self.assertEqual(filas, antes)
        self.assertEqual(resultado["total_filas_originales"], 83)
        self.assertEqual(resultado["evaluables_total"], 80)
        self.assertEqual(resultado["resumen_por_procedencia"]["USUARIO_DECLARADO_LEGADO_SIN_MODO"]["n"], 50)
        self.assertEqual(resultado["resumen_por_procedencia"]["CSV_MODO_PRACTICE"]["n"], 30)
        self.assertEqual(resultado["descartes_y_procedencia"]["NO_PRACTICE"], 1)
        self.assertEqual(resultado["descartes_y_procedencia"]["EMPATE"], 1)
        self.assertEqual(resultado["descartes_y_procedencia"]["NO_CERRADA"], 1)
        self.assertEqual(resultado["evaluacion_temporal"]["dias_disponibles"], 8)
        self.assertFalse(resultado["autoriza_operaciones"])
        self.assertFalse(resultado["memoria_productiva_modificada"])
        self.assertFalse(resultado["cambios_operativos_autorizados"])

    def test_reporta_cantidad_correcta_si_no_hay_dias_evaluables(self):
        filas = [registro(14400000000+i, 10, 20.75, "") for i in range(10)]
        resultado = auditor.generar_informe(filas)
        self.assertEqual(resultado["evaluables_total"], 10)
        self.assertEqual(resultado["evaluacion_temporal"]["dias_test_evaluados"], 0)
        self.assertFalse(resultado["evaluacion_temporal"]["supera_60_y_neto"])


if __name__ == "__main__":
    unittest.main()
