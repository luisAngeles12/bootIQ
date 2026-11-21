"""Pruebas del informe PRACTICE; sin broker ni archivos de produccion."""
import unittest

from auditar_calidad_setup_practice import analizar, _rama_reaccion, _rama_reaccion_literal_live


class CalidadSetupPracticeTests(unittest.TestCase):
    def test_etiquetas_y_procedencia_sin_autoridad(self):
        filas = [
            {
                "fecha": "2026-11-10 10:00:00",
                "estado": "CERRADA",
                "estado_operacion": "OPERADA_DIRECTA",
                "modo_cuenta_configurado": "",
                "origen_autoridad": "BOOTSTRAP_PRACTICE_SIN_HISTORIAL",
                "order_id": "12345678901",
                "direccion": "call",
                "resultado": "20.75",
                "calidad_setup": "PREMIUM",
                "patron": "reaccion compradora",
            },
            {
                "fecha": "2026-11-17 10:00:00",
                "estado": "CERRADA",
                "estado_operacion": "OPERADA_DIRECTA",
                "modo_cuenta_configurado": "PRACTICE",
                "order_id": "12345678902",
                "direccion": "put",
                "resultado": "-25",
                "calidad_setup": "PREMIUM",
                "patron": "CHOCH bajista",
            },
            {
                "fecha": "2026-11-17 10:01:00",
                "estado": "CERRADA",
                "estado_operacion": "OPERADA_DIRECTA",
                "modo_cuenta_configurado": "REAL",
                "order_id": "12345678903",
                "direccion": "put",
                "resultado": "20.75",
                "calidad_setup": "PREMIUM",
            },
        ]
        salida = analizar(filas)
        self.assertEqual(salida["total"], 2)
        self.assertEqual(salida["descartes"]["NO_PRACTICE"], 1)
        self.assertEqual(salida["procedencia"]["USUARIO_DECLARADO_LEGADO_SIN_MODO"], 1)
        self.assertEqual(salida["procedencia"]["CSV_MODO_PRACTICE"], 1)
        self.assertEqual(salida["calidades"]["PREMIUM"]["TRAIN"]["wins"], 1)
        self.assertEqual(salida["calidades"]["PREMIUM"]["TEST"]["losses"], 1)
        self.assertEqual(salida["rama_reaccion_por_calidad"]["PREMIUM"]["TRAIN"]["n"], 1)
        self.assertEqual(salida["rama_reaccion_por_calidad"]["PREMIUM"]["TEST"]["n"], 0)
        self.assertFalse(salida["autoriza_operaciones"])
        self.assertFalse(salida["autoriza_real"])
        self.assertEqual(salida["alerta_calibracion_premium"]["estado"],
                         "SIN_EVIDENCIA_SUFICIENTE_DE_INVERSION")

    def test_alerta_calibracion_no_autoriza_operaciones(self):
        filas = []
        for i in range(20):
            for calidad, gana in (("PREMIUM", i < 8), ("BUENA", i < 12)):
                filas.append({
                    "fecha": f"2026-11-18 10:{i:02d}:00",
                    "estado": "CERRADA",
                    "estado_operacion": "OPERADA_DIRECTA",
                    "modo_cuenta_configurado": "PRACTICE",
                    "order_id": f"X{i:03d}{calidad}",
                    "direccion": "call",
                    "resultado": "20.75" if gana else "-25",
                    "calidad_setup": calidad,
                })
        salida = analizar(filas)
        alerta = salida["alerta_calibracion_premium"]
        self.assertEqual(alerta["estado"], "PREMIUM_INFERIOR_A_BUENA_EN_TEST")
        self.assertEqual(alerta["brecha_winrate_test_vs_buena_pp"], -20.0)
        self.assertFalse(salida["autoriza_operaciones"])

    def test_reaccion_acentuada_queda_registrada_como_brecha_live(self):
        fila = {
            "fecha": "2026-11-18 10:00:00",
            "estado": "CERRADA",
            "estado_operacion": "OPERADA_DIRECTA",
            "modo_cuenta_configurado": "PRACTICE",
            "order_id": "ID001",
            "direccion": "call",
            "resultado": "-25",
            "calidad_setup": "PREMIUM",
            "patron": "reacción compradora en soporte",
            "tipo_setup": "INDEFINIDO",
        }
        salida = analizar([fila])
        self.assertEqual(
            salida["reacciones_con_tilde_no_reconocidas_por_condicion_literal"]
                  ["PREMIUM"]["TEST"]["n"], 1,
        )

    def test_rama_reaccion_sigue_condicion_literal_de_entrada(self):
        self.assertTrue(_rama_reaccion({"patron": "reaccion vendedora"}))
        self.assertTrue(_rama_reaccion({"patron": "reacción vendedora en resistencia"}))
        self.assertTrue(_rama_reaccion({"patron": "REACCIÓN COMPRADORA EN SOPORTE"}))
        self.assertFalse(_rama_reaccion_literal_live({"patron": "reacción compradora"}))
        self.assertTrue(_rama_reaccion_literal_live({"patron": "reaccion compradora"}))
        self.assertTrue(_rama_reaccion({"tipo_setup": "RECHAZO_ALCISTA"}))
        self.assertFalse(_rama_reaccion({"patron": "CHOCH bajista"}))


if __name__ == "__main__":
    unittest.main()
