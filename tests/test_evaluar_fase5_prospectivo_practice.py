import unittest

from evaluar_fase5_prospectivo_practice import evaluar


def fila(oid, patron="CHOCH bajista", regimen="TENDENCIA_LIMPIA",
         resultado="20.75", estado="CERRADA"):
    return {
        "order_id": oid, "patron": patron, "regimen_mercado": regimen,
        "resultado": resultado, "estado": estado,
    }


BASELINE = {"solo_practice": True, "total_filas": 2, "order_ids": ["a", "b"]}


class Fase5ProspectivoTest(unittest.TestCase):
    def test_no_reutiliza_operaciones_del_baseline(self):
        r = evaluar([fila("a"), fila("b")], BASELINE)
        self.assertEqual(r["estado"], "SIN_DATOS_NUEVOS")
        self.assertEqual(r["descartes"]["baseline"], 2)
        self.assertEqual(r["escenarios"]["original"]["conservadas"], 0)

    def test_compara_hipotesis_fijas(self):
        registros = [
            fila("a"),
            fila("c", "pullback alcista a EMA", "TENDENCIA_LIMPIA", "-25"),
            fila("d", "pullback alcista a EMA", "TENDENCIA_SUCIA", "20.75"),
            fila("e", "CHOCH bajista", "TENDENCIA_LIMPIA", "20.75"),
        ]
        r = evaluar(registros, BASELINE)
        self.assertEqual(r["ordenes_nuevas_evaluables"], 3)
        self.assertEqual(r["escenarios"]["original"]["neto_conservado"], 16.5)
        self.assertEqual(r["escenarios"]["filtro_1"]["neto_conservado"], 41.5)
        self.assertEqual(r["escenarios"]["filtro_2"]["neto_conservado"], 20.75)
        self.assertEqual(r["escenarios"]["filtro_2"]["excluidas"], 2)

    def test_rechaza_id_nuevo_duplicado(self):
        with self.assertRaises(ValueError):
            evaluar([fila("c"), fila("c")], BASELINE)

    def test_no_contempla_operaciones_sin_cierre(self):
        r = evaluar([fila("c", estado="ABIERTA")], BASELINE)
        self.assertEqual(r["estado"], "SIN_DATOS_NUEVOS")
        self.assertEqual(r["descartes"]["no_cerrada"], 1)

    def test_no_acepta_baseline_inconsistente(self):
        with self.assertRaises(ValueError):
            evaluar([], {"solo_practice": True, "total_filas": 3,
                         "order_ids": ["a", "b"]})


if __name__ == "__main__":
    unittest.main()
