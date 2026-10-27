"""Pruebas del diagnóstico breakout/retest SOMBRA, sin autoridad operativa."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

import zonas


class BreakoutZonaPreviaShadowTests(unittest.TestCase):
    @staticmethod
    def velas(lado):
        if lado == "call":
            closes = [99.0] * 8 + [101.5, 101.0]
            highs = [100.0] * 8 + [102.5, 102.0]
            lows = [95.0] * 8 + [98.5, 100.2]
        else:
            closes = [96.0] * 8 + [93.7, 94.0]
            highs = [100.0] * 8 + [96.2, 94.8]
            lows = [95.0] * 8 + [93.5, 93.8]
        return list(closes), closes, highs, lows

    def test_zona_anclada_al_precio_actual_invalida_br_en_ambos_lados(self):
        for lado in ("call", "put"):
            with self.subTest(lado=lado):
                o, c, h, l = self.velas(lado)
                so, re = zonas.soporte_resistencia_zonas(c[-1], h, l, 2.0)
                zona = re if lado == "call" else so
                tipo = "resistencia" if lado == "call" else "soporte"
                original, _ = zonas.breakout_retest(o, c, h, l, zona, tipo)
                self.assertEqual(original, 0)
                sombra = zonas.diagnosticar_breakout_retest_pre_evento(
                    o, c, h, l, 2.0)
                self.assertEqual(sombra["br_call_sombra" if lado == "call"
                                        else "br_put_sombra"],
                                 1 if lado == "call" else -1)

    def test_nivel_pre_evento_excluye_las_dos_velas_de_confirmacion(self):
        o, c, h, l = self.velas("call")
        original = zonas.soporte_resistencia_zonas
        with patch.object(zonas, "soporte_resistencia_zonas",
                          wraps=original) as selector:
            zonas.diagnosticar_breakout_retest_pre_evento(o, c, h, l, 2.0)
            self.assertEqual(selector.call_count, 1)
            args = selector.call_args.args
            self.assertEqual(args[0], c[-3])
            self.assertEqual(args[1], h[:-2])
            self.assertEqual(args[2], l[:-2])

    def test_falla_cerrado_si_faltan_velas(self):
        v = zonas.diagnosticar_breakout_retest_pre_evento(
            [1.0]*4, [1.0]*4, [1.0]*4, [1.0]*4, 0.2)
        self.assertEqual(v["br_call_sombra"], 0)
        self.assertEqual(v["br_put_sombra"], 0)

    def test_lector_no_sustituye_activadores_productivos(self):
        text = Path(__file__).resolve().parents[1].joinpath(
            "lector_contexto.py").read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn('br_call, nombre_br_call = breakout_retest(', text)
        self.assertIn('br_put, nombre_br_put = breakout_retest(', text)
        self.assertIn('br_pre_evento_sombra = diagnosticar_breakout_retest_pre_evento(', text)
        self.assertIn('**br_pre_evento_sombra,', text)


if __name__ == "__main__":
    unittest.main()
