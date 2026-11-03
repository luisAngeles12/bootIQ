"""Pruebas del experimento no operativo, sin broker ni cambios de estrategia."""
import unittest
from experimento_alineacion_sombra_practice import alinear, comparar, depurar


def fila(activo="USDINR-OTC", ts=120, direccion="call", tendencia="ALCISTA_NORMAL",
         resultado="WIN", patron="CHOCH alcista", accion="RECHAZO_COMPRADOR_SOPORTE",
         calidad="NORMAL", tiempo="HIPOTETICO_VELA_COMPLETA_SIN_FILL"):
    return {
        "activo": activo, "vela_senal_from": str(ts),
        "direccion": direccion, "estado_tendencia": tendencia,
        "resultado_hipotetico": resultado, "patron": patron,
        "accion_precio": accion, "calidad_mercado": calidad,
        "calidad_tiempo": tiempo, "decision": "NO_OPERAR",
    }


class ExperimentoAlineacion(unittest.TestCase):
    def test_clasificacion_direccional(self):
        self.assertEqual(alinear("call", "ALCISTA_FUERTE"), "A_FAVOR")
        self.assertEqual(alinear("put", "BAJISTA_DEBIL"), "A_FAVOR")
        self.assertEqual(alinear("put", "ALCISTA_NORMAL"), "EN_CONTRA")
        self.assertEqual(alinear("call", "BAJISTA_NORMAL"), "EN_CONTRA")
        self.assertEqual(alinear("put", "INDEFINIDA"), "INDEFINIDA")

    def test_un_activo_minuto_dos_patrones_son_una_oportunidad(self):
        x = fila()
        y = fila(patron="continuación alcista con tendencia")
        r = comparar([x, y])
        s = r["escenarios"]["BASE_SIN_FILTRO_NUEVO"]
        self.assertEqual(s["oportunidades"], 1)
        self.assertEqual((s["wins"], s["losses"]), (1, 0))
        self.assertFalse(r["ordenes_autorizadas"])

    def test_conflicto_call_put_no_se_selecciona_por_resultado(self):
        op, razones = depurar([
            fila(direccion="call", resultado="WIN"),
            fila(direccion="put", resultado="LOSS"),
        ])
        self.assertEqual(len(op), 0)
        self.assertEqual(razones["CONFLICTO_ACTIVO_MINUTO"], 1)

    def test_no_entran_sucios_ni_pendientes(self):
        op, descartes = depurar([
            fila(calidad="SUCIO"),
            fila(activo="OTRO", resultado="", tiempo="PENDIENTE_VELA_POSTERIOR"),
        ])
        self.assertFalse(op)
        self.assertEqual(descartes["MERCADO_NO_APTO"], 1)
        self.assertEqual(descartes["SIN_RESULTADO_TRAZABLE"], 1)

    def test_no_proclama_winrate_validado_aun_con_cien_por_ciento(self):
        r = comparar([fila(), fila(activo="USDBRL-OTC")])
        self.assertEqual(r["escenarios"]["BASE_SIN_FILTRO_NUEVO"]["winrate_proxy_pct"], 100)
        self.assertEqual(r["escenarios"]["BASE_SIN_FILTRO_NUEVO"]["simultaneas_otro_activo"], 1)
        for escenario in r["escenarios"].values():
            self.assertEqual(escenario["validacion_60"], "NO_VALIDADA")
            self.assertFalse(escenario["ordenes_autorizadas"])

    def test_filtro_post_hoc_no_modifica_entrada(self):
        original = fila(accion="CALL_RESISTENCIA_CERCA_SIN_RUPTURA")
        otro = fila(ts=180, direccion="put", tendencia="BAJISTA_NORMAL", resultado="LOSS")
        lista = [original, otro]
        r = comparar(lista)
        self.assertEqual(r["escenarios"]["BASE_SIN_FILTRO_NUEVO"]["oportunidades"], 2)
        self.assertEqual(r["escenarios"]["SOLO_A_FAVOR_TENDENCIA"]["oportunidades"], 2)
        self.assertEqual(
            r["escenarios"]["A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA"]["oportunidades"], 1
        )
        self.assertEqual(original["accion_precio"], "CALL_RESISTENCIA_CERCA_SIN_RUPTURA")


if __name__ == "__main__":
    unittest.main()
