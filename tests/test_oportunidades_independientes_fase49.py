"""Regresiones de independencia y exclusion de mercados sucios."""
import unittest
from reporte_candidatas_sombra_practice import resumen_oportunidades_independientes


def fila(patron="PULLBACK", direccion="call", resultado="WIN",
         ts=120, activo="USDINR-OTC", calidad="NORMAL",
         tiempo="HIPOTETICO_VELA_COMPLETA_SIN_FILL"):
    return {
        "patron": patron,
        "direccion": direccion,
        "resultado_hipotetico": resultado,
        "vela_senal_from": str(ts),
        "activo": activo,
        "calidad_mercado": calidad,
        "calidad_tiempo": tiempo,
        "decision": "NO_OPERAR",
    }


class Independencia(unittest.TestCase):
    def test_dos_estrategias_un_activo_minuto_cuentan_una_vez(self):
        r = resumen_oportunidades_independientes([
            fila(patron="EMA"), fila(patron="CHOCH")])
        self.assertEqual((r["oportunidades_independientes"], r["wins"]), (1, 1))
        self.assertEqual(r["candidatas_duplicadas_agrupadas"], 1)
        self.assertEqual(r["atribucion_estrategia_sin_ambiguedad"], {})
        self.assertFalse(r["operaciones_autorizadas"])

    def test_call_put_conflictivo_no_infla_porcentaje(self):
        r = resumen_oportunidades_independientes([
            fila(direccion="call", resultado="WIN"),
            fila(direccion="put", resultado="LOSS")])
        self.assertEqual(r["oportunidades_independientes"], 0)
        self.assertEqual(r["oportunidades_con_conflicto_excluidas"], 1)
        self.assertIsNone(r["winrate_proxy_pct"])

    def test_mercado_sucio_excluido_del_recuento(self):
        r = resumen_oportunidades_independientes([
            fila(calidad="SUCIO"), fila(ts=180, calidad="CAOTICO"),
            fila(ts=240, resultado="LOSS")])
        self.assertEqual((r["wins"], r["losses"]), (0, 1))
        self.assertEqual(r["filas_excluidas_por_calidad_o_trazabilidad"], 2)

    def test_sin_trazabilidad_no_cuenta(self):
        r = resumen_oportunidades_independientes([
            fila(tiempo="PENDIENTE_VELA_POSTERIOR")])
        self.assertEqual(r["oportunidades_independientes"], 0)
        self.assertEqual(r["filas_excluidas_por_calidad_o_trazabilidad"], 1)

    def test_senales_distintas_se_cuentan_y_sin_permiso(self):
        r = resumen_oportunidades_independientes([
            fila(ts=120, resultado="WIN"),
            fila(ts=180, resultado="LOSS"),
            fila(ts=240, resultado="EMPATE")])
        self.assertEqual((r["wins"], r["losses"], r["empates"]), (1, 1, 1))
        self.assertEqual(r["winrate_proxy_pct"], 33.33)
        self.assertEqual(r["resultado"], "PROXY_NO_VALIDADO")
        self.assertFalse(r["operaciones_autorizadas"])

if __name__ == "__main__":
    unittest.main()
