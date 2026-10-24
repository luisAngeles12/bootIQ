import unittest

from auditoria_historial_contextual import (
    contexto_historico,
    agrupar_cierres_por_contexto,
    diagnosticos_historicos,
    agrupar_cierres_por_diagnostico,
    agrupar_cierres_por_ruta_y_ubicacion,
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

    def test_extrae_motivos_sin_confundir_secciones(self):
        razon = (
            "MERCADO: TENDENCIA_BAJISTA, "
            "VALIDACIÓN MERCADO: PUT permitido a favor de tendencia bajista, "
            "ZONA SR: zona válida, "
            "ACCION PRECIO: acción precio: PUT con soporte cerca; decisión delegada a zonas, "
            "RUPTURA: sin ruptura confirmada de soporte"
        )
        motivos = diagnosticos_historicos({"razon": razon})
        self.assertEqual(motivos["VALIDACION_MERCADO"], "PUT permitido a favor de tendencia bajista")
        self.assertEqual(motivos["ZONA_SR"], "zona válida")
        self.assertEqual(motivos["ACCION_PRECIO"], "acción precio: PUT con soporte cerca; decisión delegada a zonas")
        grupos = agrupar_cierres_por_diagnostico([
            {"estado": "CERRADA", "resultado": "-25", "razon": razon},
            {"estado": "ABIERTA", "resultado": "100", "razon": razon},
        ])
        self.assertEqual(len(grupos), 3)
        self.assertTrue(all(x["losses"] == 1 and x["wins"] == 0 for x in grupos))

    def test_no_mezcla_rutas_r1_r6_en_soporte(self):
        razon = "ACCION PRECIO: acción precio: PUT con soporte cerca; decisión delegada a zonas, RUPTURA: sin ruptura confirmada de soporte"
        base = {"estado": "CERRADA", "razon": razon}
        grupos = agrupar_cierres_por_ruta_y_ubicacion([
            {**base, "core4_reglas": "R1_INDEFINIDO_PREMIUM", "resultado": "-25"},
            {**base, "core4_reglas": "R6_CONT_BAJISTA_IMPULSO_FUERTE", "resultado": "20"},
            {**base, "core4_reglas": "R6_CONT_BAJISTA_IMPULSO_FUERTE", "resultado": "-25"},
        ])
        self.assertEqual(len(grupos), 2)
        por_regla = {g["reglas"]: g for g in grupos}
        self.assertEqual(por_regla["R1_INDEFINIDO_PREMIUM"]["losses"], 1)
        self.assertEqual(por_regla["R6_CONT_BAJISTA_IMPULSO_FUERTE"]["total"], 2)
        self.assertTrue(all(g["ubicacion"] == "PUT_SOPORTE_CERCA" for g in grupos))


if __name__ == "__main__":
    unittest.main()
