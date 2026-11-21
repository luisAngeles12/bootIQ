"""No promocionar subgrupos CHOCH descubiertos con datos TEST."""
import unittest
from diagnosticar_choch_bajista_practice import diagnosticar


def fila(dia, minuto, n, patron, win, calidad):
    return {
        "order_id": f"{dia}-{minuto}-{n}",
        "fecha": f"2026-11-{dia:02d} 12:{minuto:02d}:00",
        "estado": "CERRADA",
        "estado_operacion": "OPERADA_DIRECTA",
        "modo_cuenta_configurado": "PRACTICE",
        "resultado": "20.75" if win else "-25",
        "patron": patron,
        "calidad_mercado": calidad,
        "direccion": "put",
    }


class DiagnosticoChochTest(unittest.TestCase):
    def test_train_test_y_subgrupos_sin_autorizacion(self):
        filas = []
        for dia in range(10, 20):
            for minuto in range(10):
                # CHOCH tiene buen TRAIN pero pierde en TEST.
                filas.append(fila(dia, minuto, 0, "CHOCH BAJISTA",
                                  dia <= 16, "NORMAL"))
                filas.append(fila(dia, minuto + 20, 1, "OTRO", True, "NORMAL"))
        resultado = diagnosticar(filas, corte="2026-11-16")
        self.assertEqual(resultado["train"]["total"]["n"], 70)
        self.assertEqual(resultado["test"]["total"]["n"], 30)
        self.assertGreater(resultado["train"]["total"]["neto"], 0)
        self.assertLess(resultado["test"]["total"]["neto"], 0)
        self.assertEqual(len(resultado["test"]["por_dia"]), 3)
        self.assertFalse(resultado["autoriza_operaciones"])
        self.assertFalse(resultado["puede_promover_patron"])
        self.assertIn("fechas futuras", resultado["advertencia"])
        calidad = [x for x in resultado["test"]["por_condicion"]
                   if x["campo"] == "calidad_mercado"]
        self.assertEqual(len(calidad), 1)
        self.assertEqual(calidad[0]["valor"], "NORMAL")

    def test_compara_condiciones_train_y_test_sin_ocultar_caida(self):
        filas = []
        for dia in range(10, 20):
            for minuto in range(12):
                registro = fila(dia, minuto, 0, "CHOCH BAJISTA",
                                dia <= 16, "NORMAL")
                registro["accion_precio"] = "PUT_SOPORTE_CERCA_SIN_RUPTURA"
                filas.append(registro)
        salida = diagnosticar(filas, corte="2026-11-16")
        comparados = [
            x for x in salida["comparacion_condiciones_train_test"]
            if x["campo"] == "accion_precio"
            and x["valor"] == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
        ]
        self.assertEqual(len(comparados), 1)
        self.assertEqual(comparados[0]["n_train"], 84)
        self.assertEqual(comparados[0]["n_test"], 36)
        self.assertEqual(comparados[0]["winrate_train_pct"], 100)
        self.assertEqual(comparados[0]["winrate_test_pct"], 0)
        self.assertEqual(comparados[0]["delta_winrate_pp"], -100)
        self.assertFalse(comparados[0]["no_autoriza_operaciones"] is False)
        self.assertTrue(salida["seleccion_por_test_prohibida"])

    def test_subgrupo_train_sin_muestra_test_no_se_declara_ganador(self):
        filas = []
        for dia in range(10, 20):
            for minuto in range(12):
                registro = fila(dia, minuto, 0, "CHOCH BAJISTA", True, "NORMAL")
                registro["pa_tipo"] = "IMPULSO_BAJISTA_FUERTE" if dia <= 16 else "OTRO"
                filas.append(registro)
        salida = diagnosticar(filas, corte="2026-11-16")
        grupo = next(x for x in salida["comparacion_condiciones_train_test"]
                     if x["campo"] == "pa_tipo"
                     and x["valor"] == "IMPULSO_BAJISTA_FUERTE")
        self.assertEqual(grupo["n_test"], 0)
        self.assertIsNone(grupo["winrate_test_pct"])
        self.assertIsNone(grupo["delta_winrate_pp"])
        self.assertTrue(grupo["muestra_test_limitada"])
        self.assertFalse(salida["autoriza_operaciones"])

    def test_no_transforma_hipoteticas_en_operaciones(self):
        filas = [fila(17, 5, 0, "CHOCH BAJISTA", True, "LIMPIO")]
        filas[0]["modo_cuenta_configurado"] = "REAL"
        r = diagnosticar(filas)
        self.assertEqual(r["test"]["total"]["n"], 0)
        self.assertFalse(r["autoriza_operaciones"])

    def test_minimo_invalido_rechazado(self):
        with self.assertRaises(ValueError):
            diagnosticar([], minimo_subgrupo=0)


if __name__ == "__main__":
    unittest.main()
