"""Regresiones: historial V3 frente a bootstrap, sin broker."""
import unittest

from diagnosticar_uso_memoria_v3_practice import auditar


def fila(oid, pnl, ruta="BOOTSTRAP_PRACTICE_SIN_HISTORIAL", muestra="0",
         fuente="", fecha="2026-11-17 10:00:00", modo="PRACTICE",
         estado="CERRADA"):
    return {
        "order_id": str(oid), "estado": estado, "fecha": fecha,
        "estado_operacion": "OPERADA_DIRECTA", "modo_cuenta_configurado": modo,
        "resultado": str(pnl), "origen_autoridad": ruta,
        "muestra_probabilidad": muestra,
        "clave_probabilidad_principal": fuente,
        "patron": "CHOCH bajista", "activo": "USDCLP-OTC",
    }


class UsoMemoriaTest(unittest.TestCase):
    def test_cobertura_y_rentabilidad_por_ruta(self):
        r = auditar([
            fila(1,-25), fila(2,-25),
            fila(3,20.75,"CEREBRO_V3","30","CHOCH|PUT"),
            fila(4,20.75,"CEREBRO_V3","40","CHOCH|PUT"),
        ])
        self.assertEqual(r["total_cierres_evaluables"],4)
        self.assertEqual(r["cobertura_v3_con_fuente_pct"],50)
        self.assertEqual(r["participacion_bootstrap_pct"],50)
        self.assertEqual(r["rutas"]["BOOTSTRAP_SIN_MEMORIA"]["neto"],-50)
        self.assertEqual(r["rutas"]["V3_CON_FUENTE_Y_MUESTRA"]["neto"],41.5)
        self.assertFalse(r["autoriza_operaciones"])

    def test_datos_pendientes_real_y_duplicados_no_contaminan(self):
        r = auditar([
            fila(1,20), fila(1,-25), fila(2,25,estado="ABIERTA"),
            fila(3,20,modo="REAL"), fila(4,0), fila(5,float("nan")),
        ])
        self.assertEqual(r["total_cierres_evaluables"],1)
        self.assertEqual(r["descartes"]["NO_CERRADA"],1)
        self.assertEqual(r["descartes"]["NO_PRACTICE"],1)
        self.assertEqual(r["descartes"]["ORDER_ID_DUPLICADO"],1)
        self.assertEqual(r["descartes"]["EMPATE"],1)
        self.assertEqual(r["descartes"]["ID_O_RESULTADO_INVALIDO"],1)

    def test_muestra_sin_clave_no_equivale_a_memoria_utilizable(self):
        r = auditar([fila(1,-25,"CEREBRO_V3","30","")])
        self.assertEqual(r["cobertura_v3_con_fuente_pct"],0)
        self.assertEqual(r["rutas"]["MUESTRA_SIN_CLAVE_PRINCIPAL"]["n"],1)


if __name__ == "__main__":
    unittest.main()
