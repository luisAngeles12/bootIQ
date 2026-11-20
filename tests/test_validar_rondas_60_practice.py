"""Regresiones sin broker para el gate prospectivo 3/4 x 20."""
import unittest
from datetime import datetime, timedelta, timezone
from validar_rondas_60_practice import evaluar

FREEZE = "2026-11-19T00:00:00Z"


def datos(n=80, wins_por_ronda=12, loss=-25, win=20.75):
    comienzo = datetime(2026, 11, 20, tzinfo=timezone.utc)
    filas = []
    for i in range(n):
        ganado = i % 20 < wins_por_ronda
        filas.append({"ronda_id": "R" + str(i // 20 + 1),
                      "order_id": str(i + 1), "fecha_cierre": (comienzo + timedelta(minutes=i * 30)).isoformat(),
                      "estado": "CERRADA", "tipo_cuenta": "PRACTICE",
                      "resultado": "WIN" if ganado else "LOSS",
                      "neto": str(win if ganado else loss), "familia": "CHOCH",
                      "origen_autoridad": "V3_PROSPECTIVA"})
    return filas


class Rondas60PracticeTests(unittest.TestCase):
    def test_cuatro_rondas_con_neto_y_dias_distintos(self):
        r = evaluar(datos(), FREEZE)
        self.assertEqual(r["resultado_observado_3_4_rondas"], "CUMPLE")
        self.assertEqual(r["rondas_aprobadas"], 4)
        self.assertFalse(r["procedencia_broker_certificada"])
        self.assertFalse(r["autoriza_real"])

    def test_tres_rondas_permitidas(self):
        r = evaluar(datos(60), FREEZE, 3)
        self.assertEqual(r["resultado_observado_3_4_rondas"], "CUMPLE")

    def test_ronda_fallida_no_se_oculta(self):
        filas = datos()
        filas[21]["resultado"], filas[21]["neto"] = "LOSS", "-25"
        r = evaluar(filas, FREEZE)
        self.assertEqual(r["resultado_observado_3_4_rondas"], "NO_DEMOSTRADO")
        self.assertEqual(r["rondas_aprobadas"], 3)

    def test_muestra_incompleta_no_certifica(self):
        r = evaluar(datos(79), FREEZE)
        self.assertEqual(r["resultado_observado_3_4_rondas"], "NO_DEMOSTRADO")

    def test_pnl_negativo_no_vale_con_60(self):
        r = evaluar(datos(win=0.01), FREEZE)
        self.assertEqual(r["rondas_aprobadas"], 0)

    def test_rechaza_bootstrap(self):
        filas = datos(1)
        filas[0]["origen_autoridad"] = "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"
        with self.assertRaisesRegex(ValueError, "BOOTSTRAP"):
            evaluar(filas, FREEZE)

    def test_rechaza_real_y_modo_faltante(self):
        for modo in ("REAL", ""):
            filas = datos(1)
            filas[0]["tipo_cuenta"] = modo
            with self.subTest(modo=modo), self.assertRaises(ValueError):
                evaluar(filas, FREEZE)

    def test_rechaza_fechas_precongelacion(self):
        filas = datos(1)
        filas[0]["fecha_cierre"] = FREEZE
        with self.assertRaisesRegex(ValueError, "NO_PROSPECTIVA"):
            evaluar(filas, FREEZE)

    def test_rechaza_duplicados(self):
        filas = datos(2)
        filas[1]["order_id"] = filas[0]["order_id"]
        with self.assertRaisesRegex(ValueError, "DUPLICADO"):
            evaluar(filas, FREEZE)

    def test_rechaza_orden_temporal_invertido(self):
        filas = datos(2)
        filas[0], filas[1] = filas[1], filas[0]
        with self.assertRaisesRegex(ValueError, "CRONOLOGIA"):
            evaluar(filas, FREEZE)

    def test_rechaza_rondas_intercaladas(self):
        filas = datos(3)
        filas[0]["ronda_id"] = "A"
        filas[1]["ronda_id"] = "B"
        filas[2]["ronda_id"] = "A"
        with self.assertRaisesRegex(ValueError, "INTERCALADA"):
            evaluar(filas, FREEZE)

    def test_rechaza_81_operaciones(self):
        with self.assertRaisesRegex(ValueError, "EXCEDEN"):
            evaluar(datos(100), FREEZE)

    def test_sin_dos_dias_no_da_por_demostrado(self):
        filas = datos()
        for i, fila in enumerate(filas):
            fila["fecha_cierre"] = (datetime(2026, 11, 20, tzinfo=timezone.utc) + timedelta(minutes=i)).isoformat()
        r = evaluar(filas, FREEZE)
        self.assertEqual(r["rondas_aprobadas"], 4)
        self.assertEqual(r["resultado_observado_3_4_rondas"], "NO_DEMOSTRADO")


if __name__ == "__main__":
    unittest.main()
