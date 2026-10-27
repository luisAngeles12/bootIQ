import unittest

from auditoria_intervalo_cerebro_fase3 import contrastar_intervalo_cerebro


def senal(numero, decision="OPERAR_SOMBRA", probabilidad="60",
          inferior="56", resultado="WIN"):
    return {
        "fecha_senal": str(1793059200 + 60*numero),
        "activo": "EURUSD-OTC", "patron": "PATRON", "direccion": "call",
        "decision_estadistica_sombra": decision,
        "probabilidad_estimada": probabilidad,
        "intervalo_probabilidad_inferior": inferior,
        "muestra_probabilidad": "25",
        "resultado_hipotetico": resultado, "estado_operacion": "CANCELADA_CEREBRO",
    }


class IntervalosCerebroFase3Tests(unittest.TestCase):
    def test_compara_punto_con_intervalo_sin_operar(self):
        filas = [senal(0), senal(1, inferior="49", resultado="LOSS"),
                 senal(2, decision="OPERAR_CON_PROTOCOLO_SOMBRA",
                       probabilidad="53", inferior="51")]
        r = contrastar_intervalo_cerebro(filas)
        self.assertEqual(r["cohortes"]["OPERAR_SOMBRA|INTERVALO_SOSTIENE_UMBRAL"]["wins_hipoteticos"], 1)
        self.assertEqual(r["cohortes"]["OPERAR_SOMBRA|SOLO_ESTIMACION_PUNTUAL"]["losses_hipoteticas"], 1)
        self.assertEqual(r["cohortes"]["OPERAR_CON_PROTOCOLO_SOMBRA|INTERVALO_SOSTIENE_UMBRAL"]["n"], 1)
        self.assertFalse(r["autoriza_operaciones"])
        self.assertTrue(all(not x["autoriza_cambio"] for x in r["cohortes"].values()))

    def test_no_cuenta_resultados_sin_intervalos_validos(self):
        filas = [
            senal(0, inferior=""),
            senal(1, inferior="65"),
            senal(2, probabilidad="nan"),
            senal(3, resultado="EMPATE"),
            senal(4, probabilidad="49", inferior="40"),
            senal(5, decision="NO_OPERAR_SOMBRA"),
        ]
        r = contrastar_intervalo_cerebro(filas)
        self.assertEqual(r["cohortes"], {})
        self.assertEqual(r["descartes"]["INTERVALO_O_MUESTRA_INVALIDA"], 3)
        self.assertEqual(r["descartes"]["SIN_RESULTADO_HIPOTETICO"], 1)
        self.assertEqual(r["descartes"]["DECISION_INCOHERENTE_CON_UMBRAL"], 1)
        self.assertEqual(r["descartes"]["NO_AUTORIZADA_ESTADISTICAMENTE"], 1)

    def test_intervalo_de_principal_no_se_confunde_con_probabilidad_combinada(self):
        fila = senal(0, probabilidad="60", inferior="40")
        fila["intervalo_probabilidad_superior"] = "55"
        r = contrastar_intervalo_cerebro([fila])
        self.assertEqual(r["estimaciones_fuera_intervalo_fuente_principal"], 1)
        self.assertEqual(r["intervalos_superiores_no_validos"], 0)
        self.assertEqual(r["cohortes"]["OPERAR_SOMBRA|SOLO_ESTIMACION_PUNTUAL"]["n"], 1)
        self.assertEqual(r["proveniencia_intervalo"], "FUENTE_PRINCIPAL_NO_INTERVALO_DE_MEZCLA")
        self.assertFalse(r["autoriza_operaciones"])

    def test_duplicados_no_inflan_evidencia(self):
        fila = senal(0)
        with self.assertRaisesRegex(ValueError, "repetida"):
            contrastar_intervalo_cerebro([fila, dict(fila)])

    def test_no_exige_mismo_activo_para_mismo_instante(self):
        fila = senal(0)
        otro = dict(fila, activo="USDJPY-OTC")
        r = contrastar_intervalo_cerebro([fila, otro])
        self.assertEqual(r["cohortes"]["OPERAR_SOMBRA|INTERVALO_SOSTIENE_UMBRAL"]["n"], 2)


if __name__ == "__main__":
    unittest.main()
