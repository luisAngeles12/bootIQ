"""La meta 60% no se declara ganada si la ventaja OOS es inferior al baseline."""
import unittest
from datetime import datetime, timedelta

from analizar_oportunidades_integrales_practice import analizar


def _fila(dia, minuto, patron, gana):
    fecha = datetime(2026, 11, 1) + timedelta(days=dia, minutes=minuto)
    return {
        "fecha": fecha.isoformat(sep=" "),
        "modo_cuenta_configurado": "PRACTICE",
        "estado": "CERRADA",
        "estado_operacion": "OPERADA_DIRECTA",
        "order_id": f"OID-{dia}-{minuto}-{patron}",
        "direccion": "call",
        "resultado": "20.75" if gana else "-25.0",
        "patron": patron,
    }


class VentajaOOSSobreBaseline(unittest.TestCase):
    def test_winrate_alto_no_valida_si_peor_que_sistema_base(self):
        filas = []
        for dia in range(10):
            for n in range(30):
                # A domina TRAIN; en TEST A gana 80%, B gana 100%.
                filas.append(_fila(dia, n, "A", dia < 7 or n < 24))
                filas.append(_fila(dia, n + 30, "B", dia >= 7))
        resultado = analizar(filas, minimo_train=20, minimo_oos=20)
        candidato = resultado["candidato"]
        self.assertEqual((candidato["variable"], candidato["valor"]), ("patron", "A"))
        self.assertEqual(candidato["test_oos"]["winrate_pct"], 80.0)
        self.assertGreater(candidato["test_oos"]["neto"], 0)
        self.assertGreater(candidato["test_oos"]["wilson_minutos_95_pct"], 50)
        self.assertLess(candidato["diferencia_expectativa_oos_vs_baseline"], 0)
        self.assertFalse(candidato["supera_objetivo_oos"])
        self.assertFalse(candidato["autoriza_operaciones"])

    def test_un_dia_de_test_no_acredita_constancia(self):
        filas = []
        for dia in range(10):
            for n in range(40):
                # A existe en TRAIN y solo en ultimo dia de TEST,
                # aunque el dia final tenga buen PnL/WR.
                if dia < 7 or dia == 9:
                    filas.append(_fila(dia, n, "A", True))
                filas.append(_fila(dia, n + 60, "B", False))
        resultado = analizar(filas, minimo_train=20, minimo_oos=20)
        candidato = resultado["candidato"]
        self.assertEqual((candidato["variable"], candidato["valor"]), ("patron", "A"))
        self.assertEqual(candidato["dias_oos_candidato"], 1)
        self.assertGreater(candidato["test_oos"]["neto"], 0)
        self.assertFalse(candidato["supera_objetivo_oos"])


if __name__ == "__main__":
    unittest.main()
