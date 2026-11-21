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

    def test_agregado_favorable_oculta_jornada_perdedora(self):
        filas = []
        for dia in range(10):
            for minuto in range(30):
                # TRAIN 7 dias: A 100% y B 0%.
                # TEST: A 40%, 90%, 90%; WR total 73.33%
                # pero primer dia pierde dinero.
                if dia < 7:
                    ganar_a = True
                elif dia == 7:
                    ganar_a = minuto < 12
                else:
                    ganar_a = minuto < 27
                filas.append(_fila(dia, minuto, "A", ganar_a))
                filas.append(_fila(dia, minuto + 30, "B", False))
        r = analizar(filas, minimo_train=20, minimo_oos=20)
        c = r["candidato"]
        self.assertEqual((c["variable"], c["valor"]), ("patron", "A"))
        self.assertGreater(c["test_oos"]["winrate_pct"], 60)
        self.assertGreater(c["test_oos"]["neto"], 0)
        self.assertGreater(c["diferencia_expectativa_oos_vs_baseline"], 0)
        self.assertEqual(c["test_por_dia"]["2026-11-08"]["winrate_pct"], 40)
        self.assertLess(c["test_por_dia"]["2026-11-08"]["neto"], 0)
        self.assertFalse(c["jornadas_oos_estables"])
        self.assertFalse(c["supera_objetivo_oos"])
        self.assertFalse(c["autoriza_operaciones"])

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
