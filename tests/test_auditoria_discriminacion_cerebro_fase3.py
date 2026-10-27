import unittest
from datetime import datetime, timezone

from auditoria_discriminacion_cerebro_fase3 import auditar_discriminacion


def fila(i, win, autorizada, activo="A"):
    fecha = datetime(2026, 9, 15, tzinfo=timezone.utc).timestamp()+i*60
    return {"fecha_senal": fecha, "resultado_hipotetico": "WIN" if win else "LOSS",
            "decision_estadistica_sombra": "OPERAR_SOMBRA" if autorizada else "CANCELAR",
            "activo": activo, "patron": "X", "direccion": "call"}


class DiscriminacionCerebroFase3Tests(unittest.TestCase):
    def test_discriminacion_y_estratos(self):
        r = auditar_discriminacion([
            fila(0, True, True), fila(1, True, True),
            fila(2, False, False), fila(3, True, False),
        ])
        self.assertEqual(r["autorizadas"]["wins"], 2)
        self.assertEqual(r["rechazadas"]["wins"], 1)
        self.assertEqual(r["estratos_dia_activo_comparables"], 1)
        self.assertEqual(r["diferencia_global"]["diferencia_pp"], 50)
        self.assertFalse(r["autoriza_cambio"])

    def test_rechaza_duplicados_y_no_infiere_lift_vacio(self):
        a = fila(0, True, True)
        with self.assertRaises(ValueError):
            auditar_discriminacion([a, dict(a)])
        r = auditar_discriminacion([a])
        self.assertIsNone(r["diferencia_global"])
        self.assertEqual(r["estratos_dia_activo_comparables"], 0)

    def test_omitir_resultados_sin_cierre(self):
        r = auditar_discriminacion([{"resultado_hipotetico":"EMPATE"}, fila(0, False, False)])
        self.assertEqual(r["senales_omitidas"], 1)
        self.assertEqual(r["rechazadas"]["losses"], 1)


if __name__ == "__main__":
    unittest.main()
