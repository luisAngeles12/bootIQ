"""Regresiones de ranking y arbitraje V3: pruebas aisladas sin broker."""
import unittest
from copy import deepcopy

from motor_candidatos import ordenar_candidatas_v3, seleccionar_mejor_candidata_v3


def candidata(nombre, direccion, decision, probabilidad, muestra, puntaje):
    return {
        "nombre_prueba": nombre,
        "activo": "EURUSD",
        "direccion": direccion,
        "cerebro_unico_decision": decision,
        "probabilidad_v3": probabilidad,
        "muestra_probabilidad": muestra,
        "puntaje": puntaje,
    }


class RankingArbitrajeV3Tests(unittest.TestCase):
    def _comprobar_ganadora(self, senales, esperada):
        antes = deepcopy(senales)
        ordenadas = ordenar_candidatas_v3(senales)
        mejor = seleccionar_mejor_candidata_v3(senales)
        self.assertIsNotNone(mejor)
        self.assertEqual(mejor["nombre_prueba"], esperada)
        self.assertEqual(ordenadas[0]["nombre_prueba"], esperada)
        self.assertEqual(senales, antes, "El ranking no debe modificar sus entradas.")

    def test_autorizacion_prevalece_sobre_puntaje_y_probabilidad(self):
        self._comprobar_ganadora([
            candidata("RECHAZADA", "CALL", "NO_OPERAR", 95, 100, 100),
            candidata("AUTORIZADA", "PUT", "OPERAR", 51, 0, 5),
        ], "AUTORIZADA")

    def test_probabilidad_prevalece_entre_autorizadas(self):
        self._comprobar_ganadora([
            candidata("MENOR_PROB", "CALL", "OPERAR", 55, 100, 90),
            candidata("MAYOR_PROB", "PUT", "OPERAR", 65, 20, 10),
        ], "MAYOR_PROB")

    def test_muestra_desempata_probabilidad(self):
        self._comprobar_ganadora([
            candidata("MENOR_MUESTRA", "CALL", "OPERAR", 60, 10, 100),
            candidata("MAYOR_MUESTRA", "PUT", "OPERAR", 60, 50, 5),
        ], "MAYOR_MUESTRA")

    def test_mayoria_de_rechazadas_no_supera_autorizacion(self):
        self._comprobar_ganadora([
            candidata("CALL_1", "CALL", "NO_OPERAR", 70, 50, 90),
            candidata("CALL_2", "CALL", "NO_OPERAR", 70, 50, 90),
            candidata("PUT_AUTORIZADA", "PUT", "OPERAR", 49, 0, 5),
        ], "PUT_AUTORIZADA")

    def test_diagnostico_competencia_no_cambia_ranking(self):
        base = [
            candidata("CALL_AUTORIZADA", "CALL", "OPERAR", 55, 30, 15),
            candidata("PUT_AUTORIZADA", "PUT", "OPERAR", 60, 30, 15),
        ]
        escenarios = (
            ("SIN_CONFLICTO", False, False, "SIN_CONFLICTO"),
            ("MAYORIA_CALL", True, True, "CALL"),
            ("MAYORIA_PUT", True, True, "PUT"),
            ("EMPATE", True, False, "EMPATE"),
        )
        for nombre, conflicto, mayoria, direccion_mayoria in escenarios:
            with self.subTest(escenario=nombre):
                senales = deepcopy(base)
                for senal in senales:
                    senal["competencia_conflicto"] = conflicto
                    senal["competencia_conflicto_con_mayoria"] = mayoria
                    senal["competencia_direccion_mayoria"] = direccion_mayoria
                self._comprobar_ganadora(senales, "PUT_AUTORIZADA")


if __name__ == "__main__":
    unittest.main()
