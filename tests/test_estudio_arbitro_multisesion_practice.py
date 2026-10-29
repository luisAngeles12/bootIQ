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
        self.assertFalse(r["operaciones_autorizadas"])

    def test_holdout_favorable_no_autoriza_operar(self):
        r = estudiar_eventos_arbitro(sesiones())
        self.assertEqual(r["estado"], "EVIDENCIA_OOS_ARB_SOMBRA")
        self.assertEqual(r["holdout"]["dias"], 3)
        self.assertEqual(r["viabilidad_pago_holdout"]["estado"], "NO_VALIDADA")
        self.assertFalse(r["operaciones_autorizadas"])

    def test_una_sesion_no_establece_evidencia(self):
        r = estudiar_eventos_arbitro([sesiones()[0]])
        self.assertEqual(r["estado"], "ARBITRO_OOS_NO_VALIDADO")
        self.assertIn("DIAS_INSUFICIENTES", r["motivos"])

    def test_duplicados_bloquean_evidencia(self):
        muestras = sesiones()
        repetida = ("USDINR-OTC", ts(1) + 1, eventos(ts(1), 36, 4))
        r = estudiar_eventos_arbitro(muestras + [repetida])
        self.assertIn("ARBITRO_DESARROLLO_NO_VALIDADO", r["motivos"])


if __name__ == "__main__":
    unittest.main()
