"""R9-15: comparador IQ offline; sin login, órdenes ni memoria."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.conciliar_exportacion_iq_fase9 import conciliar_exportacion


def _crear(carpeta, nombre, campos, filas):
    ruta = Path(carpeta) / nombre
    with ruta.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)
    return ruta


BOT = [
    "order_id", "modo_cuenta_configurado", "estado", "resultado",
    "fecha_conciliacion_local_utc", "fecha_apertura_registro_local_utc",
]
IQ = ["order_id", "modo_cuenta", "estado", "pnl", "fecha_cierre_utc"]


def _bot(oid, pnl="20.75", mode="PRACTICE", state="CERRADA",
         timestamp="2026-11-19T18:05:00+00:00", apertura=""):
    return {"order_id": oid, "modo_cuenta_configurado": mode,
            "estado": state, "resultado": pnl,
            "fecha_conciliacion_local_utc": timestamp,
            "fecha_apertura_registro_local_utc": apertura}


def _iq(oid, pnl="20.75", mode="PRACTICE", state="CERRADA",
        timestamp="2026-11-19T18:04:00+00:00"):
    return {"order_id": oid, "modo_cuenta": mode, "estado": state,
            "pnl": pnl, "fecha_cierre_utc": timestamp}


class ConciliacionOfflineIQFase9Tests(unittest.TestCase):
    def analizar(self, tmp, bot, iq):
        ruta_bot = _crear(tmp, "bot.csv", BOT, bot)
        ruta_iq = _crear(tmp, "iq.csv", IQ, iq)
        previo = (ruta_bot.read_bytes(), ruta_iq.read_bytes())
        resultado = conciliar_exportacion(ruta_bot, ruta_iq)
        self.assertEqual((ruta_bot.read_bytes(), ruta_iq.read_bytes()), previo)
        self.assertFalse(resultado["habilita_trading"])
        self.assertFalse(resultado["memoria_generada"])
        self.assertFalse(resultado["broker_verificado_en_linea"])
        return resultado

    def test_match_exactamente_por_order_id_y_pnl(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("001", "20.75"),
                                    _bot("002", "-25")],
                             [_iq("002", "-25.00"), _iq("001", "20.750")])
            self.assertEqual(r["conciliadas_preliminares"], 2)
            self.assertEqual(r["pnl_conciliado_preliminar"], "-4.25")
            self.assertEqual(r["estado"], "COINCIDENCIAS_OFFLINE_NO_CERTIFICADAS")
            self.assertFalse(r["origen_exportacion_verificado"])

    def test_rechaza_diferencia_pnl_y_modo_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("1"), _bot("2")],
                             [_iq("1", "21.00"), _iq("2", mode="REAL")])
            self.assertEqual(r["conciliadas_preliminares"], 0)
            self.assertEqual(r["exclusiones"]["PNL_DIFIERE"], 1)
            self.assertEqual(r["exclusiones"]["BROKER_MODO_NO_PRACTICE"], 1)

    def test_no_promueve_orden_duplicada_y_preserva_ceros(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("001"), _bot("001"), _bot("1")],
                             [_iq("001"), _iq("1")])
            self.assertEqual(r["ids_bot_duplicados"], 1)
            self.assertEqual(r["conciliadas_preliminares"], 1)
            self.assertEqual(r["exclusiones"], {})

    def test_rechaza_cierre_iq_posterior_al_registro_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("1")], [_iq(
                "1", timestamp="2026-11-19T18:06:00Z"
            )])
            self.assertEqual(r["exclusiones"][
                "CIERRE_BROKER_POSTERIOR_CONCILIACION_BOT"], 1)

    def test_faltan_fechas_y_cierre_no_es_certificable(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("1", timestamp="")], [_iq("1")])
            self.assertEqual(r["exclusiones"]["BOT_CONCILIACION_UTC_AUSENTE"], 1)

    def test_broker_duplicado_no_se_puede_resolver_por_ultima_fila(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("1")], [_iq("1"), _iq("1")])
            self.assertEqual(r["ids_broker_duplicados"], 1)
            self.assertEqual(r["conciliadas_preliminares"], 0)
            self.assertEqual(r["exclusiones"]["SIN_ID_UNICO_BROKER"], 1)

    def test_ignora_filas_broker_extra_y_no_imputa_ausencias(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("1")], [_iq("2")])
            self.assertEqual(r["ids_sin_broker"], 1)
            self.assertEqual(r["ids_solo_broker"], 1)
            self.assertEqual(r["conciliadas_preliminares"], 0)

    def test_rechaza_cierre_broker_antes_de_apertura_utc_del_bot(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(
                tmp, [_bot("001", apertura="2026-11-19T18:03:00Z")],
                [_iq("001", timestamp="2026-11-19T18:02:00Z")],
            )
            self.assertEqual(r["conciliadas_preliminares"], 0)
            self.assertEqual(r["exclusiones"][
                "CIERRE_BROKER_ANTERIOR_APERTURA_BOT"], 1)

    def test_acepta_cronologia_utc_con_zonas_distintas(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(
                tmp, [_bot("001", apertura="2026-11-19T14:02:00-04:00")],
                [_iq("001", timestamp="2026-11-19T18:04:00Z")],
            )
            self.assertEqual(r["conciliadas_preliminares"], 1)
            self.assertFalse(r["origen_exportacion_verificado"])

    def test_bloquea_apertura_explicita_sin_zona(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(
                tmp, [_bot("001", apertura="2026-11-19T18:01:00")],
                [_iq("001")],
            )
            self.assertEqual(r["conciliadas_preliminares"], 0)
            self.assertEqual(r["exclusiones"]["BOT_APERTURA_UTC_INVALIDA"], 1)

    def test_rechaza_conciliacion_local_anterior_a_apertura(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(
                tmp, [_bot("001", timestamp="2026-11-19T18:01:00Z",
                           apertura="2026-11-19T18:02:00Z")],
                [_iq("001", timestamp="2026-11-19T18:00:00Z")],
            )
            self.assertEqual(r["conciliadas_preliminares"], 0)
            self.assertEqual(r["exclusiones"][
                "CIERRE_BROKER_ANTERIOR_APERTURA_BOT"], 1)

    def test_legacy_sin_apertura_utc_no_inventa_fecha(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("001", apertura="")], [_iq("001")])
            self.assertEqual(r["conciliadas_preliminares"], 1)
            self.assertFalse(r["origen_exportacion_verificado"])

    def test_mismo_archivo_no_equivale_a_broker_independiente(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = _crear(tmp, "bot.csv", BOT, [_bot("1")])
            r = conciliar_exportacion(ruta, ruta)
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "MISMO_ARCHIVO")

    def test_pnl_con_fracciones_de_centavo_no_se_redondea(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("1", "20.755")], [_iq("1", "20.76")])
            self.assertEqual(r["conciliadas_preliminares"], 0)
            self.assertEqual(r["exclusiones"]["BOT_PNL_INVALIDO"], 1)

    def test_pnl_infinito_o_nan_nunca_se_concilia(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.analizar(tmp, [_bot("1", "nan"), _bot("2", "inf")],
                             [_iq("1", "nan"), _iq("2", "inf")])
            self.assertEqual(r["conciliadas_preliminares"], 0)
            self.assertEqual(r["exclusiones"]["BOT_PNL_INVALIDO"], 2)

    def test_exportacion_broker_malformada_no_se_repara(self):
        with tempfile.TemporaryDirectory() as tmp:
            bot = _crear(tmp, "bot.csv", BOT, [_bot("1")])
            broker = _crear(tmp, "iq.csv", ["order_id", "pnl"], [
                {"order_id": "1", "pnl": "20.75"}
            ])
            r = conciliar_exportacion(bot, broker)
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["broker_error"], "COLUMNAS_FALTANTES")


if __name__ == "__main__":
    unittest.main()
