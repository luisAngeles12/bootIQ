"""Regresion F12.20: PREMIUM no permite reaccion sin PA confirmada.

No conecta al broker ni permite REAL. La funcion evaluada solo inspecciona
la senal y devuelve motivo de espera o None.
"""
import unittest
from entrada import motivo_pendiente_por_accion_precio


class ReaccionPremiumTests(unittest.TestCase):
    def senal(self, **cambios):
        base = {
            "direccion": "call",
            "patron": "reaccion compradora en soporte",
            "tipo_setup": "RECHAZO_ALCISTA",
            "calidad_setup": "PREMIUM",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
        }
        base.update(cambios)
        return base

    def test_premium_sin_price_action_espera(self):
        senal = self.senal()
        self.assertEqual(
            motivo_pendiente_por_accion_precio(senal),
            "ESPERANDO_CONFIRMACION_RECHAZO",
        )
        self.assertEqual(
            senal["entrada_auditoria_motivo_veto"],
            "PREMIUM_REACCION_SIN_PA_CONFIRMADA",
        )

    def test_premium_pa_contrario_espera(self):
        self.assertEqual(
            motivo_pendiente_por_accion_precio(self.senal(
                pa_tipo="RECHAZO_VENDEDOR_CONFIRMADO", pa_direccion="PUT",
            )),
            "ESPERANDO_CONFIRMACION_RECHAZO",
        )

    def test_premium_call_confirmado_no_impone_espera(self):
        self.assertIsNone(motivo_pendiente_por_accion_precio(self.senal(
            pa_tipo="RECHAZO_COMPRADOR_CONFIRMADO", pa_direccion="CALL",
        )))

    def test_premium_put_confirmado_no_impone_espera(self):
        self.assertIsNone(motivo_pendiente_por_accion_precio(self.senal(
            direccion="put", patron="reaccion vendedora en resistencia",
            tipo_setup="RECHAZO_BAJISTA",
            pa_tipo="RECHAZO_VENDEDOR_CONFIRMADO", pa_direccion="PUT",
        )))

    def test_buena_conserva_comportamiento(self):
        self.assertIsNone(motivo_pendiente_por_accion_precio(self.senal(
            calidad_setup="BUENA",
        )))

    def test_riesgo_critico_siempre_veta(self):
        self.assertEqual(
            motivo_pendiente_por_accion_precio(self.senal(
                riesgo_estructural_critico_setup=True,
                pa_tipo="RECHAZO_COMPRADOR_CONFIRMADO",
                pa_direccion="CALL",
            )),
            "CANCELAR_PROTOCOLO_RIESGO_CRITICO",
        )

    def test_ruptura_prioritaria_sigue_esperando(self):
        self.assertEqual(
            motivo_pendiente_por_accion_precio(self.senal(
                accion_precio="CALL_RESISTENCIA_CERCA_SIN_RUPTURA",
                pa_tipo="RECHAZO_COMPRADOR_CONFIRMADO",
                pa_direccion="CALL",
            )),
            "ESPERANDO_RUPTURA_RESISTENCIA",
        )


if __name__ == "__main__":
    unittest.main()
