"""Pruebas de particion temporal: ninguna modifica memoria ni decisiones."""
import unittest
from verificar_particion_train_valid_practice import verificar_particion


def fila(activo, fecha, direccion="CALL"):
    return {"activo": activo, "fecha": str(fecha), "direccion": direccion}


class SeparacionCronologicaTests(unittest.TestCase):
    def test_separacion_train_antes_de_validacion(self):
        r = verificar_particion(
            [fila("EURUSD", 1700000000), fila("EURUSD", 1700000060)],
            [fila("EURUSD", 1700000120)],
        )
        self.assertTrue(r["apta_para_experimento_cronologico"])
        self.assertFalse(r["permiso_generar_memoria_productiva"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_solapamiento_temporal_rechazado(self):
        r = verificar_particion(
            [fila("EURUSD", 1700000120)],
            [fila("USDJPY", 1700000060)],
        )
        self.assertFalse(r["separacion_cronologica_estricta"])
        self.assertFalse(r["apta_para_experimento_cronologico"])

    def test_evento_compartido_detectado(self):
        r = verificar_particion(
            [fila("EURUSD", 1700000000)],
            [fila("EURUSD", 1700000000)],
        )
        self.assertEqual(r["eventos_compartidos"], 1)
        self.assertFalse(r["apta_para_experimento_cronologico"])

    def test_fechas_invalidas_y_identidad_incompleta(self):
        r = verificar_particion(
            [fila("EURUSD", "invalida"), fila("", 1700000000)],
            [fila("EURUSD", 1700000060)],
        )
        self.assertEqual(r["train_validos"], 0)
        self.assertFalse(r["apta_para_experimento_cronologico"])

    def test_duplicado_train_local_no_se_considera_dato_independiente(self):
        r = verificar_particion(
            [fila("EURUSD", 1700000000), fila("EURUSD", 1700000000)],
            [fila("USDJPY", 1700000060)],
        )
        self.assertEqual(r["descartes"]["train"]["EVENTO_DUPLICADO_LOCAL"], 1)
        self.assertFalse(r["apta_para_experimento_cronologico"])

    def test_fechas_iso_con_zona(self):
        r = verificar_particion(
            [fila("EURUSD", "2026-11-10T10:00:00+00:00")],
            [fila("EURUSD", "2026-11-11T10:00:00Z")],
        )
        self.assertTrue(r["apta_para_experimento_cronologico"])


if __name__ == "__main__":
    unittest.main()
