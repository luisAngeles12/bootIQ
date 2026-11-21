"""Evita declarar ventaja ficticia con trades simultaneos PRACTICE."""
import unittest
from datetime import datetime, timedelta

from analizar_oportunidades_integrales_practice import analizar


class TradesSimultaneosTests(unittest.TestCase):
    def fila(self, dia, minuto, numero, patron, gana):
        fecha = datetime(2026, 11, 10) + timedelta(days=dia, minutes=minuto)
        return {
            "fecha": fecha.isoformat(sep=" "),
            "modo_cuenta_configurado": "PRACTICE",
            "estado": "CERRADA",
            "estado_operacion": "OPERADA_DIRECTA",
            "order_id": f"T{dia:02d}-{minuto:03d}-{numero:03d}",
            "direccion": "call",
            "resultado": "20.75" if gana else "-25.0",
            "patron": patron,
        }

    def test_muchas_operaciones_mismo_minuto_no_son_muestra_independiente(self):
        filas = []
        for dia in range(10):
            for numero in range(50):
                filas.append(self.fila(dia, 3, numero, "PATRON_A", True))
                filas.append(self.fila(dia, 4, numero, "PATRON_B", False))
        salida = analizar(filas, minimo_train=20, minimo_oos=20)
        self.assertIsNone(salida["candidato"])
        self.assertEqual(salida["train"]["minutos_distintos"], 14)
        self.assertEqual(salida["candidatos_train_comparados"], 0)

    def test_metricas_reales_siguen_siendo_operaciones_no_minutos(self):
        filas = []
        for dia in range(10):
            for minuto in range(30):
                filas.append(self.fila(dia, minuto, 0, "PATRON_A", minuto % 2 == 0))
                filas.append(self.fila(dia, minuto+30, 1, "PATRON_B", False))
        salida = analizar(filas, minimo_train=20, minimo_oos=20)
        self.assertEqual(salida["operaciones_validas"], 600)
        self.assertEqual(salida["train"]["minutos_distintos"], 420)
        self.assertEqual(salida["train"]["n"], 420)
        self.assertFalse(salida["candidato"]["autoriza_operaciones"])


if __name__ == "__main__":
    unittest.main()
