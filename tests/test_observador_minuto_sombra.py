"""Pruebas del observador minuto a minuto sin broker."""
import unittest

from observador_minuto_sombra import ObservadorMinutoSombra
from paridad_sombra_practice import evaluar_flujo, reproducir_cierres


def muestra(cantidad=26 * 60):
    return {
        t: {"from": t, "open": 100 + t * .001,
            "close": 100 + t * .001, "min": 99.9 + t * .001,
            "max": 100.1 + t * .001}
        for t in range(cantidad)
    }


class ObservadorSombraTests(unittest.TestCase):
    def test_decisiones_identicas_a_replay_y_sin_ordenes(self):
        velas = muestra()
        observador = ObservadorMinutoSombra()
        salidas = []
        for t, vela in velas.items():
            salidas.extend(observador.registrar(vela, t + 1))
        self.assertEqual(salidas, reproducir_cierres(velas))
        self.assertTrue(all(not d["arbitraje"]["operable"] for _, d in salidas))

    def test_lote_mismo_segundo_no_cierra_antes_de_ultima_vela(self):
        datos = muestra(120)
        observador = ObservadorMinutoSombra()
        salidas = []
        for t in range(58):
            salidas.extend(observador.registrar_lote([datos[t]], t + 1))
        # Ambos cierres se conocen en el segundo 60; antes, registrar()
        # cerraba el minuto al insertar 58 y rechazaba 59.
        salidas.extend(observador.registrar_lote([datos[58], datos[59]], 60))
        self.assertEqual([fin for fin, _ in salidas], [60])
        self.assertEqual(salidas, reproducir_cierres({t: datos[t] for t in range(60)}))

    def test_lote_no_admite_vela_que_llego_despues_del_cierre(self):
        datos = muestra(120)
        observador = ObservadorMinutoSombra()
        salidas = []
        for t in range(58):
            salidas.extend(observador.registrar_lote([datos[t]], t + 1))
        salidas.extend(observador.registrar_lote([datos[58]], 59))
        salidas.extend(observador.registrar_lote([datos[59]], 61))
        for t in range(60, 120):
            salidas.extend(observador.registrar_lote([datos[t]], t + 1))
        self.assertEqual([fin for fin, _ in salidas], [120])

    def test_captura_tardia_no_rehace_cierre(self):
        datos = muestra(120)
        observador = ObservadorMinutoSombra()
        salidas = []
        for t, vela in datos.items():
            if t != 59:
                salidas.extend(observador.registrar(vela, t + 1))
        salidas.extend(observador.registrar(datos[59], 122))
        self.assertEqual([t for t, _ in salidas], [120])
        llegadas = [(t + 1, v) for t, v in datos.items() if t != 59]
        llegadas.append((122, datos[59]))
        self.assertEqual(salidas, evaluar_flujo(llegadas))

    def test_hueco_bloquea_el_minuto(self):
        observador = ObservadorMinutoSombra()
        salidas = []
        for t, vela in muestra(120).items():
            if t != 20:
                salidas.extend(observador.registrar(vela, t + 1))
        self.assertEqual([t for t, _ in salidas], [120])

    def test_reloj_retrocedido_se_rechaza(self):
        observador = ObservadorMinutoSombra()
        observador.avanzar(10)
        with self.assertRaisesRegex(ValueError, "RELOJ_RETROCEDIO"):
            observador.avanzar(9)

    def test_vela_abierta_se_rechaza(self):
        observador = ObservadorMinutoSombra()
        with self.assertRaisesRegex(ValueError, "VELA_AUN_ABIERTA"):
            observador.registrar(muestra(1)[0], 0)


if __name__ == "__main__":
    unittest.main()
