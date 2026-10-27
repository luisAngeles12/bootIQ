import unittest
from unittest.mock import patch

import evaluar_breakout_retest_sombra as evaluador


def velas_call(cierre_futuro=None):
    filas = []
    total = 183 if cierre_futuro is not None else 182
    for idx in range(total):
        ruptura = idx == 180
        retest = idx == 181
        futuro = idx == 182
        cierre = (
            100.8 if ruptura else 100.6 if retest
            else cierre_futuro if futuro else 99.5
        )
        apertura = 99.7 if ruptura else 100.5 if retest else 99.5
        maximo = 101.0 if ruptura else 100.9 if retest else max(100.0, cierre)
        minimo = 99.6 if ruptura else 100.02 if retest else min(99.0, cierre)
        filas.append({
            "activo": "PRUEBA", "tipo": "turbo",
            "from": str(100000 + idx * 60),
            "open": str(apertura), "close": str(cierre),
            "max": str(maximo), "min": str(minimo),
        })
    return filas


class EvaluacionBreakoutRetestSombraTests(unittest.TestCase):
    def test_call_win_con_una_vela_futura(self):
        eventos = evaluador.evaluar_filas(velas_call(101.0))
        caso = [e for e in eventos if e["idx_senal"] == 181]
        self.assertEqual(len(caso), 1)
        self.assertEqual(caso[0]["direccion_sombra"], "call")
        self.assertEqual(caso[0]["resultado_hipotetico_sombra"], "WIN")

    def test_ultima_vela_no_usa_futuro_inexistente(self):
        eventos = evaluador.evaluar_filas(velas_call())
        caso = [e for e in eventos if e["idx_senal"] == 181]
        self.assertEqual(len(caso), 1)
        self.assertEqual(caso[0]["resultado_hipotetico_sombra"], "SIN_FUTURO")

    def test_empate_no_cuenta_como_win(self):
        eventos = evaluador.evaluar_filas(velas_call(100.6))
        caso = [e for e in eventos if e["idx_senal"] == 181]
        self.assertEqual(caso[0]["resultado_hipotetico_sombra"], "EMPATE")

    def test_direccion_ambigua_se_excluye_del_winrate(self):
        fila = {
            "idx_senal": 181, "activo": "PRUEBA",
            "br_call_sombra": 1, "br_put_sombra": -1,
        }
        with patch.object(evaluador, "auditar_filas", return_value=[fila]):
            casos = evaluador.evaluar_filas(velas_call(101.0))
        self.assertEqual(casos[0]["direccion_sombra"], "AMBAS")
        self.assertEqual(casos[0]["resultado_hipotetico_sombra"], "AMBIGUA")


if __name__ == "__main__":
    unittest.main()
