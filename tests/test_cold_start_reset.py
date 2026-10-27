import unittest

from motor_aprendizaje_historico import (
    PRIOR_WINRATE,
    evaluar_aprendizaje_historico,
    cargar_aprendizaje,
)


class ColdStartTests(unittest.TestCase):
    def test_memoria_ausente_no_se_reutiliza(self):
        self.assertEqual(
            cargar_aprendizaje("__bootiq_archivo_inexistente_para_test__.csv"),
            {},
        )

    def test_prior_neutro_en_ausencia_de_historia(self):
        self.assertEqual(PRIOR_WINRATE, 50.0)
        r = evaluar_aprendizaje_historico({}, memoria={})
        self.assertFalse(r["aprendizaje_encontrado"])
        self.assertEqual(r["muestra_historica"], 0)
        self.assertEqual(r["probabilidad_estimada"], 50.0)
        self.assertEqual(r["decision_aprendizaje"], "SIN_DATOS")


if __name__ == "__main__":
    unittest.main()
