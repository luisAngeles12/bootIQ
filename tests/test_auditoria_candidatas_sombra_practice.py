"""Pruebas de observacion prospectiva sin broker ni datos inventados."""
import csv
import tempfile
import unittest
from pathlib import Path

from auditoria_candidatas_sombra_practice import (
    registrar_candidata, resolver_candidatas,
)


def senal(direccion="call"):
    return {
        "activo": "USDINR-OTC",
        "patron": "PULLBACK",
        "direccion": direccion,
        "vela_senal_from": 600,
        "decision_unificada_accion": "NO_OPERAR",
        "accion_precio": "RECHAZO_COMPRADOR_SOPORTE",
    }


def ctx(froms=None, opens=None, closes=None):
    return {
        "activo": "USDINR-OTC",
        "vela_senal_from": (froms or [600])[-1],
        "froms": froms or [600],
        "opens": opens or [100],
        "closes": closes or [100],
        "tipo_mercado": "TENDENCIA_ALCISTA",
        "calidad_mercado": "NORMAL",
        "estado_tendencia": "ALCISTA_NORMAL",
    }


class AuditoriaCandidatasSombra(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.p = Path(self.t.name) / "sombra.csv"

    def leer(self):
        with self.p.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_rechazada_persiste_sin_autorizar_orden(self):
        s = senal()
        self.assertTrue(registrar_candidata(s, ctx(), self.p))
        self.assertEqual(s["decision_unificada_accion"], "NO_OPERAR")
        self.assertFalse(registrar_candidata(s, ctx(), self.p))
        filas = self.leer()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["resultado_hipotetico"], "")

    def test_motivo_largo_conserva_causa_final(self):
        s = senal()
        motivo = "DIAGNOSTICO: " + ("x" * 600) + " | CAUSA_FINAL: SIN_DATOS_ESTADISTICOS"
        s["motivo_decision_unificada"] = motivo
        s["razon"] = "FALLBACK_NO_DEBE_USARSE"
        self.assertTrue(registrar_candidata(s, ctx(), self.p))
        fila = self.leer()[0]
        self.assertEqual(fila["motivo"], motivo)
        self.assertTrue(fila["motivo"].endswith("CAUSA_FINAL: SIN_DATOS_ESTADISTICOS"))
        self.assertEqual(fila["decision"], "NO_OPERAR")

    def test_motivo_oficial_tiene_prioridad_sobre_razon_preliminar(self):
        s = senal()
        s["motivo_decision_unificada"] = "DECISION OFICIAL: SIN FUENTE HISTORICA"
        s["razon"] = "ESTRATEGIA: motivo preliminar"
        self.assertTrue(registrar_candidata(s, ctx(), self.p))
        fila = self.leer()[0]
        self.assertEqual(fila["motivo"], s["motivo_decision_unificada"])
        self.assertEqual(fila["decision"], "NO_OPERAR")

    def test_sin_vela_futura_no_inventa_resultado(self):
        registrar_candidata(senal(), ctx(), self.p)
        self.assertEqual(resolver_candidatas("USDINR-OTC", ctx(), self.p), 0)
        self.assertEqual(self.leer()[0]["resultado_hipotetico"], "")

    def test_resultado_de_vela_posterior_y_solo_hipotetico(self):
        registrar_candidata(senal(), ctx(), self.p)
        datos = ctx([600, 660], [100, 100], [101, 102])
        self.assertEqual(resolver_candidatas("USDINR-OTC", datos, self.p), 1)
        fila = self.leer()[0]
        self.assertEqual(fila["resultado_hipotetico"], "WIN")
        self.assertEqual(fila["precio_entrada_hipotetico"], "100.0")
        self.assertEqual(fila["calidad_tiempo"], "HIPOTETICO_VELA_COMPLETA_SIN_FILL")
        self.assertEqual(resolver_candidatas("USDINR-OTC", datos, self.p), 0)

    def test_put_perdedor(self):
        registrar_candidata(senal("put"), ctx(), self.p)
        self.assertEqual(
            resolver_candidatas("USDINR-OTC", ctx([600, 660], [100, 100], [100, 101]), self.p), 1
        )
        self.assertEqual(self.leer()[0]["resultado_hipotetico"], "LOSS")

    def test_empate_no_se_cuenta_como_win(self):
        registrar_candidata(senal(), ctx(), self.p)
        resolver_candidatas("USDINR-OTC", ctx([600, 660], [100, 100], [100, 100]), self.p)
        self.assertEqual(self.leer()[0]["resultado_hipotetico"], "EMPATE")

    def test_ventana_expirada_se_reporta_sin_imputar_win_loss(self):
        registrar_candidata(senal(), ctx(), self.p)
        datos = ctx([900, 960], [100, 100], [100, 101])
        self.assertEqual(resolver_candidatas("USDINR-OTC", datos, self.p), 1)
        fila = self.leer()[0]
        self.assertEqual(fila["resultado_hipotetico"], "")
        self.assertEqual(fila["calidad_tiempo"], "SIN_VELA_POSTERIOR_EN_BUFFER")
        self.assertEqual(resolver_candidatas("USDINR-OTC", datos, self.p), 0)

    def test_contexto_discontinuo_no_cierra_ninguna_senal(self):
        registrar_candidata(senal(), ctx(), self.p)
        datos = ctx([600, 660, 780], [100, 100, 100], [101, 102, 103])
        self.assertEqual(resolver_candidatas("USDINR-OTC", datos, self.p), 0)
        self.assertEqual(self.leer()[0]["resultado_hipotetico"], "")

    def test_no_registra_senal_aprobada(self):
        s = senal()
        s["decision_unificada_accion"] = "OPERAR"
        self.assertFalse(registrar_candidata(s, ctx(), self.p))
        self.assertFalse(self.p.exists())

    def test_hueco_no_se_resuelve(self):
        registrar_candidata(senal(), ctx(), self.p)
        self.assertEqual(
            resolver_candidatas("USDINR-OTC", ctx([540, 660], [99, 100], [100, 101]), self.p), 0
        )
        self.assertEqual(self.leer()[0]["resultado_hipotetico"], "")

if __name__ == "__main__":
    unittest.main()
