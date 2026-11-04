"""Pruebas aisladas de corte temporal y trazabilidad sin broker."""
import tempfile
import unittest
from pathlib import Path

from validacion_choch_soporte_congelada import CORTE_UTC, evaluar, cargar_filas_opcionales
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

    def test_fecha_invalida_se_clasifica_sin_crash(self):
        registro = fila("fecha", CORTE_UTC)
        registro["vela_senal_from"] = "fecha-no-numerica"
        r = evaluar([registro], ledger(fecha="ANALISIS_VALIDADO"))
        self.assertEqual(r["exclusiones"]["FECHA_INVALIDA"], 1)
        self.assertEqual(r["registros_post_corte_con_ronda_validada"], 0)

    def test_csv_aun_no_creado_implica_muestra_vacia(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "no-existe.csv"
            filas = cargar_filas_opcionales(ruta)
        self.assertEqual(filas, [])
        r = evaluar(filas, ledger())
        self.assertIsNone(r["objetivo_choch_bajista"]["winrate_proxy_pct"])
        self.assertFalse(r["operaciones_autorizadas"])

    def test_sin_datos_no_inventa_porcentaje(self):
        r = evaluar([], ledger())
        self.assertIsNone(r["objetivo_choch_bajista"]["winrate_proxy_pct"])
        self.assertEqual(r["evidencia_para_conclusion"], "PENDIENTE_VALIDACION_INDEPENDIENTE")
        self.assertFalse(r["winrate_60_validado"])


    def test_candidato_descartado_no_convierte_evento_en_patron_exclusivo(self):
        objetivo = fila("principal", CORTE_UTC, resultado="WIN")
        descartada = fila("otra", CORTE_UTC, patron="pullback bajista a EMA",
                          resultado="LOSS")
        descartada["activo"] = objetivo["activo"]
        descartada["id"] = calcular_id_sombra(
            descartada["activo"], descartada["patron"],
            descartada["direccion"], CORTE_UTC,
        )
        r = evaluar([objetivo, descartada], {
            "ids_por_estado": {
                objetivo["id"]: "ANALISIS_VALIDADO",
                descartada["id"]: "DESCARTADA",
            },
        })
        self.assertEqual(r["objetivo_choch_bajista"]["oportunidades"], 0)
        self.assertEqual(r["exclusiones"]["RONDA_NO_VALIDADA"], 1)
        self.assertEqual(
            r["exclusiones"]["EVENTO_CONTAMINADO_POR_CANDIDATA_EXCLUIDA"], 1
        )

    def test_pendiente_no_permite_reconstruir_evento_exclusivo(self):
        objetivo = fila("principal_pendiente", CORTE_UTC, resultado="WIN")
        pendiente = fila("otro_pendiente", CORTE_UTC,
                         patron="pullback bajista a EMA", resultado="")
        pendiente["activo"] = objetivo["activo"]
        pendiente["id"] = calcular_id_sombra(
            pendiente["activo"], pendiente["patron"],
            pendiente["direccion"], CORTE_UTC,
        )
        ids = {f["id"]: "ANALISIS_VALIDADO" for f in (objetivo, pendiente)}
        r = evaluar([objetivo, pendiente], {"ids_por_estado": ids})
        self.assertEqual(r["objetivo_choch_bajista"]["oportunidades"], 0)
        self.assertEqual(
            r["exclusiones"]["EVENTO_CONTAMINADO_POR_CANDIDATA_EXCLUIDA"], 2
        )

    def test_candidato_historico_no_cuarentena_evento_futuro(self):
        pasado = fila("hist", CORTE_UTC - 60, resultado="LOSS")
        futuro = fila("fut", CORTE_UTC, resultado="WIN")
        futuro["activo"] = pasado["activo"]
        futuro["id"] = calcular_id_sombra(
            futuro["activo"], futuro["patron"],
            futuro["direccion"], CORTE_UTC,
        )
        r = evaluar([pasado, futuro], {"ids_por_estado": {
            pasado["id"]: "DESCARTADA",
            futuro["id"]: "ANALISIS_VALIDADO",
        }})
        self.assertEqual(r["objetivo_choch_bajista"]["wins"], 1)


if __name__ == "__main__":
    unittest.main()
