"""R9-14: ventanas 20 observacionales con corte de fuga estricto."""
import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.evaluar_oos_descriptivo_fase9 import evaluar_oos, _metricas


CAMPOS = [
    "order_id", "modo_cuenta_configurado", "estado", "resultado",
    "fecha", "fecha_conciliacion_local_utc", "origen_autoridad",
]


def filas_base(n=50, *, wins_oos=12):
    base = datetime(2026, 11, 19, tzinfo=timezone.utc)
    filas = []
    for i in range(n):
        inicio = base + timedelta(minutes=i * 3)
        cierre = inicio + timedelta(minutes=1)
        pnl = 20.75 if (i < 30 or (i - 30) % 20 < wins_oos) else -25
        filas.append({
            "order_id": str(i).zfill(5),
            "modo_cuenta_configurado": "PRACTICE",
            "estado": "CERRADA",
            "resultado": str(pnl),
            "fecha": inicio.isoformat(),
            "fecha_conciliacion_local_utc": cierre.isoformat(),
            "origen_autoridad": "BOOTSTRAP_PRACTICE_SIN_HISTORIAL",
        })
    return filas


class EvaluacionOosDescriptivaFase9Tests(unittest.TestCase):
    def crear(self, carpeta, filas):
        ruta = Path(carpeta) / "historial.csv"
        with ruta.open("w", newline="", encoding="utf-8") as archivo:
            w = csv.DictWriter(archivo, fieldnames=CAMPOS)
            w.writeheader()
            w.writerows(filas)
        return ruta

    def test_bloque_60_positivo_es_descriptivo_no_valida_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = self.crear(tmp, filas_base())
            anterior = ruta.read_bytes()
            r = evaluar_oos(ruta)
            self.assertEqual(r["estado"], "DESCRIPTIVO_NO_VERIFICADO_BROKER")
            self.assertEqual(r["oos_operaciones"], 20)
            self.assertEqual(r["bloques_20_no_solapados"][0]["ganadas"], 12)
            self.assertEqual(r["bloques_20_no_solapados"][0]["neto"], 49.0)
            self.assertTrue(r["cumple_todos_bloques_20"])
            self.assertEqual(r["ventanas_moviles_20"], 1)
            self.assertFalse(r["habilita_trading"])
            self.assertFalse(r["memoria_generada"])
            self.assertIn("BOOTSTRAP_PRACTICE_SIN_HISTORIAL",
                          r["autoridades_observadas"])
            self.assertEqual(anterior, ruta.read_bytes())

    def test_60_por_ciento_no_implica_neto_positivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            for f in filas[30:]:
                if float(f["resultado"]) > 0:
                    f["resultado"] = "10"
            r = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(r["bloques_20_no_solapados"][0]["ganadas"], 12)
            self.assertLess(r["bloques_20_no_solapados"][0]["neto"], 0)
            self.assertFalse(r["cumple_todos_bloques_20"])

    def test_cierre_train_tardio_falla_cerrado_sin_metricas(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            filas[29]["fecha_conciliacion_local_utc"] = filas[30]["fecha"]
            r = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"],
                             "RESULTADOS_TRAIN_NO_CONOCIDOS_ANTES_DE_OOS")
            self.assertNotIn("bloques_20_no_solapados", r)

    def test_oos_sin_cierre_no_es_evaluable(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            filas[40]["fecha_conciliacion_local_utc"] = ""
            r = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "OOS_SIN_MARCA_CONCILIACION")

    def test_menos_de_20_oos_no_crea_bloque_falso(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluar_oos(self.crear(tmp, filas_base(35)))
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "PARTICION_INVALIDA")

    def test_ventanas_moviles_pueden_fallar_aunque_bloques_pasaron(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base(70, wins_oos=12)
            r = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(r["oos_operaciones"], 21)
            # 70 filas, TRAIN 49 y OOS 21; basta una ventana adversa
            # para comprobar que no se infiere consistencia del agregado.
            self.assertGreaterEqual(r["ventanas_moviles_20"], 2)


    def test_apertura_utc_explicita_prevalece_sobre_fecha_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            for f in filas:
                f["fecha_apertura_registro_local_utc"] = f["fecha"]
                f["fecha"] = "FECHA_LEGACY_NO_USAR"
            ruta = Path(tmp) / "historial.csv"
            with ruta.open("w", newline="", encoding="utf-8") as archivo:
                writer = csv.DictWriter(
                    archivo, fieldnames=CAMPOS +
                    ["fecha_apertura_registro_local_utc"]
                )
                writer.writeheader()
                writer.writerows(filas)
            previo = ruta.read_bytes()
            r = evaluar_oos(ruta)
            self.assertEqual(r["estado"], "DESCRIPTIVO_NO_VERIFICADO_BROKER")
            self.assertEqual(r["oos_operaciones"], 20)
            self.assertTrue(r["corte"]["aperturas_utc_100pct"])
            self.assertEqual(previo, ruta.read_bytes())

    def test_marca_apertura_utc_invalida_no_fabrica_resultado_oos(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base(51)
            for f in filas:
                f["fecha_apertura_registro_local_utc"] = f["fecha"]
                f["fecha"] = "FECHA_LEGACY_NO_USAR"
            filas[-1]["fecha_apertura_registro_local_utc"] = "fecha_corrupta"
            ruta = Path(tmp) / "historial.csv"
            with ruta.open("w", newline="", encoding="utf-8") as archivo:
                writer = csv.DictWriter(
                    archivo, fieldnames=CAMPOS +
                    ["fecha_apertura_registro_local_utc"]
                )
                writer.writeheader()
                writer.writerows(filas)
            r = evaluar_oos(ruta)
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "UNIVERSO_PRACTICE_INCOMPLETO")
            self.assertEqual(r["filas_practice_no_admisibles"], 1)
            self.assertNotIn("bloques_20_no_solapados", r)


    def _exportacion_iq(self, carpeta, filas, *, omitir=None, alterar=None):
        ruta = Path(carpeta) / "iq_export.csv"
        with ruta.open("w", newline="", encoding="utf-8") as archivo:
            writer = csv.DictWriter(archivo, fieldnames=[
                "order_id", "modo_cuenta", "estado", "pnl", "fecha_cierre_utc"
            ])
            writer.writeheader()
            for f in filas:
                if f["order_id"] == omitir:
                    continue
                cierre = datetime.fromisoformat(f["fecha_conciliacion_local_utc"])
                pnl = f["resultado"]
                if f["order_id"] == alterar:
                    pnl = "-25" if float(pnl) > 0 else "20.75"
                writer.writerow({
                    "order_id": f["order_id"], "modo_cuenta": "PRACTICE",
                    "estado": "CERRADA", "pnl": pnl,
                    "fecha_cierre_utc": (
                        cierre - timedelta(seconds=20)
                    ).isoformat(),
                })
        return ruta

    def test_cotejo_completo_oos_aun_no_certifica_procedencia_broker(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            ruta = self.crear(tmp, filas)
            iq = self._exportacion_iq(tmp, filas)
            previa = (ruta.read_bytes(), iq.read_bytes())
            resultado = evaluar_oos(ruta, exportacion_iq=iq)
            self.assertEqual(resultado["estado"],
                             "DESCRIPTIVO_NO_VERIFICADO_BROKER")
            self.assertEqual(resultado["cotejo_offline"]["objetivo_oos_total"], 20)
            self.assertEqual(resultado["cotejo_offline"]["conciliadas_preliminares"], 20)
            self.assertTrue(resultado["cotejo_offline"]["objetivo_oos_conciliado_completo"])
            self.assertFalse(resultado["origen_broker_independiente_certificado"])
            self.assertFalse(resultado["habilita_trading"])
            self.assertEqual(previa, (ruta.read_bytes(), iq.read_bytes()))

    def test_discrepancia_pnl_oos_bloquea_metricas(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            ruta = self.crear(tmp, filas)
            iq = self._exportacion_iq(tmp, filas, alterar=filas[35]["order_id"])
            resultado = evaluar_oos(ruta, exportacion_iq=iq)
            self.assertEqual(resultado["estado"], "NO_APTO")
            self.assertEqual(resultado["causa"], "OOS_DIFIERE_BROKER_OFFLINE")
            self.assertNotIn("bloques_20_no_solapados", resultado)

    def test_id_oos_ausente_en_exportacion_bloquea_metricas(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            ruta = self.crear(tmp, filas)
            iq = self._exportacion_iq(tmp, filas, omitir=filas[45]["order_id"])
            resultado = evaluar_oos(ruta, exportacion_iq=iq)
            self.assertEqual(resultado["estado"], "NO_APTO")
            self.assertEqual(resultado["causa"], "OOS_DIFIERE_BROKER_OFFLINE")
            self.assertEqual(
                resultado["cotejo_offline"]["exclusiones"]["SIN_ID_UNICO_BROKER"], 1
            )


    def test_drawdown_y_racha_son_de_pnl_no_de_balance_porcentual(self):
        bloque = [
            (None, str(i), pnl, "TEST")
            for i, pnl in enumerate([20.75, -25, -25, 20.75, -25])
        ]
        datos = _metricas(bloque)
        self.assertEqual(datos["operaciones"], 5)
        self.assertEqual(datos["ganadas"], 2)
        self.assertEqual(datos["perdidas"], 3)
        self.assertEqual(datos["neto"], -33.5)
        self.assertEqual(datos["drawdown_maximo_unidades"], 54.25)
        self.assertEqual(datos["racha_maxima_perdidas"], 2)
        self.assertFalse(datos["cumple_60_y_neto_positivo"])

    def test_oos_descriptivo_informa_peor_ventana_y_muestra_incompleta(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluar_oos(self.crear(tmp, filas_base(70, wins_oos=12)))
            self.assertEqual(r["estado"], "DESCRIPTIVO_NO_VERIFICADO_BROKER")
            self.assertEqual(r["oos_operaciones"], 21)
            self.assertEqual(r["bloques_20_completos"], 1)
            self.assertEqual(r["operaciones_restantes_sin_bloque_completo"], 1)
            self.assertGreaterEqual(r["ventanas_moviles_20"], 2)
            self.assertIn("peor_winrate_ventana_20", r)
            self.assertIn("peor_neto_ventana_20", r)
            self.assertIn("drawdown_maximo_unidades", r["resumen_oos_descriptivo"])
            self.assertFalse(r["evidencia_sostenida_60_pct"])
            self.assertFalse(r["habilita_trading"])

    def test_un_bloque_60_no_demuestra_meta_sostenida(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluar_oos(self.crear(tmp, filas_base()))
            self.assertTrue(r["cumple_todos_bloques_20"])
            self.assertTrue(r["cumple_todas_ventanas_moviles_20"])
            self.assertFalse(r["evidencia_sostenida_60_pct"])
            self.assertEqual(
                r["calidad_evidencia"], "DESCRIPTIVO_HISTORICO_NO_INDEPENDIENTE"
            )

    def test_oos_fallas_monetarias_son_reportadas_sin_ocultarse(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            for fila in filas[30:]:
                if float(fila["resultado"]) > 0:
                    fila["resultado"] = "10"
            r = evaluar_oos(self.crear(tmp, filas))
            self.assertFalse(r["cumple_todos_bloques_20"])
            self.assertEqual(len(r["bloques_20_que_incumplen"]), 1)
            self.assertEqual(r["bloques_20_que_incumplen"][0]["ganadas"], 12)
            self.assertLess(r["bloques_20_que_incumplen"][0]["neto"], 0)
            self.assertFalse(r["evidencia_sostenida_60_pct"])


    def test_familias_sin_muestra_no_se_declaran_consistentes(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            for i, fila in enumerate(filas):
                fila["familia_setup"] = "RUPTURA" if i % 2 else "REVERSAL"
            ruta = Path(tmp) / "historial.csv"
            with ruta.open("w", encoding="utf-8", newline="") as archivo:
                w = csv.DictWriter(archivo, fieldnames=CAMPOS + ["familia_setup"])
                w.writeheader()
                w.writerows(filas)
            resultado = evaluar_oos(ruta)
            self.assertEqual(resultado["estado"], "DESCRIPTIVO_NO_VERIFICADO_BROKER")
            self.assertEqual(resultado["operaciones_sin_familia"], 0)
            self.assertEqual(resultado["familias_con_muestra_minima_20"], 0)
            self.assertEqual(resultado["familias"]["RUPTURA"]["operaciones"], 10)
            self.assertEqual(resultado["familias"]["REVERSAL"]["operaciones"], 10)
            self.assertEqual(resultado["familias"]["RUPTURA"]["estado"],
                             "SIN_MUESTRA_MINIMA_20")
            self.assertFalse(resultado["familias"]["REVERSAL"][
                "cumple_todas_ventanas_observadas"])

    def test_familia_vacia_se_reporta_sin_imputar_una_estrategia(self):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = evaluar_oos(self.crear(tmp, filas_base()))
            self.assertEqual(resultado["operaciones_sin_familia"], 20)
            self.assertIn("SIN_FAMILIA", resultado["familias"])
            self.assertEqual(resultado["familias_con_muestra_minima_20"], 0)

    def test_una_familia_con_20_reporta_resultado_descriptivo_sin_certificar(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base()
            for f in filas:
                f["familia_setup"] = "RUPTURA"
            ruta = Path(tmp) / "historial.csv"
            with ruta.open("w", encoding="utf-8", newline="") as archivo:
                w = csv.DictWriter(archivo, fieldnames=CAMPOS + ["familia_setup"])
                w.writeheader()
                w.writerows(filas)
            resultado = evaluar_oos(ruta)
            self.assertEqual(resultado["familias_con_muestra_minima_20"], 1)
            self.assertEqual(resultado["familias"]["RUPTURA"]["ventanas_moviles_20"], 1)
            self.assertEqual(resultado["familias"]["RUPTURA"]["estado"],
                             "DESCRIPTIVO_NO_VERIFICADO")
            self.assertFalse(resultado["evidencia_sostenida_60_pct"])

    def test_empate_en_tramo_oos_no_desaparece_de_bloques_de_20(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base(51)
            filas[42]["resultado"] = "0.0"
            resultado = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(resultado["estado"], "NO_APTO")
            self.assertEqual(resultado["causa"], "UNIVERSO_PRACTICE_INCOMPLETO")
            self.assertEqual(resultado["filas_practice_no_admisibles"], 1)
            self.assertNotIn("bloques_20_no_solapados", resultado)

    def test_cierre_pendiente_oos_tampoco_se_borra_del_universo(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base(51)
            filas[42]["estado"] = "ABIERTA"
            resultado = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(resultado["estado"], "NO_APTO")
            self.assertEqual(resultado["causa"], "UNIVERSO_PRACTICE_INCOMPLETO")
            self.assertEqual(resultado["filas_practice_no_admisibles"], 1)


    def test_empate_antes_del_corte_no_desplaza_oos_silenciosamente(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base(51)
            filas[4]["resultado"] = "0"
            ruta = self.crear(tmp, filas)
            previo = ruta.read_bytes()
            r = evaluar_oos(ruta)
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "UNIVERSO_PRACTICE_INCOMPLETO")
            self.assertEqual(r["filas_practice_no_admisibles"], 1)
            self.assertNotIn("bloques_20_no_solapados", r)
            self.assertEqual(previo, ruta.read_bytes())

    def test_fecha_invalida_practice_antes_del_corte_bloquea(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base(51)
            filas[3]["fecha"] = "INVALIDA"
            r = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "UNIVERSO_PRACTICE_INCOMPLETO")
            self.assertEqual(r["filas_practice_no_admisibles"], 1)

    def test_modo_desconocido_no_se_promueve_a_practice_ni_se_oculta(self):
        with tempfile.TemporaryDirectory() as tmp:
            filas = filas_base(51)
            filas[3]["modo_cuenta_configurado"] = ""
            r = evaluar_oos(self.crear(tmp, filas))
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "UNIVERSO_PRACTICE_INCOMPLETO")
            self.assertEqual(r["filas_sin_modo"], 1)
            self.assertFalse(r["habilita_trading"])


if __name__ == "__main__":
    unittest.main()
