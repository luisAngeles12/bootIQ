"""Pruebas de cobertura prospectiva sin contaminar TRAIN."""
import unittest

from auditar_cobertura_memoria_v3_practice import auditar_cobertura


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


class CoberturaMemoriaV3Tests(unittest.TestCase):
    def test_cobertura_aparece_solo_si_train_tiene_muestra(self):
        datos = [
            fila(i, "2026-11-10T10:00:00", 20.75) for i in range(1, 6)
        ] + [fila(6, "2026-11-12T10:00:00", -25)]
        r = auditar_cobertura(datos)
        self.assertEqual(r["train_n"], 5)
        self.assertEqual(r["validacion_n"], 1)
        self.assertEqual(r["validacion_con_fuente_minima"], 1)
        self.assertFalse(r["memoria_generada"])
        self.assertFalse(r["ordenes_autorizadas"])

    def test_validacion_no_entrena_sus_propias_claves(self):
        datos = [fila(1, "2026-11-10T10:00:00", 20.75)] + [
            fila(i, "2026-11-12T10:00:00", 20.75) for i in range(2, 25)
        ]
        r = auditar_cobertura(datos)
        self.assertEqual(r["train_n"], 1)
        self.assertEqual(r["validacion_n"], 23)
        self.assertEqual(r["validacion_con_fuente_minima"], 0)
        self.assertFalse(r["resultado_validacion_usado_para_entrenar"])

    def test_empates_y_duplicados_no_aumentan_muestra(self):
        r = auditar_cobertura([
            fila(1, "2026-11-10T10:00:00", 0),
            fila(1, "2026-11-10T10:00:00", 20.75),
            fila(2, "2026-11-12T10:00:00", -25),
        ])
        self.assertEqual(r["train_n"], 0)
        self.assertEqual(r["validacion_n"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)
        self.assertEqual(r["descartes"]["ID_INVALIDO_O_REPETIDO"], 1)

    def test_prohibe_fechas_naive_y_aware_mezcladas(self):
        with self.assertRaisesRegex(ValueError, "FECHAS_MIXTAS"):
            auditar_cobertura([
                fila(1, "2026-11-11T10:00:00", 20.75),
                fila(2, "2026-11-12T10:00:00-04:00", -25),
            ])


if __name__ == "__main__":
    unittest.main()
