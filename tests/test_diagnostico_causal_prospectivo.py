import unittest

from diagnostico_causal_prospectivo import diagnosticar
from validacion_prospectiva_alineacion import CORTE_SENAL_UTC


def fila(ts, activo="CADCHF-OTC", direccion="call", patron="CHOCH alcista",
         resultado="WIN", calidad="NORMAL"):
    return {
        "activo": activo, "vela_senal_from": str(ts), "direccion": direccion,
        "patron": patron, "estado_tendencia": "ALCISTA_NORMAL",
        "accion_precio": "RECHAZO_COMPRADOR_SOPORTE",
        "calidad_mercado": calidad,
        "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
        "resultado_hipotetico": resultado, "decision": "NO_OPERAR",
    }


class DiagnosticoProspectivo(unittest.TestCase):
    def test_corte_no_contamina_resultados(self):
        r = diagnosticar([
            fila(CORTE_SENAL_UTC, resultado="WIN"),
            fila(CORTE_SENAL_UTC + 60, resultado="LOSS"),
        ])
        self.assertEqual(r["registros_desarrollo_excluidos"], 1)
        self.assertEqual(r["registros_posteriores"], 1)
        self.assertEqual(r["resumen"]["wins"], 0)
        self.assertEqual(r["resumen"]["losses"], 1)

    def test_un_activo_minuto_no_duplica(self):
        r = diagnosticar([
            fila(CORTE_SENAL_UTC + 60, patron="CHOCH alcista"),
            fila(CORTE_SENAL_UTC + 60, patron="continuacion alcista"),
        ])
        self.assertEqual(r["resumen"]["oportunidades"], 1)
        self.assertEqual(r["por_patron_exclusivo"]["atribucion_excluida_multi_patron"], 1)

    def test_conflicto_no_selecciona_ganador(self):
        r = diagnosticar([
            fila(CORTE_SENAL_UTC + 60, direccion="call", resultado="WIN"),
            fila(CORTE_SENAL_UTC + 60, direccion="put", resultado="LOSS"),
        ])
        self.assertEqual(r["resumen"]["oportunidades"], 0)
        self.assertEqual(r["descartes"]["CONFLICTO_ACTIVO_MINUTO"], 1)

    def test_pendientes_y_sucios_se_excluyen(self):
        r = diagnosticar([
            fila(CORTE_SENAL_UTC + 60, resultado=""),
            fila(CORTE_SENAL_UTC + 60, activo="USDCHF", calidad="SUCIO"),
        ])
        self.assertEqual(r["resumen"]["oportunidades"], 0)
        self.assertEqual(r["descartes"]["SIN_RESULTADO_TRAZABLE"], 1)
        self.assertEqual(r["descartes"]["MERCADO_NO_APTO"], 1)

    def test_simultaneidad_se_mide_y_no_autoriza(self):
        r = diagnosticar([
            fila(CORTE_SENAL_UTC + 60),
            fila(CORTE_SENAL_UTC + 60, activo="USDCHF", resultado="LOSS"),
        ])
        self.assertEqual(r["resumen"]["oportunidades"], 2)
        self.assertEqual(r["comparacion_pareada_por_minuto"]["minutos_con_multiples_activos"], 1)
        self.assertEqual(r["comparacion_pareada_por_minuto"]["minutos_con_resultados_mixtos"], 1)
        self.assertEqual(r["validacion_60"], "NO_VALIDADA")
        self.assertFalse(r["ordenes_autorizadas"])


if __name__ == "__main__":
    unittest.main()
