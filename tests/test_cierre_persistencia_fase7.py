"""Regresion D7.7: un cierre PRACTICE no se pierde ante fallo del CSV."""
import time
import unittest
from unittest.mock import patch

import estado
import operaciones


class CierrePersistenciaFase7Tests(unittest.TestCase):
    def test_fallo_csv_conserva_resultado_y_reintento_no_reconsulta_iq(self):
        op = {
            "order_id": "000123",
            "activo": "EURUSD",
            "tipo": "turbo",
            "direccion": "call",
            "patron": "test",
            "hora_apertura": time.time() - 3600,
            "resultado_pendiente_csv": None,
        }
        operaciones_originales = estado.operaciones_abiertas
        cooldown_original = estado.cooldown_activos
        try:
            estado.operaciones_abiertas = [op]
            estado.cooldown_activos = {}
            with patch.object(
                operaciones, "obtener_resultado_operacion", return_value=20.75
            ) as consultar, patch.object(
                operaciones, "actualizar_historial_cierre", side_effect=[False, True]
            ) as persistir, patch.object(
                operaciones, "guardar_operaciones_pendientes"
            ) as guardar, patch.object(
                operaciones, "MODO_CUENTA", "PRACTICE"
            ), patch(
                "monitor_deriva_estrategias.observar_cierre_sombra",
                return_value=None,
            ):
                operaciones.revisar_operaciones_abiertas()
                self.assertEqual(len(estado.operaciones_abiertas), 1)
                self.assertEqual(op["resultado_pendiente_csv"], 20.75)
                self.assertNotIn("EURUSD", estado.cooldown_activos)

                operaciones.revisar_operaciones_abiertas()
                self.assertEqual(estado.operaciones_abiertas, [])
                self.assertIn("EURUSD", estado.cooldown_activos)

                consultar.assert_called_once_with(op)
                self.assertEqual(persistir.call_count, 2)
                self.assertEqual(persistir.call_args_list[0].args, ("000123", 20.75))
                self.assertEqual(persistir.call_args_list[1].args, ("000123", 20.75))
                self.assertEqual(guardar.call_count, 2)
        finally:
            estado.operaciones_abiertas = operaciones_originales
            estado.cooldown_activos = cooldown_original


if __name__ == "__main__":
    unittest.main()
