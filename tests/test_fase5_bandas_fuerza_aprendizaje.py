"""Regresiones Fase 5: bandas de fuerza de evidencia usadas por memoria.

Sin broker, sin lectura/escritura de memoria ni autoridad de trading.
"""
import unittest

from motor_aprendizaje_historico import (
    _banda_fuerza_evidencia,
    _token_evidencia_enriquecida,
)


class BandaFuerzaAprendizajeFase5Test(unittest.TestCase):
    def test_ausentes_y_no_finitos_no_fabrican_fuerza_alta(self):
        for valor in (None, "", True, False, float("nan"),
                      float("inf"), -float("inf"), "NaN", "Infinity"):
            with self.subTest(valor=str(valor)):
                self.assertEqual(_banda_fuerza_evidencia(valor), "")

    def test_bandas_validas_y_limites_no_cambian(self):
        casos = (
            (0, "FZA_0_39"),
            (39.99, "FZA_0_39"),
            (40, "FZA_40_59"),
            (59.99, "FZA_40_59"),
            (60, "FZA_60_74"),
            (74.99, "FZA_60_74"),
            (75, "FZA_75_MAS"),
            (100, "FZA_75_MAS"),
        )
        for fuerza, banda in casos:
            with self.subTest(fuerza=fuerza):
                self.assertEqual(_banda_fuerza_evidencia(fuerza), banda)

    def test_pa_no_finito_no_agrega_banda_superior_a_token(self):
        for fuerza in ("NaN", "Infinity", float("nan"), float("inf")):
            with self.subTest(fuerza=str(fuerza)):
                token = _token_evidencia_enriquecida({
                    "tipo": "IMPULSO", "modulo": "price_action",
                    "categoria": "PRICE_ACTION", "direccion": "CALL",
                    "fuerza": fuerza, "confirmada": False,
                })
                self.assertNotIn("FZA_75_MAS", token)
                self.assertIn("DIR_CALL", token)
                self.assertIn("CONF_NO", token)

    def test_confirmacion_cruda_invalida_no_fabrica_memoria_confirmada(self):
        for confirmada in ("False", "no", "invalida", 2, float("nan"),
                           float("inf"), None):
            with self.subTest(confirmada=str(confirmada)):
                token = _token_evidencia_enriquecida({
                    "tipo": "IMPULSO",
                    "modulo": "price_action",
                    "direccion": "CALL",
                    "confirmada": confirmada,
                })
                self.assertIn("CONF_NO", token)
                self.assertNotIn("CONF_SI", token)

    def test_confirmacion_cruda_valida_conserva_semantica(self):
        for confirmada in (True, 1, "true", "1", "sí", "yes"):
            with self.subTest(confirmada=str(confirmada)):
                token = _token_evidencia_enriquecida({
                    "tipo": "IMPULSO", "direccion": "PUT",
                    "confirmada": confirmada,
                })
                self.assertIn("CONF_SI", token)

    def test_pa_valido_sigue_convirtiendo_escala_a_porcentaje(self):
        token = _token_evidencia_enriquecida({
            "tipo": "IMPULSO", "modulo": "price_action",
            "categoria": "PRICE_ACTION", "direccion": "PUT",
            "fuerza": 0.8, "confirmada": True,
        })
        self.assertIn("FZA_75_MAS", token)
        self.assertIn("CONF_SI", token)


if __name__ == "__main__":
    unittest.main()
