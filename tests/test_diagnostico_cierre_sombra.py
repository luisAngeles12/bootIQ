"""Regresiones del diagnostico no operativo sin broker."""
import unittest

from diagnostico_cierre_sombra import diagnosticar


def fila(id_, activo, instante, calidad, resultado=""):
    return {
        "id": id_, "activo": activo, "vela_senal_from": str(instante),
        "calidad_tiempo": calidad, "resultado_hipotetico": resultado,
    }


class TestDiagnosticoCierreSombra(unittest.TestCase):
    def test_pendientes_y_sin_buffer_no_se_convierten_en_resultados(self):
        filas = [
            fila("a", "A", 600, "HIPOTETICO_VELA_COMPLETA_SIN_FILL", "WIN"),
            fila("b", "A", 660, "PENDIENTE_VELA_POSTERIOR"),
            fila("c", "B", 600, "SIN_VELA_POSTERIOR_EN_BUFFER"),
            fila("d", "B", 1200, "HIPOTETICO_VELA_COMPLETA_SIN_FILL", "LOSS"),
        ]
        original = [dict(x) for x in filas]
        r = diagnosticar(filas, {"ids_por_estado": {
            "a": "ANALISIS_VALIDADO", "b": "ANALISIS_VALIDADO",
            "c": "DESCARTADA",
        }})
        self.assertEqual(r["pendientes"], 1)
        self.assertEqual(r["sin_vela_en_buffer"], 1)
        self.assertEqual(r["pendientes_en_ultimo_minuto_con_senal"], 1)
        self.assertEqual(r["sin_buffer_con_senal_posterior"], 1)
        self.assertEqual(r["inconsistencias_resultado_estado"], 0)
        self.assertEqual(filas, original)
        self.assertFalse(r["autoriza_operaciones"])

    def test_registros_inconsistentes_no_se_disfrazan_como_resueltos(self):
        filas = [
            fila("a", "A", 600, "PENDIENTE_VELA_POSTERIOR", "WIN"),
            fila("b", "A", 660, "HIPOTETICO_VELA_COMPLETA_SIN_FILL", ""),
        ]
        r = diagnosticar(filas, {"ids_por_estado": {}})
        self.assertEqual(r["inconsistencias_resultado_estado"], 2)
        self.assertEqual(r["pendientes"], 0)
        self.assertFalse(r["valida_winrate_60"])

    def test_muestra_vacia_no_inventa_cierre(self):
        r = diagnosticar([], {"ids_por_estado": {}})
        self.assertEqual(r["registros_csv"], 0)
        self.assertEqual(r["pendientes"], 0)
        self.assertEqual(r["activos"], [])


if __name__ == "__main__":
    unittest.main()
