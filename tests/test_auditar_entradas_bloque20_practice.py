"""Auditoria de 20 entradas: solo resultados observados y snapshots CSV."""
import copy
import unittest

from auditar_entradas_bloque20_practice import auditar


def reporte():
    operaciones = []
    for i in range(20):
        riesgo = i < 4
        pnl = -25 if (i < 3 or i >= 10) else 20.75
        operaciones.append({
            "order_id": str(14400000001 + i),
            "estado": "CERRADA", "estado_operacion": "OPERADA_DIRECTA",
            "modo_cuenta_configurado": "PRACTICE",
            "pnl_numerico": pnl, "activo": "TEST-OTC",
            "patron": "CHOCH bajista" if riesgo else "PULLBACK",
            "direccion": "put" if riesgo else "call",
            "accion_precio": "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            if riesgo else "RECHAZO_COMPRADOR_SOPORTE",
            "origen_autoridad": "BOOTSTRAP_PRACTICE_SIN_HISTORIAL",
        })
    wins = sum(x["pnl_numerico"] > 0 for x in operaciones)
    losses = 20-wins
    return {
        "estado": "BLOQUE_20_CERRADO", "modo": "PRACTICE",
        "bloque_inicio": "20261118T120000Z",
        "operaciones": operaciones,
        "resultado": {"total": 20, "ganadas": wins,
                      "perdidas": losses, "empates": 0,
                      "winrate_pct": round(100*wins/20, 2),
                      "neto": round(sum(x["pnl_numerico"] for x in operaciones), 2)}
    }


class AuditarEntradasTests(unittest.TestCase):
    def test_riesgo_zona_bootstrap_cruzado_con_pnl_sin_mutacion(self):
        datos = reporte()
        antes = copy.deepcopy(datos)
        informe = auditar(datos)
        self.assertEqual(datos, antes)
        self.assertEqual(informe["estado"], "AUDITORIA_ENTRADAS_BLOQUE20_PRACTICE")
        self.assertEqual(informe["resultado"]["n"], 20)
        riesgo = informe["riesgo_bootstrap_put_soporte"]
        self.assertEqual(riesgo["n"], 4)
        self.assertEqual(riesgo["wins"], 1)
        self.assertEqual(riesgo["losses"], 3)
        self.assertEqual(riesgo["neto"], -54.25)
        self.assertEqual(len(riesgo["order_ids"]), 4)
        self.assertEqual(informe["riesgo_bootstrap_call_resistencia"]["n"], 0)
        self.assertEqual(sum(x["n"] for x in informe["desglose"]["estrategia"]), 20)
        self.assertFalse(informe["autoriza_operaciones"])
        self.assertFalse(informe["memoria_productiva_modificada"])

    def test_no_acepta_informe_incompleto(self):
        datos = reporte()
        datos["operaciones"].pop()
        r = auditar(datos)
        self.assertEqual(r["estado"], "NO_EVALUABLE")
        self.assertEqual(r["motivo"], "CANTIDAD_INVALIDA")
        self.assertFalse(r["autoriza_operaciones"])

    def test_rechaza_operacion_real_incluso_en_informe_practice(self):
        datos = reporte()
        datos["operaciones"][0]["modo_cuenta_configurado"] = "REAL"
        r = auditar(datos)
        self.assertEqual(r["estado"], "NO_EVALUABLE")
        self.assertEqual(r["motivo"], "OPERACION_NO_PRACTICE")


if __name__ == "__main__":
    unittest.main()
