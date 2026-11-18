"""Validacion del comparador de sesiones PRACTICE, sin broker."""
import copy
import unittest

import comparar_bloques_20_practice as comparar


def bloque(sesion, inicio_id, ganadas=12, ganancia=21.125, perdida=25):
    filas = []
    for i in range(20):
        pn = ganancia if i < ganadas else -perdida
        filas.append({
            "order_id": str(inicio_id+i), "estado": "CERRADA",
            "estado_operacion": "OPERADA_DIRECTA",
            "modo_cuenta_configurado": "PRACTICE",
            "pnl_numerico": pn,
        })
    neto = round(ganadas*ganancia-(20-ganadas)*perdida, 2)
    wr = round(100*ganadas/20, 2)
    return {
        "bloque_inicio": sesion, "estado": "BLOQUE_20_CERRADO",
        "modo": "PRACTICE",
        "resultado": {"total": 20, "ganadas": ganadas,
                      "perdidas": 20-ganadas, "empates": 0,
                      "neto": neto, "winrate_pct": wr},
        "operaciones": filas,
    }


class ComparacionBloquesTest(unittest.TestCase):
    def test_dos_bloques_y_comparacion_independiente(self):
        uno = bloque("20261118T150000Z", 100, 12, 21.125)
        dos = bloque("20261119T150000Z", 200, 10, 21.125)
        original = copy.deepcopy([uno, dos])
        resultado = comparar.comparar_bloques([("z.json", dos), ("a.json", uno)])
        self.assertEqual([uno, dos], original)
        self.assertEqual(resultado["bloques_validos"], 2)
        self.assertEqual(resultado["operaciones"], 40)
        self.assertEqual(resultado["wins"], 22)
        self.assertEqual(resultado["losses"], 18)
        self.assertEqual(resultado["winrate_global_pct"], 55.0)
        self.assertEqual(resultado["neto_acumulado"], 14.75)
        self.assertEqual(resultado["bloques_cumplen_60_y_neto"], 1)
        self.assertEqual(resultado["bloques_no_cumplen"], 1)
        self.assertFalse(resultado["todos_los_bloques_cumplen"])
        self.assertFalse(resultado["autoriza_operaciones"])

    def test_estrategia_y_accion_precio_acumuladas_en_dos_bloques(self):
        primero = bloque("20261118T100000Z", 100, 12, 20.75)
        segundo = bloque("20261118T120000Z", 200, 10, 20.75)
        for informe, indices in ((primero, (0, 1, 16)),
                                 (segundo, (0, 18, 19))):
            for i in indices:
                fila = informe["operaciones"][i]
                fila["patron"] = "pullback alcista a EMA"
                fila["accion_precio"] = "PUT_SOPORTE_CERCA_SIN_RUPTURA"
                fila["origen_autoridad"] = "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"
        resultado = comparar.comparar_bloques([
            ("primero.json", primero), ("segundo.json", segundo)
        ])
        self.assertEqual(resultado["bloques_validos"], 2)
        for campo, valor in (
            ("desglose_estrategias", "pullback alcista a EMA"),
            ("desglose_accion_precio", "PUT_SOPORTE_CERCA_SIN_RUPTURA"),
            ("desglose_autoridades", "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"),
        ):
            grupo = next(x for x in resultado[campo] if x["valor"] == valor)
            self.assertEqual(grupo["n"], 6)
            self.assertEqual(grupo["wins"], 3)
            self.assertEqual(grupo["losses"], 3)
            self.assertEqual(grupo["neto"], -12.75)
            self.assertEqual(grupo["bloques_con_operaciones"], 2)
        self.assertEqual(sum(x["n"] for x in resultado["desglose_estrategias"]), 40)

    def test_excluye_repetidos_incompletos_y_real(self):
        valido = bloque("sesion_A", 100)
        doble = bloque("sesion_B", 100)
        real = bloque("sesion_C", 400)
        real["operaciones"][3]["modo_cuenta_configurado"] = "REAL"
        incompleto = bloque("sesion_D", 500)
        incompleto["estado"] = "INFORME_INCOMPLETO_NO_CONCLUYENTE"
        resultado = comparar.comparar_bloques([
            ("01.json", valido), ("02.json", doble),
            ("03.json", real), ("04.json", incompleto),
        ])
        self.assertEqual(resultado["bloques_validos"], 1)
        self.assertEqual(len(resultado["excluidos"]), 3)
        self.assertEqual({x["motivo"] for x in resultado["excluidos"]},
                         {"ORDER_ID_COMPARTIDO_ENTRE_BLOQUES",
                          "OPERACION_NO_PRACTICE", "NO_CERRADO"})

    def test_no_confunde_resumen_falso_ni_error_de_orden(self):
        b = bloque("sesion_A", 100)
        b["resultado"]["neto"] += 100
        resultado = comparar.comparar_bloques([("x.json", b)])
        self.assertEqual(resultado["bloques_validos"], 0)
        self.assertEqual(resultado["excluidos"][0]["motivo"], "RESUMEN_NO_COINCIDE")
        self.assertFalse(resultado["todos_los_bloques_cumplen"])

    def test_controla_id_duplicado_dentro_de_sesion(self):
        b = bloque("sesion_A", 100)
        b["operaciones"][1]["order_id"] = b["operaciones"][0]["order_id"]
        resultado = comparar.comparar_bloques([("x.json", b)])
        self.assertEqual(resultado["excluidos"][0]["motivo"], "ID_DUPLICADO_INTERNO")

    def test_sin_informes_no_inventa_resultados(self):
        resultado = comparar.comparar_bloques([])
        self.assertEqual(resultado["bloques_validos"], 0)
        self.assertIsNone(resultado["winrate_global_pct"])
        self.assertFalse(resultado["todos_los_bloques_cumplen"])


if __name__ == "__main__":
    unittest.main()
