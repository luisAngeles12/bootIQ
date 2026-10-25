import unittest

from auditoria_diversidad_temporal import analizar_diversidad


class DiversidadTemporalTests(unittest.TestCase):
    def test_multiples_senales_mismo_minuto_no_simulan_dias_independientes(self):
        filas = [
            {"patron": "CHOCH", "tipo_mercado": "TENDENCIA_ALCISTA",
             "direccion": "CALL", "activo": "AAA",
             "fecha_senal": "1791807060", "resultado_hipotetico": "WIN"},
            {"patron": "CHOCH", "tipo_mercado": "TENDENCIA_ALCISTA",
             "direccion": "CALL", "activo": "BBB",
             "fecha_senal": "1791807060", "resultado_hipotetico": "LOSS"},
            {"patron": "CHOCH", "tipo_mercado": "TENDENCIA_ALCISTA",
             "direccion": "CALL", "activo": "AAA",
             "fecha_senal": "1791807120", "resultado_hipotetico": "WIN"},
        ]
        grupos, descartadas = analizar_diversidad(filas)
        self.assertEqual(descartadas, 0)
        self.assertEqual(len(grupos), 1)
        g = grupos[0]
        self.assertEqual(g["total"], 3)
        self.assertEqual(g["dias_distintos"], 1)
        self.assertEqual(g["minutos_distintos"], 2)
        self.assertEqual(g["activos_distintos"], 2)
        self.assertEqual((g["wins_hipoteticos"], g["losses_hipoteticos"]), (2, 1))
        self.assertEqual(g["porcentaje_dia_dominante"], 100.0)

    def test_dias_distintos_y_fecha_iso_se_unifican_en_utc(self):
        filas = [
            {"patron": "A", "tipo_mercado": "NORMAL", "direccion": "PUT",
             "fecha": "2026-10-12T23:45:00-04:00"},
            {"patron": "A", "tipo_mercado": "NORMAL", "direccion": "PUT",
             "fecha": "2026-10-13T03:45:00Z"},
            {"patron": "A", "tipo_mercado": "NORMAL", "direccion": "PUT",
             "fecha": "2026-10-14T00:00:00Z"},
        ]
        grupos, _ = analizar_diversidad(filas)
        self.assertEqual(grupos[0]["dias_distintos"], 2)
        self.assertEqual(grupos[0]["minutos_distintos"], 2)
        self.assertEqual(grupos[0]["porcentaje_dia_dominante"], 66.67)

    def test_fecha_ausente_no_se_inventa_y_contexto_incompleto_se_excluye(self):
        filas = [
            {"patron": "A", "tipo_mercado": "NORMAL", "direccion": "PUT",
             "activo": "AAA", "fecha_senal": "", "resultado_hipotetico": "WIN"},
            {"patron": "A", "tipo_mercado": "", "direccion": "PUT",
             "resultado_hipotetico": "WIN"},
            None,
        ]
        grupos, descartadas = analizar_diversidad(filas)
        self.assertEqual(descartadas, 2)
        self.assertEqual(grupos[0]["total"], 1)
        self.assertEqual(grupos[0]["sin_fecha"], 1)
        self.assertEqual(grupos[0]["dias_distintos"], 0)
        self.assertIsNone(grupos[0]["porcentaje_dia_dominante"])

    def test_no_convierte_resultado_ejecutado_en_hipotetico(self):
        grupos, _ = analizar_diversidad([{
            "patron": "A", "tipo_mercado": "NORMAL",
            "direccion": "CALL", "resultado": "WIN",
            "estado_operacion": "OPERADA_DIRECTA",
        }])
        self.assertEqual(grupos[0]["wins_hipoteticos"], 0)
        self.assertEqual(grupos[0]["losses_hipoteticos"], 0)


if __name__ == "__main__":
    unittest.main()
