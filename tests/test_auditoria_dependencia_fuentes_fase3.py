import unittest

from auditoria_dependencia_fuentes_fase3 import auditar_dependencia_fuentes


class DependenciaFuentesFase3Tests(unittest.TestCase):
    def test_detecta_igualdad_contadores_sin_inferir_solapamiento(self):
        principal = {"nivel":"CONTEXTO_SETUP", "clave":"A", "total":20,
                     "wins":12, "losses":8}
        respaldo = {"nivel":"FAMILIA", "clave":"B", "total":20,
                    "wins":12, "losses":8}
        r = auditar_dependencia_fuentes([{
            "fuente_probabilidad_principal":repr(principal),
            "fuente_probabilidad_respaldo":repr(respaldo),
        }])
        self.assertEqual(r["conteos"]["CON_AMBAS_FUENTES"], 1)
        self.assertEqual(r["conteos"]["CONTADORES_WIN_LOSS_IDENTICOS"], 1)
        self.assertEqual(r["conteos"].get("CLAVES_IGUALES", 0), 0)
        self.assertFalse(r["solapamiento_individual_verificable"])
        self.assertFalse(r["autoriza_cambio"])

    def test_no_confunde_mayor_respaldo_con_prueba_de_solapamiento(self):
        r = auditar_dependencia_fuentes([{
            "fuente_probabilidad_principal":
                {"nivel":"CONTEXTO_SETUP", "clave":"A", "total":20, "wins":12, "losses":8},
            "fuente_probabilidad_respaldo":
                {"nivel":"FAMILIA", "clave":"B", "total":50, "wins":25, "losses":25},
        }])
        self.assertEqual(r["conteos"]["RESPALDO_MUESTRA_MAYOR"], 1)
        self.assertEqual(r["conteos"]["CONTEOS_COMPARABLES"], 1)
        self.assertFalse(r["identidades_de_observaciones_disponibles"])

    def test_fuentes_faltantes_o_malformadas_no_fabrican_comparacion(self):
        r = auditar_dependencia_fuentes([
            {"fuente_probabilidad_principal":"__import__('os').system('false')"},
            {"fuente_probabilidad_principal":"{'nivel':'A'}",
             "fuente_probabilidad_respaldo":"{'nivel':'B'}"},
            {"fuente_probabilidad_principal":"{'total':5,'wins':4,'losses':1}"},
        ])
        self.assertEqual(r["conteos"]["SIN_PRINCIPAL"], 1)
        self.assertEqual(r["conteos"]["CONTEOS_NO_COMPARABLES"], 1)
        self.assertEqual(r["conteos"]["SIN_RESPALDO"], 1)


if __name__ == "__main__":
    unittest.main()
