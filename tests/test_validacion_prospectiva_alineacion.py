"""Pruebas del corte prospectivo fijo; nunca habilitan operaciones."""
import unittest

from validacion_prospectiva_alineacion import (
    CORTE_SENAL_UTC, validar_prospectivamente,
)


def fila(ts, direccion="call", tendencia="ALCISTA_NORMAL", resultado="WIN",
         activo="USDINR-OTC", accion="RECHAZO_COMPRADOR_SOPORTE"):
    return {
        "activo": activo,
        "vela_senal_from": str(ts),
        "direccion": direccion,
        "estado_tendencia": tendencia,
        "resultado_hipotetico": resultado,
        "patron": "PULLBACK",
        "accion_precio": accion,
        "calidad_mercado": "NORMAL",
        "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
        "decision": "NO_OPERAR",
    }


class CorteProspectivo(unittest.TestCase):
    def test_original_no_cuenta_como_nuevo(self):
        r = validar_prospectivamente([
            fila(CORTE_SENAL_UTC - 60),
            fila(CORTE_SENAL_UTC),
        ])
        self.assertEqual(r["registros_desarrollo_excluidos"], 2)
        self.assertEqual(r["registros_posteriores_al_corte"], 0)
        self.assertEqual(r["pendiente"], "SIN_MUESTRA_POSTERIOR")
        self.assertEqual(r["escenarios_congelados"]["BASE_SIN_FILTRO_NUEVO"]["oportunidades"], 0)

    def test_futuro_separado_no_recalcula_baseline(self):
        r = validar_prospectivamente([
            fila(CORTE_SENAL_UTC, resultado="WIN"),
            fila(CORTE_SENAL_UTC + 60, resultado="LOSS"),
        ])
        self.assertEqual(r["registros_desarrollo_excluidos"], 1)
        self.assertEqual(r["registros_posteriores_al_corte"], 1)
        self.assertEqual(r["escenarios_congelados"]["BASE_SIN_FILTRO_NUEVO"]["losses"], 1)
        self.assertEqual(
            r["deriva_respecto_desarrollo"]["BASE_SIN_FILTRO_NUEVO"]["desarrollo_pct"],
            51.11,
        )

    def test_hasta_con_cien_por_ciento_no_autoriza(self):
        r = validar_prospectivamente([fila(CORTE_SENAL_UTC + 60)])
        self.assertEqual(r["escenarios_congelados"]["BASE_SIN_FILTRO_NUEVO"]["winrate_proxy_pct"], 100)
        self.assertEqual(r["validacion_winrate_60"], "NO_VALIDADA")
        self.assertEqual(r["validacion_economica"], "SIN_FILL_NI_PAYOUT_PREENTRADA")
        self.assertFalse(r["ordenes_autorizadas"])
        self.assertFalse(r["cerebro_modificado"])

    def test_sin_segundo_resultado_no_cuenta(self):
        f = fila(CORTE_SENAL_UTC + 60)
        f["resultado_hipotetico"] = ""
        f["calidad_tiempo"] = "PENDIENTE_VELA_POSTERIOR"
        r = validar_prospectivamente([f])
        self.assertEqual(r["registros_posteriores_al_corte"], 1)
        self.assertEqual(r["escenarios_congelados"]["BASE_SIN_FILTRO_NUEVO"]["oportunidades"], 0)
        self.assertEqual(r["pendiente"], "SIN_MUESTRA_POSTERIOR")

    def test_fecha_invalida_no_contamina_future(self):
        f = fila(CORTE_SENAL_UTC + 60)
        f["vela_senal_from"] = "NO_ES_FECHA"
        r = validar_prospectivamente([f])
        self.assertEqual(r["registros_con_fecha_invalida"], 1)
        self.assertEqual(r["registros_posteriores_al_corte"], 0)

    def test_politicas_congeladas_no_rechazan_senal_historica_por_elegir_resultado(self):
        r = validar_prospectivamente([
            fila(CORTE_SENAL_UTC + 60, resultado="WIN",
                 accion="CALL_RESISTENCIA_CERCA_SIN_RUPTURA"),
            fila(CORTE_SENAL_UTC + 120, resultado="LOSS"),
        ])
        self.assertEqual(r["escenarios_congelados"]["BASE_SIN_FILTRO_NUEVO"]["oportunidades"], 2)
        self.assertEqual(r["escenarios_congelados"]["SOLO_A_FAVOR_TENDENCIA"]["oportunidades"], 2)
        self.assertEqual(r["escenarios_congelados"]["A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA"]["oportunidades"], 1)
        self.assertEqual(r["escenarios_congelados"]["A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA"]["losses"], 1)


if __name__ == "__main__":
    unittest.main()
