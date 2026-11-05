"""Pruebas del evaluador de absorcion congelada, sin broker."""
import tempfile
import unittest
import json
from pathlib import Path
from datetime import datetime, timezone

from auditoria_candidatas_sombra_practice import _id
from validacion_choch_absorcion_congelada import evaluar, leer_registro

CORTE = 1793923200
REGISTRO = {
    "tipo": "HIPOTESIS_PROSPECTIVA_CONGELADA_SOLO_LECTURA",
    "cuenta": "PRACTICE", "autoriza_operaciones": False,
    "grupo_objetivo": "CHOCH bajista",
    "grupo_comparador": "Otros patrones PUT exclusivos",
    "direccion": "put", "accion_precio": "ABSORCION_COMPRADORA",
    "corte_utc_inclusivo": "2026-11-06T00:00:00+00:00",
    "congelada_utc": "2026-11-05T14:50:38.677216+00:00",
}


def fila(activo, ts, patron="CHOCH bajista", resultado="LOSS",
         accion="ABSORCION_COMPRADORA"):
    return {
        "id": _id(activo, patron, "put", ts),
        "activo": activo, "vela_senal_from": str(ts),
        "patron": patron, "direccion": "put", "decision": "NO_OPERAR",
        "accion_precio": accion, "calidad_mercado": "NORMAL",
        "estado_tendencia": "BAJISTA_NORMAL",
        "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
        "resultado_hipotetico": resultado,
    }


def ledger(filas, estado="ANALISIS_VALIDADO"):
    return {"ids_por_estado": {f["id"]: estado for f in filas}}


class TestAbsorcionCongelada(unittest.TestCase):
    def test_corte_y_comparador(self):
        filas = [
            fila("vieja", CORTE - 60, resultado="WIN"),
            fila("choch", CORTE, resultado="LOSS"),
            fila("otra", CORTE + 60, patron="pullback bajista a EMA", resultado="WIN"),
            fila("otraaccion", CORTE + 120, accion="PUT_SOPORTE_CERCA_SIN_RUPTURA", resultado="WIN"),
        ]
        r = evaluar(filas, ledger(filas), REGISTRO)
        self.assertEqual(r["exclusiones"]["ANTES_DEL_CORTE"], 1)
        self.assertEqual(r["objetivo_choch_bajista"]["loss"], 1)
        self.assertEqual(r["comparador_otros_put"]["win"], 1)
        self.assertEqual(r["diferencia_choch_menos_otros_pp"], -100.0)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_pendiente_contamina_evento_completo(self):
        a = fila("a", CORTE, resultado="WIN")
        b = fila("a", CORTE, patron="pullback bajista a EMA", resultado="")
        r = evaluar([a, b], ledger([a, b]), REGISTRO)
        self.assertEqual(r["exclusiones"]["EVENTO_EN_CUARENTENA"], 2)
        self.assertEqual(r["objetivo_choch_bajista"]["eventos"], 0)

    def test_ronda_descartada_cuarentena_otro_patron(self):
        a = fila("a", CORTE, resultado="WIN")
        b = fila("a", CORTE, patron="pullback bajista a EMA")
        r = evaluar([a, b], {"ids_por_estado": {
            a["id"]: "ANALISIS_VALIDADO", b["id"]: "DESCARTADA",
        }}, REGISTRO)
        self.assertEqual(r["exclusiones"]["RONDA_NO_VALIDADA"], 1)
        self.assertEqual(r["exclusiones"]["EVENTO_EN_CUARENTENA"], 1)
        self.assertEqual(r["objetivo_choch_bajista"]["eventos"], 0)

    def test_ids_duplicados_no_entran(self):
        a = fila("a", CORTE, resultado="WIN")
        r = evaluar([a, dict(a)], ledger([a]), REGISTRO)
        self.assertEqual(r["exclusiones"]["ID_FALTANTE_O_DUPLICADO"], 2)
        self.assertEqual(r["objetivo_choch_bajista"]["eventos"], 0)

    def test_contradiccion_no_elige_patron(self):
        a = fila("a", CORTE, resultado="WIN")
        b = fila("a", CORTE, patron="pullback bajista a EMA", resultado="LOSS")
        r = evaluar([a, b], ledger([a, b]), REGISTRO)
        self.assertEqual(r["descartes_depuracion"]["CONFLICTO_ACTIVO_MINUTO"], 1)
        self.assertEqual(r["objetivo_choch_bajista"]["eventos"], 0)

    def test_sin_muestra_no_inventa_tasa(self):
        r = evaluar([], ledger([]), REGISTRO)
        self.assertIsNone(r["objetivo_choch_bajista"]["winrate_proxy_pct"])
        self.assertIsNone(r["diferencia_choch_menos_otros_pp"])
        self.assertFalse(r["winrate_60_validado"])

    def test_registro_incompatible_rechazado(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "hipotesis.json"
            d = dict(REGISTRO, autoriza_operaciones=True)
            p.write_text(json.dumps(d), encoding="utf-8")
            with self.assertRaises(ValueError):
                leer_registro(p)

    def test_registro_versionado(self):
        d = leer_registro()
        self.assertEqual(d["corte_utc_inclusivo"], REGISTRO["corte_utc_inclusivo"])
        self.assertFalse(d["autoriza_operaciones"])


if __name__ == "__main__":
    unittest.main()
