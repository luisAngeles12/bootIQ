import unittest
from datetime import datetime, timezone

from validar_evidencia_practice import (
    limite_inferior_wilson, verificar_evidencia_sostenida,
)


def ts(dia):
    return int(datetime(2026, 10, dia, tzinfo=timezone.utc).timestamp())


def eventos(wins, losses, calidad="TIEMPO_VERIFICADO", inicio=None):
    filas = ([{"resultado": "WIN", "calidad_tiempo": calidad}] * wins
             + [{"resultado": "LOSS", "calidad_tiempo": calidad}] * losses)
    if inicio is not None:
        filas = [dict(fila, timestamp_senal=inicio + i + 60)
                 for i, fila in enumerate(filas)]
    return filas


class ValidacionEvidenciaPracticeTests(unittest.TestCase):
    def test_captura_37_84_no_esta_validada(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(27), eventos(14, 23, "LATENCIA_NO_REGISTRADA"))
        ])
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertEqual(r["wr_hipotetico"], 37.84)
        self.assertIn("MENOS_DE_TRES_DIAS", r["motivos"])
        self.assertIn("LATENCIA_SIN_VERIFICAR_O_TARDIA", r["motivos"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_pasar_57_en_un_solo_dia_no_basta(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(27), eventos(100, 0))
        ])
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertIn("MENOS_DE_TRES_DIAS", r["motivos"])

    def test_tres_dias_con_muestra_suficiente_solo_evidencia_preliminar(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(26), eventos(70, 10, inicio=ts(26))),
            ("USDINR-OTC", ts(27), eventos(70, 10, inicio=ts(27))),
            ("USDINR-OTC", ts(28), eventos(70, 10, inicio=ts(28))),
        ])
        self.assertEqual(r["estado"], "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO")
        self.assertGreater(r["limite_inferior_95_pct"], 57)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_distingue_aprobacion_57_de_meta_sostenida_60(self):
        # 200 observaciones, 130 WIN: Wilson > 57 % pero < 60 %.
        evidencia_57 = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(26), eventos(65, 35, inicio=ts(26))),
            ("USDINR-OTC", ts(27), eventos(32, 18, inicio=ts(27))),
            ("USDINR-OTC", ts(28), eventos(33, 17, inicio=ts(28))),
        ])
        self.assertEqual(evidencia_57["estado"],
                         "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO")
        self.assertFalse(evidencia_57["objetivo_principal_60_respaldado"])
        self.assertEqual(evidencia_57["minimo_aprobacion_pct"], 57.0)
        self.assertEqual(evidencia_57["objetivo_principal_wr_pct"], 60.0)

        evidencia_60 = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(26), eventos(90, 10, inicio=ts(26))),
            ("USDINR-OTC", ts(27), eventos(90, 10, inicio=ts(27))),
            ("USDINR-OTC", ts(28), eventos(90, 10, inicio=ts(28))),
        ])
        self.assertTrue(evidencia_60["objetivo_principal_60_respaldado"])
        self.assertFalse(evidencia_60["operaciones_autorizadas"])

    def test_dia_con_resultado_malo_impide_validacion(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(26), eventos(80, 0)),
            ("USDINR-OTC", ts(27), eventos(7, 13)),
            ("USDINR-OTC", ts(28), eventos(80, 0)),
        ])
        self.assertIn("SESION_BAJO_OBJETIVO", r["motivos"])
        self.assertEqual(r["estado"], "NO_VALIDADA")

    def test_no_inflar_el_porcentaje_con_sesiones_repetidas(self):
        inicio = ts(26)
        iguales = eventos(50, 0, inicio=inicio)
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", inicio, iguales),
            ("USDINR-OTC", inicio + 1, iguales),
            ("USDINR-OTC", ts(27), eventos(50, 0, inicio=ts(27))),
            ("USDINR-OTC", ts(28), eventos(50, 0, inicio=ts(28))),
        ])
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertIn("EVENTO_DUPLICADO_ENTRE_SESIONES", r["motivos"])

    def test_winrate_perfecto_sin_timestamps_no_valida(self):
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", ts(dia), eventos(70, 10))
            for dia in (26, 27, 28)
        ])
        self.assertEqual(r["estado"], "NO_VALIDADA")
        self.assertIn("SIN_TRAZABILIDAD_TEMPORAL", r["motivos"])

    def test_timestamps_desordenados_o_anteriores_bloquean(self):
        inicio = ts(26)
        filas = eventos(40, 0, inicio=inicio)
        filas[0]["timestamp_senal"] = inicio - 1
        filas[1]["timestamp_senal"] = inicio - 1
        r = verificar_evidencia_sostenida([
            ("USDINR-OTC", inicio, filas),
            ("USDINR-OTC", ts(27), eventos(40, 0, inicio=ts(27))),
            ("USDINR-OTC", ts(28), eventos(40, 0, inicio=ts(28))),
        ])
        self.assertIn("EVENTO_ANTERIOR_A_LA_SESION", r["motivos"])
        self.assertIn("EVENTOS_DESORDENADOS_O_REPETIDOS", r["motivos"])

    def test_reporte_60_distingue_resultados_brutos_de_verificados(self):
        muestras = [
            ("USDINR-OTC", ts(dia), eventos(90, 10, inicio=ts(dia)))
            for dia in (26, 27, 28)
        ]
        # Quince WIN sin tiempo comprobado no deben respaldar la meta 60.
        for sesion in muestras:
            for fila in sesion[2][:5]:
                fila["calidad_tiempo"] = "DETECCION_TARDIA"
        resultado = verificar_evidencia_sostenida(muestras)
        self.assertEqual(resultado["evaluables"], 300)
        self.assertEqual(resultado["evaluables_tiempo_verificado"], 285)
        self.assertEqual(resultado["wins_tiempo_verificado"], 255)
        self.assertEqual(resultado["estado"], "NO_VALIDADA")
        self.assertFalse(resultado["objetivo_principal_60_respaldado"])
        self.assertIn("LATENCIA_SIN_VERIFICAR_O_TARDIA", resultado["motivos"])
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_umbral_100_no_cuenta_resultados_temporalmente_invalidos(self):
        muestras = [
            ("USDINR-OTC", ts(dia), eventos(36, 4, inicio=ts(dia)))
            for dia in (26, 27, 28)
        ]
        # 120 WIN/LOSS brutos, pero 90 validos: la puerta no puede aprobar.
        for sesion in muestras:
            for fila in sesion[2][:10]:
                fila["calidad_tiempo"] = "DETECCION_TARDIA"
        resultado = verificar_evidencia_sostenida(muestras)
        self.assertEqual(resultado["evaluables"], 120)
        self.assertEqual(resultado["evaluables_tiempo_verificado"], 90)
        self.assertIn("MENOS_DE_100_RESULTADOS", resultado["motivos"])
        self.assertEqual(resultado["estado"], "NO_VALIDADA")

    def test_umbral_por_sesion_usa_solo_resultados_verificados(self):
        muestras = [
            ("USDINR-OTC", ts(dia), eventos(17, 3, inicio=ts(dia)))
            for dia in (26, 27, 28)
        ]
        for sesion in muestras:
            for fila in sesion[2][:6]:
                fila["calidad_tiempo"] = "DETECCION_TARDIA"
        resultado = verificar_evidencia_sostenida(muestras)
        self.assertEqual(resultado["evaluables_tiempo_verificado"], 42)
        self.assertIn("MUESTRA_POR_SESION_INSUFICIENTE", resultado["motivos"])
        self.assertFalse(resultado["operaciones_autorizadas"])

    def test_wilson_limita_muestras_pequenas(self):
        self.assertLess(limite_inferior_wilson(6, 10), .57)
        self.assertEqual(limite_inferior_wilson(0, 0), 0.0)


    def test_evento_de_otro_dia_invalida_evidencia_aunque_todo_gane(self):
        muestras = [
            ("USDINR-OTC", ts(dia), eventos(40, 0, inicio=ts(dia)))
            for dia in (26, 27, 28)
        ]
        muestras[0][2][-1]["timestamp_senal"] = ts(27) + 3600
        resultado = verificar_evidencia_sostenida(muestras)
        self.assertEqual(resultado["estado"], "NO_VALIDADA")
        self.assertIn("EVENTO_FUERA_DIA_SESION", resultado["motivos"])


    def test_solapamiento_sin_timestamps_identicos_tampoco_valida(self):
        dia = ts(26)
        # La segunda captura comienza antes de acabar la primera,
        # pero sus senales empiezan despues de la ultima de la primera.
        muestras = [
            ("USDINR-OTC", dia, eventos(40, 0, inicio=dia)),
            ("USDINR-OTC", dia + 45, eventos(40, 0, inicio=dia + 45)),
            ("USDINR-OTC", ts(27), eventos(40, 0, inicio=ts(27))),
            ("USDINR-OTC", ts(28), eventos(40, 0, inicio=ts(28))),
        ]
        resultado = verificar_evidencia_sostenida(muestras)
        self.assertEqual(resultado["estado"], "NO_VALIDADA")
        self.assertIn("SESIONES_SOLAPADAS_MISMO_ACTIVO", resultado["motivos"])
        self.assertNotIn("EVENTO_DUPLICADO_ENTRE_SESIONES", resultado["motivos"])

    def test_sesiones_sin_solapamiento_siguen_siendoseparadas(self):
        dia = ts(26)
        muestras = [
            ("USDINR-OTC", dia, eventos(40, 0, inicio=dia)),
            ("USDINR-OTC", dia + 3600,
             eventos(40, 0, inicio=dia + 3600)),
            ("USDINR-OTC", ts(27), eventos(40, 0, inicio=ts(27))),
            ("USDINR-OTC", ts(28), eventos(40, 0, inicio=ts(28))),
        ]
        resultado = verificar_evidencia_sostenida(muestras)
        self.assertEqual(resultado["estado"], "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO")
        self.assertNotIn("SESIONES_SOLAPADAS_MISMO_ACTIVO", resultado["motivos"])


if __name__ == "__main__":
    unittest.main()
