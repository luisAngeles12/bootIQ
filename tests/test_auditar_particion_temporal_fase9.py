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
            self.assertEqual((r["train"], r["oos"]), (30, 20))
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


    def test_fecha_apertura_sin_zona_solo_con_hipotesis_explicita(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i) for i in range(50)]
            for f in filas:
                f["fecha"] = f["fecha"].replace("+00:00", "")
            ruta = self.crear(tmp, filas)
            antes = ruta.read_bytes()
            estricto = auditar_particion(ruta)
            self.assertEqual(estricto["estado"], "NO_APTO")
            self.assertEqual(estricto["exclusiones"]["FECHA_SIN_ZONA"], 50)
            supuesto = auditar_particion(ruta, offset_origen_minutos=-240)
            self.assertEqual(supuesto["estado"], "PRELIMINAR_NO_VERIFICADO_IQ")
            self.assertEqual(supuesto["fechas_con_offset_asumido"], 50)
            self.assertFalse(supuesto["apto_para_memoria_productiva"])
            self.assertFalse(supuesto["cierre_temporal_verificado"])
            self.assertEqual(supuesto["fin_train_utc"], "2026-11-19T04:29:00+00:00")
            self.assertEqual(ruta.read_bytes(), antes)

    def test_offset_invalido_falla_sin_leer_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = self.crear(tmp, [fila("1", 1)])
            for valor in (1440, -1440, "0", True):
                with self.subTest(valor=valor):
                    with self.assertRaises(ValueError):
                        auditar_particion(ruta, offset_origen_minutos=valor)

    def test_fecha_con_offset_original_no_se_sustituye_por_hipotesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = self.crear(tmp, [fila(str(i), i) for i in range(50)])
            r = auditar_particion(ruta, offset_origen_minutos=-240)
            self.assertEqual(r["fechas_con_offset_asumido"], 0)
            self.assertFalse(r["cierre_temporal_verificado"])
            self.assertFalse(r["apto_para_memoria_productiva"])


    def test_train_conciliado_antes_de_primera_apertura_oos(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i * 3) for i in range(50)]
            for f in filas:
                inicio = datetime.fromisoformat(f["fecha"])
                f["fecha_conciliacion_local_utc"] = (
                    inicio + timedelta(minutes=1)
                ).isoformat()
            ruta = self.crear(tmp, filas, campos=CAMPOS + [
                "fecha_conciliacion_local_utc"
            ])
            original = ruta.read_bytes()
            resultado = auditar_particion(ruta)
            self.assertTrue(resultado["separacion_local_sin_fuga"])
            self.assertEqual(resultado["train_sin_conciliacion_utc"], 0)
            self.assertEqual(resultado["train_con_resultado_conocido_tarde"], 0)
            self.assertFalse(resultado["apto_para_memoria_productiva"])
            self.assertEqual(ruta.read_bytes(), original)

    def test_train_conciliado_en_apertura_oos_impide_validacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i * 3) for i in range(50)]
            for f in filas:
                inicio = datetime.fromisoformat(f["fecha"])
                f["fecha_conciliacion_local_utc"] = (
                    inicio + timedelta(minutes=1)
                ).isoformat()
            filas[29]["fecha_conciliacion_local_utc"] = filas[30]["fecha"]
            ruta = self.crear(tmp, filas, campos=CAMPOS + [
                "fecha_conciliacion_local_utc"
            ])
            resultado = auditar_particion(ruta)
            self.assertFalse(resultado["separacion_local_sin_fuga"])
            self.assertEqual(resultado["train_con_resultado_conocido_tarde"], 1)

    def test_falta_conciliacion_train_no_infiere_cierre_de_expiracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i * 3) for i in range(50)]
            ruta = self.crear(tmp, filas)
            resultado = auditar_particion(ruta)
            self.assertFalse(resultado["separacion_local_sin_fuga"])
            self.assertEqual(resultado["train_sin_conciliacion_utc"], 30)
            self.assertEqual(resultado["cierres_conciliacion_utc_faltantes"], 50)

    def test_fecha_conciliacion_invalida_o_anterior_se_rechaza(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i * 3) for i in range(50)]
            for f in filas:
                f["fecha_conciliacion_local_utc"] = f["fecha"]
            filas[0]["fecha_conciliacion_local_utc"] = "sin_fecha"
            filas[1]["fecha_conciliacion_local_utc"] = "2026-11-19T03:00:00"
            filas[2]["fecha_conciliacion_local_utc"] = (
                datetime.fromisoformat(filas[2]["fecha"]) -
                timedelta(seconds=1)
            ).isoformat()
            ruta = self.crear(tmp, filas, campos=CAMPOS + [
                "fecha_conciliacion_local_utc"
            ])
            resultado = auditar_particion(ruta)
            self.assertFalse(resultado["separacion_local_sin_fuga"])
            self.assertEqual(resultado["cierres_conciliacion_utc_faltantes"], 1)
            self.assertEqual(resultado["cierres_conciliacion_utc_invalidos"], 1)
            self.assertEqual(resultado["cierres_anteriores_a_apertura"], 1)

    def test_offset_supuesto_nunca_certifica_separacion_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = [fila(str(i), i * 3) for i in range(50)]
            for f in filas:
                apertura = datetime.fromisoformat(f["fecha"])
                f["fecha_conciliacion_local_utc"] = (
                    apertura + timedelta(minutes=1)
                ).isoformat()
                f["fecha"] = apertura.replace(tzinfo=None).isoformat()
            ruta = self.crear(tmp, filas, campos=CAMPOS + [
                "fecha_conciliacion_local_utc"
            ])
            resultado = auditar_particion(ruta, offset_origen_minutos=0)
            self.assertEqual(resultado["fechas_con_offset_asumido"], 50)
            self.assertFalse(resultado["separacion_local_sin_fuga"])


if __name__ == "__main__":
    unittest.main()
