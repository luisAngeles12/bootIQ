"""Regresiones del corte cronologico previo a memoria experimental."""
import unittest

from auditar_fuente_memoria_practice import auditar_fuente_memoria


def fila(oid, dia, resultado, estado_operacion="OPERADA_DIRECTA"):
    return {
        "fecha": f"{dia}T12:00:00",
        "estado": "CERRADA",
        "estado_operacion": estado_operacion,
        "order_id": str(oid),
        "resultado": str(resultado),
        "patron": "CHOCH bajista",
    }


class AuditoriaFuenteMemoriaTests(unittest.TestCase):
    def test_separa_dias_sin_filtrar_por_ganancia(self):
        filas = [
            fila(1, "2026-11-10", 20.75),
            fila(2, "2026-11-11", -25),
            fila(3, "2026-11-12", -25),
        ]
        r = auditar_fuente_memoria(filas)
        self.assertEqual(r["train"]["n"], 2)
        self.assertEqual(r["train"]["wins"], 1)
        self.assertEqual(r["validacion_reservada"]["n"], 1)
        self.assertEqual(r["validacion_reservada"]["losses"], 1)
        self.assertFalse(r["aprendizaje_activado"])
        self.assertFalse(r["memoria_productiva_modificada"])

    def test_empates_y_duplicados_no_entran(self):
        filas = [fila(1, "2026-11-12", 0),
                 fila(1, "2026-11-12", 20.75),
                 fila(2, "2026-11-12", -25)]
        r = auditar_fuente_memoria(filas)
        self.assertEqual(r["validacion_reservada"]["n"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)
        self.assertEqual(r["descartes"]["ID_AUSENTE_O_DUPLICADO"], 1)

    def test_no_acepta_hipoteticas_para_memoria_ejecutada(self):
        r = auditar_fuente_memoria([
            fila(1, "2026-11-10", 25, estado_operacion="HIPOTETICA"),
            fila(2, "2026-11-10", -25),
        ])
        self.assertEqual(r["train"]["n"], 1)
        self.assertEqual(r["descartes"]["NO_DIRECTA_EJECUTADA"], 1)
        self.assertFalse(r["memoria_experimental_generada"])

    def test_no_asume_zona_ni_convierte_a_epoch(self):
        r = auditar_fuente_memoria([
            fila(1, "2026-11-11", 20.75),
            dict(fila(2, "2026-11-12", -25), fecha="2026-11-12T12:00:00-04:00"),
        ])
        self.assertTrue(r["mezcla_zonas_temporales"])
        self.assertFalse(r["timestamp_epoch_generado"])
        self.assertFalse(r["operaciones_autorizadas"])


if __name__ == "__main__":
    unittest.main()
