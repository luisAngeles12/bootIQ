import unittest

from auditoria_historial_contextual import (
    contexto_historico,
    agrupar_cierres_por_contexto,
)


class HistorialContextualTests(unittest.TestCase):
    def test_recupera_literal_sin_modificar_historial(self):
        fila = {
            "tipo_mercado": "", "estado_tendencia": "",
            "razon": (
                "MERCADO: TENDENCIA_BAJISTA - tendencia moderada, "
                "CALIDAD MERCADO: NORMAL score 61, "
                "TENDENCIA AVANZADA: BAJISTA_NORMAL fuerza 64"
            ),
        }
        contexto, origen = contexto_historico(fila)
        self.assertEqual(contexto["tipo_mercado"], "TENDENCIA_BAJISTA")
        self.assertEqual(contexto["estado_tendencia"], "BAJISTA_NORMAL")
        self.assertEqual(contexto["calidad_mercado"], "NORMAL")
        self.assertEqual(origen["tipo_mercado"], "TEXTO_LITERAL")
        self.assertEqual(fila["tipo_mercado"], "")

    def test_prefiere_estructura_ante_texto_contradictorio(self):
        c, origen = contexto_historico({
            "tipo_mercado": "RANGO", "razon": "MERCADO: TENDENCIA_ALCISTA",
        })
        self.assertEqual(c["tipo_mercado"], "RANGO")
        self.assertEqual(origen["tipo_mercado"], "ESTRUCTURADO")

    def test_separa_resultados_reales_y_omite_no_cerradas(self):
        base = {"patron": "CHOCH alcista", "direccion": "call", "razon": "MERCADO: RANGO"}
        filas = [
            {**base, "estado": "CERRADA", "resultado": "20"},
            {**base, "estado": "CERRADA", "resultado": "-25"},
            {**base, "estado": "ABIERTA", "resultado": "200"},
            {**base, "estado": "CERRADA", "resultado": "0"},
        ]
        grupos, descartadas = agrupar_cierres_por_contexto(filas)
        self.assertEqual((len(grupos), descartadas), (1, 2))
        self.assertEqual((grupos[0]["wins"], grupos[0]["losses"], grupos[0]["pnl"]), (1, 1, -5.0))
        self.assertEqual(agrupar_cierres_por_contexto(filas, minimo=3)[0], [])


if __name__ == "__main__":
    unittest.main()
