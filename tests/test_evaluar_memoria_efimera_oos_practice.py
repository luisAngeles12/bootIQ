"""Pruebas de evaluacion OOS con memoria efimera V3."""
import unittest

from evaluar_memoria_efimera_oos_practice import evaluar_oos_memoria


def fila(oid, fecha, resultado, patron="CHOCH bajista"):
    return {
        "fecha": fecha,
        "estado": "CERRADA",
        "estado_operacion": "OPERADA_DIRECTA",
        "order_id": str(oid),
        "resultado": str(resultado),
        "activo": "EURUSD-OTC",
        "direccion": "PUT",
        "patron": patron,
        "familia_setup": patron,
        "tipo_mercado": "RANGO",
        "calidad_mercado": "NORMAL",
        "estado_tendencia": "BAJISTA_NORMAL",
    }


class MemoriaEfimeraOOSTests(unittest.TestCase):
    def test_modelo_se_entrena_antes_del_corte(self):
        train = [
            fila(i, "2026-11-10T10:00:00", 20.75)
            for i in range(1, 21)
        ]
        validacion = [fila(21, "2026-11-12T10:00:00", -25)]
        r = evaluar_oos_memoria(train + validacion)
        self.assertEqual(r["train_n"], 20)
        self.assertEqual(r["validacion_n"], 1)
        self.assertEqual(r["senales_sin_principal"], 0)
        self.assertIsNotNone(r["brier_modelo"])
        self.assertFalse(r["archivos_escritos"])
        self.assertFalse(r["ordenes_autorizadas"])

    def test_resultado_validacion_no_altera_prediccion(self):
        train = [
            fila(i, "2026-11-11T10:00:00", -25)
            for i in range(1, 19)
        ]
        ganadora = fila(20, "2026-11-12T10:00:00", 20.75)
        perdedora = fila(20, "2026-11-12T10:00:00", -25)
        a = evaluar_oos_memoria(train + [ganadora])
        b = evaluar_oos_memoria(train + [perdedora])
        self.assertEqual(a["claves_efimeras"], b["claves_efimeras"])
        self.assertEqual(a["probabilidad_modelo_min_pct"], b["probabilidad_modelo_min_pct"])
        self.assertEqual(a["probabilidad_modelo_max_pct"], b["probabilidad_modelo_max_pct"])
        self.assertFalse(a["resultado_validacion_usado_en_memoria"])

    def test_entrenamiento_insuficiente_no_crea_principal(self):
        r = evaluar_oos_memoria([
            fila(1, "2026-11-10T10:00:00", 20.75),
            fila(2, "2026-11-12T10:00:00", -25),
        ])
        self.assertEqual(r["senales_sin_principal"], 1)
        self.assertEqual(r["validacion_n"], 1)

    def test_empate_no_influye_en_modelo(self):
        r = evaluar_oos_memoria([
            fila(1, "2026-11-10T10:00:00", 0),
            fila(2, "2026-11-12T10:00:00", -25),
        ])
        self.assertEqual(r["train_n"], 0)
        self.assertEqual(r["descartes"]["EMPATE"], 1)
        self.assertFalse(r["memoria_productiva_modificada"])


if __name__ == "__main__":
    unittest.main()
