"""Regresiones sin IQ Option, sin operaciones y sin cambios de decisiones."""
import tempfile
import unittest
from pathlib import Path

from trazabilidad_rondas_sombra import registrar_evento, auditar_intentos
from auditar_trazabilidad_sombra import auditar


def f(id_):
    return {"id": id_}


class TestTrazabilidadRondasSombra(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.p = Path(tmp.name) / "rondas.jsonl"

    def ev(self, evento, run="run1", intento=1, vela=100, candidato_id=""):
        return registrar_evento(evento, run, intento, vela, candidato_id=candidato_id, ruta=self.p)

    def test_validada_unico_intento(self):
        self.ev("INICIO")
        self.ev("CANDIDATA", candidato_id="a")
        self.ev("ANALISIS_VALIDADO")
        r = auditar([f("a"), f("sin-ledger")], auditar_intentos(self.p))
        self.assertEqual(r["filas_por_estado"]["ANALISIS_VALIDADO"], 1)
        self.assertEqual(r["filas_por_estado"]["SIN_TRAZABILIDAD"], 1)
        self.assertEqual(r["filas_con_intento_validado_unico"], 1)
        self.assertFalse(r["ordenes_autorizadas"])

    def test_descartada_no_entra(self):
        self.ev("INICIO")
        self.ev("CANDIDATA", candidato_id="a")
        self.ev("DESCARTADA")
        r = auditar([f("a")], auditar_intentos(self.p))
        self.assertEqual(r["filas_por_estado"]["DESCARTADA"], 1)
        self.assertEqual(r["filas_con_intento_validado_unico"], 0)

    def test_reintento_misma_vela_ambiguo_incluso_si_validado(self):
        self.ev("INICIO", intento=1)
        self.ev("CANDIDATA", intento=1, candidato_id="a")
        self.ev("DESCARTADA", intento=1)
        self.ev("INICIO", intento=2)
        self.ev("CANDIDATA", intento=2, candidato_id="a")
        self.ev("ANALISIS_VALIDADO", intento=2)
        r = auditar([f("a")], auditar_intentos(self.p))
        self.assertEqual(r["filas_por_estado"]["AMBIGUO_MULTIPLES_INTENTOS"], 1)

    def test_segunda_ejecucion_tiene_run_id_diferente(self):
        self.ev("INICIO", run="run1")
        self.ev("CANDIDATA", run="run1", candidato_id="a")
        self.ev("ANALISIS_VALIDADO", run="run1")
        self.ev("INICIO", run="run2")
        self.ev("CANDIDATA", run="run2", candidato_id="b")
        self.ev("DESCARTADA", run="run2")
        r = auditar([f("a"), f("b")], auditar_intentos(self.p))
        self.assertEqual(r["filas_con_intento_validado_unico"], 1)
        self.assertEqual(r["filas_por_estado"]["DESCARTADA"], 1)

    def test_incompleta_sin_cierre_no_se_aprueba(self):
        self.ev("INICIO")
        self.ev("CANDIDATA", candidato_id="a")
        r = auditar([f("a")], auditar_intentos(self.p))
        self.assertEqual(r["filas_por_estado"]["INCOMPLETO_O_AMBIGUO"], 1)

    def test_cierre_duplicado_no_se_aprueba(self):
        self.ev("INICIO")
        self.ev("CANDIDATA", candidato_id="a")
        self.ev("ANALISIS_VALIDADO")
        self.ev("DESCARTADA")
        r = auditar([f("a")], auditar_intentos(self.p))
        self.assertEqual(r["filas_con_intento_validado_unico"], 0)

    def test_evento_invalido_o_candidata_sin_id(self):
        with self.assertRaises(ValueError):
            self.ev("OPERAR")
        self.assertFalse(self.ev("CANDIDATA"))
        self.assertFalse(self.p.exists())

    def test_csv_id_duplicado_no_entra(self):
        self.ev("INICIO")
        self.ev("CANDIDATA", candidato_id="a")
        self.ev("ANALISIS_VALIDADO")
        r = auditar([f("a"), f("a")], auditar_intentos(self.p))
        self.assertEqual(r["filas_por_estado"]["ID_DUPLICADO_CSV"], 2)
        self.assertEqual(r["filas_con_intento_validado_unico"], 0)


if __name__ == "__main__":
    unittest.main()
