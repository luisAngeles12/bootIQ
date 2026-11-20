"""Regresiones de la investigación sombra por interacciones sin broker."""
import unittest
from analizar_interacciones_sombra_practice import analizar


def fila(dia, i, resultado="WIN", patron="CHOCH"):
    return {
        "activo": "USDINR-OTC", "patron": patron, "direccion": "call",
        "vela_senal_from": str((21000+dia)*86400 + i*60),
        "resultado_hipotetico": resultado,
        "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
        "calidad_mercado": "NORMAL", "decision": "NO_OPERAR",
        "estado_tendencia": "ALCISTA_NORMAL",
        "accion_precio": "RECHAZO_COMPRADOR_SOPORTE",
    }


class InteraccionesSombraTests(unittest.TestCase):
    def test_split_por_dias_y_sin_autoridad(self):
        f = [fila(d, i, "WIN" if i % 5 else "LOSS")
             for d in range(10) for i in range(10)]
        r = analizar(f, min_train=20, min_valid=10)
        self.assertEqual(len(r["dias_train"]), 7)
        self.assertEqual(len(r["dias_validacion_posterior"]), 3)
        self.assertEqual(r["interacciones_con_muestra_suficiente"], 1)
        self.assertFalse(r["promueve_estrategia"])
        self.assertFalse(r["autoriza_real"])

    def test_perdida_posterior_no_se_oculta(self):
        f = [fila(d, i, "WIN" if d < 7 else "LOSS")
             for d in range(10) for i in range(10)]
        r = analizar(f, min_train=10, min_valid=10)
        h = r["interacciones"][0]
        self.assertEqual(h["train"]["acierto_pct"], 100)
        self.assertEqual(h["validacion_posterior"]["acierto_pct"], 0)
        self.assertFalse(h["mejora_replicada_60_proxy"])

    def test_contradiccion_entre_patrones_se_excluye(self):
        f = [fila(d, i) for d in range(10) for i in range(10)]
        f.append(fila(0, 0, patron="OTRO"))
        r = analizar(f, min_train=10, min_valid=10)
        self.assertEqual(r["sin_patron_unico"], 1)
        self.assertEqual(r["oportunidades_depuradas"], 100)

    def test_sin_dias_no_inventa_validacion(self):
        f = [fila(d, i) for d in range(3) for i in range(2)]
        r = analizar(f)
        self.assertEqual(r["estado"], "JORNADAS_INSUFICIENTES")
        self.assertFalse(r["autoriza_real"])

    def test_descarta_calidad_sucia(self):
        f = [fila(d, i) for d in range(10) for i in range(10)]
        f[0]["calidad_mercado"] = "SUCIO"
        r = analizar(f, min_train=10, min_valid=10)
        self.assertEqual(r["descartes"]["MERCADO_NO_APTO"], 1)

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            analizar([], min_train=0)
        with self.assertRaises(ValueError):
            analizar([], proporcion_dias_train=1)


if __name__ == "__main__":
    unittest.main()
