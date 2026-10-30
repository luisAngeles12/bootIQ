"""Evidencia sostenida del arbitro completo sin mezclar estrategias."""
import unittest
from datetime import datetime, timezone

from estudio_arbitro_multisesion_practice import estudiar_eventos_arbitro


def ts(dia):
    return int(datetime(2026, 10, dia, tzinfo=timezone.utc).timestamp())


def eventos(inicio, wins, losses):
    return [
        {"timestamp_senal": inicio + 60 * (i + 1),
         "direccion": "call",
         "resultado": "WIN" if i < wins else "LOSS",
         "calidad_tiempo": "TIEMPO_VERIFICADO",
         "operable": False}
        for i in range(wins + losses)
    ]


def sesiones(gana_holdout=True):
    return [
        ("USDINR-OTC", ts(dia),
         eventos(ts(dia), 36 if dia <= 7 or gana_holdout else 5,
                 4 if dia <= 7 or gana_holdout else 35))
        for dia in range(1, 11)
    ]


class EstudioArbitroMultisesionTests(unittest.TestCase):
    def test_dias_futuros_bajos_impiden_validacion(self):
        r = estudiar_eventos_arbitro(sesiones(gana_holdout=False))
        self.assertEqual(r["estado"], "ARBITRO_OOS_NO_VALIDADO")
        self.assertIn("ARBITRO_HOLDOUT_NO_VALIDADO", r["motivos"])
        self.assertEqual(r["dias_holdout"], 3)
        self.assertFalse(r["objetivos_arbitro"]["principal_60_oos_respaldado"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_holdout_favorable_no_autoriza_operar(self):
        r = estudiar_eventos_arbitro(sesiones())
        self.assertEqual(r["estado"], "EVIDENCIA_OOS_ARB_SOMBRA")
        self.assertEqual(r["holdout"]["dias"], 3)
        self.assertEqual(r["viabilidad_pago_holdout"]["estado"], "NO_VALIDADA")
        self.assertFalse(r["operaciones_autorizadas"])
        self.assertTrue(r["objetivos_arbitro"]["minimo_57_oos_respaldado"])
        self.assertTrue(r["objetivos_arbitro"]["principal_60_oos_respaldado"])
        self.assertFalse(r["objetivos_arbitro"]["viabilidad_economica_holdout_validada"])
        self.assertFalse(r["objetivos_arbitro"]["operaciones_autorizadas"])

    def test_una_sesion_no_establece_evidencia(self):
        r = estudiar_eventos_arbitro([sesiones()[0]])
        self.assertEqual(r["estado"], "ARBITRO_OOS_NO_VALIDADO")
        self.assertIn("DIAS_INSUFICIENTES", r["motivos"])

    def test_duplicados_bloquean_evidencia(self):
        muestras = sesiones()
        repetida = ("USDINR-OTC", ts(1) + 1, eventos(ts(1), 36, 4))
        r = estudiar_eventos_arbitro(muestras + [repetida])
        self.assertIn("ARBITRO_DESARROLLO_NO_VALIDADO", r["motivos"])


    def test_senal_del_holdout_marcada_como_desarrollo_bloquea(self):
        muestras = sesiones()
        # Ultima senal del dia 7 se falsifica con timestamp del dia 8.
        # Nunca debe contarse como evidencia de desarrollo.
        muestras[6][2][-1]["timestamp_senal"] = ts(8) + 5
        resultado = estudiar_eventos_arbitro(muestras)
        self.assertEqual(resultado["estado"], "ARBITRO_OOS_NO_VALIDADO")
        self.assertIn("ARBITRO_DESARROLLO_NO_VALIDADO", resultado["motivos"])
        self.assertIn("EVENTO_FUERA_DIA_SESION",
                      resultado["desarrollo"]["motivos"])


    def test_evento_marcado_operable_invalida_estudio_sombra(self):
        muestras = sesiones()
        muestras[8][2][0]["operable"] = True
        r = estudiar_eventos_arbitro(muestras)
        self.assertEqual(r["estado"], "ARBITRO_OOS_NO_VALIDADO")
        self.assertIn("ARBITRO_HOLDOUT_AUTORIZACION_INESPERADA", r["motivos"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_direccion_invalida_no_se_contabiliza_como_evidencia_valida(self):
        muestras = sesiones()
        muestras[2][2][0]["direccion"] = None
        r = estudiar_eventos_arbitro(muestras)
        self.assertEqual(r["estado"], "ARBITRO_OOS_NO_VALIDADO")
        self.assertIn("ARBITRO_DESARROLLO_DIRECCION_INVALIDA", r["motivos"])
        self.assertFalse(r["operaciones_autorizadas"])


if __name__ == "__main__":
    unittest.main()
