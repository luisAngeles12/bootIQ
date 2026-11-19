"""R9-10: cortes temporales estrictos; sin red ni escritura de memoria."""
import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.auditar_particion_temporal_fase9 import auditar_particion


CAMPOS = ["order_id", "modo_cuenta_configurado", "estado", "resultado", "fecha"]


def fila(oid, minuto, *, modo="PRACTICE", estado="CERRADA", pnl="20.75"):
    fecha = (datetime(2026, 11, 19, tzinfo=timezone.utc) +
             timedelta(minutes=minuto)).isoformat()
    return {"order_id": oid, "modo_cuenta_configurado": modo,
            "estado": estado, "resultado": pnl, "fecha": fecha}


class ParticionTemporalFase9Tests(unittest.TestCase):
    def crear(self, carpeta, filas, campos=CAMPOS):
        ruta = Path(carpeta) / "historial.csv"
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(filas)
        return ruta

    def test_corte_estricto_ordenado_sin_modificar_historial(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i, pnl="20.75" if i % 2 else "-25")
                     for i in range(50)]
            ruta = self.crear(tmp, list(reversed(filas)))
            antes = ruta.read_bytes()
            r = auditar_particion(ruta)
            self.assertEqual(r["estado"], "PRELIMINAR_NO_VERIFICADO_IQ")
            self.assertEqual((r["train"], r["oos"]), (35, 15) if False else (30, 20))
            self.assertLess(r["fin_train_utc"], r["inicio_oos_utc"])
            self.assertEqual(r["solapamiento_ids"], 0)
            self.assertEqual(antes, ruta.read_bytes())

    def test_no_partir_mismo_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), 0 if i < 25 else 1) for i in range(50)]
            ruta = self.crear(tmp, filas)
            r = auditar_particion(ruta)
            self.assertEqual(r["estado"], "PRELIMINAR_NO_VERIFICADO_IQ")
            self.assertEqual((r["train"], r["oos"]), (25, 25))
            self.assertTrue(r["corte_estricto"])

    def test_duplicados_no_cuentan_y_pueden_bloquear_muestra(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i) for i in range(40)]
            filas.append(fila("0", 60))
            ruta = self.crear(tmp, filas)
            r = auditar_particion(ruta, minimo_train=20, minimo_oos=20)
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "MUESTRA_INSUFICIENTE")
            self.assertEqual(r["exclusiones"]["ORDER_ID_REPETIDO"], 2)

    def test_filtros_no_promueven_real_sin_modo_abiertas_empates_ni_fecha_sin_zona(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [
                fila("a", 1, modo="REAL"),
                fila("b", 2, modo=""),
                fila("c", 3, estado="ABIERTA"),
                fila("d", 4, pnl="0.0"),
                fila("e", 5, pnl="nan"),
                fila("f", 6),
            ]
            filas[-1]["fecha"] = "2026-11-19T00:06:00"
            r = auditar_particion(self.crear(tmp, filas))
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["candidatas_tras_filtros"], 0)
            self.assertEqual(r["exclusiones"]["MODO_NO_VERIFICADO_PRACTICE"], 2)
            self.assertEqual(r["exclusiones"]["SIN_CIERRE_EXPLICITO"], 1)
            self.assertEqual(r["exclusiones"]["RESULTADO_NO_VALIDO_TRAIN"], 2)
            self.assertEqual(r["exclusiones"]["FECHA_SIN_ZONA"], 1)

    def test_esquema_incompleto_falla_cerrado(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = self.crear(tmp, [{"order_id": "1"}], campos=["order_id"])
            r = auditar_particion(ruta)
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "COLUMNAS_FALTANTES")

    def test_mismo_timestamp_no_ofrece_corte_inventado(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = self.crear(tmp, [fila(str(i), 1) for i in range(50)])
            r = auditar_particion(ruta)
            self.assertEqual(r["causa"], "SIN_CORTE_TEMPORAL")


if __name__ == "__main__":
    unittest.main()
