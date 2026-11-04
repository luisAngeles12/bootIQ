"""Pruebas aisladas de corte temporal y trazabilidad sin broker."""
import unittest

from validacion_choch_soporte_congelada import CORTE_UTC, evaluar
from auditoria_candidatas_sombra_practice import _id as calcular_id_sombra

ALIAS = {}


def fila(id_, ts, patron="CHOCH bajista", direccion="put",
         accion="PUT_SOPORTE_CERCA_SIN_RUPTURA", resultado="LOSS"):
    candidato_id = calcular_id_sombra("ACTIVO_" + id_, patron, direccion, ts)
    ALIAS[id_] = candidato_id
    return {
        "id": candidato_id, "activo": "ACTIVO_" + id_, "patron": patron,
        "direccion": direccion, "vela_senal_from": str(ts),
        "decision": "NO_OPERAR", "calidad_mercado": "NORMAL",
        "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
        "resultado_hipotetico": resultado, "estado_tendencia": "BAJISTA_NORMAL",
        "accion_precio": accion,
    }


def ledger(**estados):
    return {"ids_por_estado": {ALIAS.get(k, k): v for k, v in estados.items()}}


class TestHipotesisCongelada(unittest.TestCase):
    def test_excluye_desarrollo_y_rondas_descartadas(self):
        filas = [
            fila("antigua", CORTE_UTC - 60, resultado="WIN"),
            fila("descartada", CORTE_UTC, resultado="WIN"),
            fila("nueva", CORTE_UTC + 60, resultado="LOSS"),
        ]
        r = evaluar(filas, ledger(antigua="ANALISIS_VALIDADO",
                                 descartada="DESCARTADA",
                                 nueva="ANALISIS_VALIDADO"))
        self.assertEqual(r["registros_post_corte_con_ronda_validada"], 1)
        self.assertEqual(r["objetivo_choch_bajista"]["losses"], 1)
        self.assertEqual(r["exclusiones"]["RONDA_NO_VALIDADA"], 1)
        self.assertEqual(r["exclusiones"]["DESARROLLO_ANTES_DEL_CORTE"], 1)

    def test_separa_objetivo_de_comparador(self):
        filas = [
            fila("choch", CORTE_UTC, resultado="LOSS"),
            fila("pullback", CORTE_UTC + 60, patron="pullback bajista a EMA",
                 resultado="WIN"),
            fila("otraaccion", CORTE_UTC + 120,
                 accion="ABSORCION_COMPRADORA", resultado="WIN"),
        ]
        r = evaluar(filas, ledger(**{f["id"]: "ANALISIS_VALIDADO" for f in filas}))
        self.assertEqual(r["objetivo_choch_bajista"]["oportunidades"], 1)
        self.assertEqual(r["comparador_otros_patrones"]["wins"], 1)
        self.assertFalse(r["operaciones_autorizadas"])

    def test_conflictos_y_id_duplicado_no_entran(self):
        a = fila("mismo", CORTE_UTC)
        b = fila("mismo", CORTE_UTC)
        c = fila("x", CORTE_UTC + 60, resultado="WIN")
        d = fila("y", CORTE_UTC + 60, resultado="LOSS")
        d["activo"] = c["activo"]
        d["patron"] = "pullback bajista a EMA"
        d["id"] = calcular_id_sombra(
            d["activo"], d["patron"], d["direccion"], int(d["vela_senal_from"])
        )
        ALIAS["y"] = d["id"]
        r = evaluar([a, b, c, d], ledger(mismo="ANALISIS_VALIDADO",
                                         x="ANALISIS_VALIDADO", y="ANALISIS_VALIDADO"))
        self.assertEqual(r["exclusiones"]["ID_FALTANTE_O_DUPLICADO"], 2)
        self.assertEqual(r["objetivo_choch_bajista"]["oportunidades"], 0)
        self.assertEqual(r["descartes_depuracion"]["CONFLICTO_ACTIVO_MINUTO"], 1)

    def test_identidad_alterada_no_entra_a_muestra(self):
        original = fila("integridad", CORTE_UTC, resultado="WIN")
        catalogo = ledger(integridad="ANALISIS_VALIDADO")
        original["patron"] = "pullback bajista a EMA"
        r = evaluar([original], catalogo)
        self.assertEqual(r["exclusiones"]["IDENTIDAD_CANDIDATA_INVALIDA"], 1)
        self.assertEqual(r["registros_post_corte_con_ronda_validada"], 0)

    def test_sin_datos_no_inventa_porcentaje(self):
        r = evaluar([], ledger())
        self.assertIsNone(r["objetivo_choch_bajista"]["winrate_proxy_pct"])
        self.assertEqual(r["evidencia_para_conclusion"], "PENDIENTE_VALIDACION_INDEPENDIENTE")
        self.assertFalse(r["winrate_60_validado"])


if __name__ == "__main__":
    unittest.main()
