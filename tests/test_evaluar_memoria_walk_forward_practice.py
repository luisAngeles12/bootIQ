"""Regresiones aisladas de memoria V3 walk-forward PRACTICE."""
import unittest
from unittest.mock import patch

import evaluar_memoria_walk_forward_practice as wf


def row(day, k, pnl):
    return {
        "order_id": str(day*1000+k), "fecha": f"2026-11-{day:02d} 12:00:00",
        "estado": "CERRADA", "estado_operacion": "OPERADA_DIRECTA",
        "modo_cuenta_configurado": "PRACTICE", "resultado": str(pnl),
        "direccion": "CALL", "patron": "CHOCH alcista",
        "tipo_mercado": "TENDENCIA_ALCISTA",
    }


def rows():
    return [row(day, k, 20.75 if k % 2 else -25)
            for day in range(10, 20) for k in range(10)]


class WalkForwardV3Test(unittest.TestCase):
    def test_dias_futuros_jamas_entrenan_al_dia_actual(self):
        registros = rows()
        llamados = []
        original = wf.mah.generar_aprendizaje_desde_resultados

        def auditor(resultados, **kwargs):
            valores = list(resultados)
            llamado = len(valores)
            llamados.append(llamado)
            self.assertTrue(all(
                int(x["order_id"])//1000 < 10 + llamado//10
                for x in valores
            ))
            self.assertTrue(all(x["resultado"] in {"WIN", "LOSS"} for x in valores))
            return original(valores, **kwargs)

        with patch.object(wf.mah, "generar_aprendizaje_desde_resultados", side_effect=auditor):
            result = wf.evaluar_walk_forward(registros)
        self.assertEqual(llamados, [20,30,40,50,60,70,80,90])
        self.assertEqual(result["dias_test_evaluados"], 8)
        self.assertEqual(result["baseline_dias_test"]["n"], 80)
        self.assertFalse(result["autoriza_operaciones"])
        self.assertFalse(result["memoria_productiva_modificada"])

    def test_resultado_futuro_no_cambia_dias_test_anteriores(self):
        a = wf.evaluar_walk_forward(rows())
        changed = rows()
        for x in changed:
            if x["fecha"].startswith("2026-11-19"):
                x["resultado"] = "20.75"
        b = wf.evaluar_walk_forward(changed)
        self.assertEqual(a["cortes"][:-1], b["cortes"][:-1])
        self.assertNotEqual(a["cortes"][-1]["test"], b["cortes"][-1]["test"])

    def test_sin_datos_no_afirma_60(self):
        r = wf.evaluar_walk_forward([row(10,i,20) for i in range(30)])
        self.assertEqual(r["dias_test_evaluados"],0)
        self.assertFalse(r["supera_60_y_neto"])
        self.assertFalse(r["muestra_seleccion_suficiente"])

    def test_winrate_global_60_no_es_constancia_20(self):
        # Dos ventanas separadas de ganancia/perdida pueden dar 60% global
        # mientras una ventana intermedia rompe el objetivo.
        registros = [row(day,k,20.75) for day in range(10,12) for k in range(10)]
        registros += [row(day,k,-25 if 12 <= day <= 14 else 20.75)
                      for day in range(12,20) for k in range(10)]
        with patch.object(wf.mah, "evaluar_aprendizaje_historico", return_value={
            "fuente_probabilidad_principal": {"nivel": "FAMILIA", "clave": "FAMILIA|X"},
            "probabilidad_estimada": 70.0,
            "muestra_historica": 25,
        }):
            resultado = wf.evaluar_walk_forward(registros)
        self.assertGreaterEqual(resultado["seleccion_probabilidad_v3_diagnostica"]["winrate_pct"],60)
        self.assertGreater(resultado["seleccion_probabilidad_v3_diagnostica"]["neto"],0)
        self.assertGreater(resultado["ventanas_moviles_20_bajo_objetivo"],0)
        self.assertFalse(resultado["supera_60_y_neto"])

    def test_ventanas_favorables_son_observacion_no_permiso(self):
        registros = [row(day,k,20.75) for day in range(10,20) for k in range(10)]
        with patch.object(wf.mah, "evaluar_aprendizaje_historico", return_value={
            "fuente_probabilidad_principal": {"nivel": "FAMILIA", "clave": "FAMILIA|X"},
            "probabilidad_estimada": 70.0,
            "muestra_historica": 25,
        }):
            resultado = wf.evaluar_walk_forward(registros)
        self.assertTrue(resultado["consistencia_20_y_neto_observada"])
        self.assertEqual(resultado["ventanas_moviles_20_bajo_objetivo"],0)
        self.assertFalse(resultado["autoriza_operaciones"])

    def test_real_y_abiertas_no_entran_en_test(self):
        registros = rows() + [
            {**row(19,100,-25), "modo_cuenta_configurado":"REAL"},
            {**row(19,101,20), "estado":"ABIERTA"},
        ]
        result = wf.evaluar_walk_forward(registros)
        self.assertEqual(result["baseline_dias_test"]["n"],80)
        self.assertEqual(result["descartes"]["NO_PRACTICE"],1)
        self.assertEqual(result["descartes"]["NO_CERRADA"],1)


if __name__ == "__main__":
    unittest.main()
