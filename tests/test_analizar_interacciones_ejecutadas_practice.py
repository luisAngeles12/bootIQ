"""Regresiones para busqueda cronologica de interacciones PRACTICE."""
import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from analizar_interacciones_ejecutadas_practice import analizar, leer_filas


def fila(order_id, day, patron, pnl, modo="PRACTICE", estado="CERRADA"):
    return {
        "order_id": str(order_id),
        "fecha": "2026-11-{:02d} 12:00:00".format(day),
        "estado": estado,
        "estado_operacion": "OPERADA_DIRECTA",
        "modo_cuenta_configurado": modo,
        "resultado": str(pnl),
        "patron": patron,
        "direccion": "put",
        "tipo_mercado": "TENDENCIA_BAJISTA",
        "calidad_mercado": "NORMAL",
        "direccion_tendencia": "BAJISTA",
    }


def escribir_csv(path, filas):
    with path.open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        writer.writeheader()
        writer.writerows(filas)


class InteraccionesEjecutadasTests(unittest.TestCase):
    def dataset(self):
        filas = []
        order_id = 0
        for day in range(10, 15):
            for patron, cantidad in (("A", 4), ("B", 2)):
                for i in range(cantidad):
                    order_id += 1
                    if patron == "A" and day <= 12:
                        pnl = 20.75 if i < 3 else -25
                    elif patron == "A":
                        pnl = -25
                    elif day >= 13:
                        pnl = 20.75
                    else:
                        pnl = -25
                    filas.append(fila(order_id, day, patron, pnl))
        return filas

    def test_entrenamiento_elige_regla_y_holdout_no_la_reordena(self):
        filas = self.dataset()
        resultado = analizar(filas, min_train=6, min_test=4)
        regla_a = next(
            item for item in resultado["interacciones"]
            if item["regla"] == {
                "patron": "A", "tipo_mercado": "TENDENCIA_BAJISTA"
            }
        )
        self.assertEqual(regla_a["train"]["n"], 12)
        self.assertEqual(regla_a["train"]["winrate_pct"], 75.0)
        self.assertEqual(regla_a["test_oos"]["n"], 8)
        self.assertEqual(regla_a["test_oos"]["winrate_pct"], 0.0)
        self.assertFalse(regla_a["cumple_60_y_neto_positivo_test"])
        self.assertFalse(resultado["promueve_estrategia"])
        self.assertFalse(resultado["autoriza_real"])

        hit_posthoc = next(
            item for item in resultado["descubrimientos_posthoc_test"]
            if item["regla"] == {
                "patron": "B", "tipo_mercado": "TENDENCIA_BAJISTA"
            }
        )
        self.assertEqual(hit_posthoc["train"]["winrate_pct"], 0.0)
        self.assertEqual(hit_posthoc["test_oos"]["winrate_pct"], 100.0)
        self.assertTrue(hit_posthoc["seleccion_posthoc_por_test"])
        self.assertTrue(hit_posthoc["requiere_validacion_prospectiva"])
        self.assertFalse(hit_posthoc["autoriza_operaciones"])
        self.assertNotIn(
            hit_posthoc["regla"],
            [item["regla"] for item in resultado["interacciones"]],
        )

        filas_futuras_cambiadas = [
            dict(f, resultado="20.75")
            if f["fecha"][:10] in ("2026-11-13", "2026-11-14")
            and f["patron"] == "A" else dict(f)
            for f in filas
        ]
        cambiado = analizar(filas_futuras_cambiadas, min_train=6, min_test=4)
        self.assertEqual(
            [x["regla"] for x in resultado["interacciones"]],
            [x["regla"] for x in cambiado["interacciones"]],
        )
        regla_cambiada = next(
            x for x in cambiado["interacciones"] if x["regla"] == regla_a["regla"]
        )
        self.assertEqual(regla_cambiada["test_oos"]["winrate_pct"], 100.0)

    def test_excluye_real_y_abiertas(self):
        filas = self.dataset()
        filas.extend([
            fila(100, 14, "A", 20.75, modo="REAL"),
            fila(101, 14, "A", 20.75, estado="ABIERTA"),
        ])
        resultado = analizar(filas, min_train=6, min_test=4)
        self.assertEqual(resultado["descartes"]["NO_PRACTICE"], 1)
        self.assertEqual(resultado["descartes"]["NO_CERRADA"], 1)
        self.assertEqual(resultado["operaciones_validas_no_empate"], 30)

    def test_pocas_jornadas_no_producen_candidato(self):
        resultado = analizar(
            [fila(day * 100 + i, day, "A", 20.75)
             for day in (10, 11, 12, 13) for i in range(3)],
            min_train=2,
            min_test=2,
        )
        self.assertEqual(resultado["estado"], "JORNADAS_INSUFICIENTES")
        self.assertEqual(resultado["interacciones"], [])
        self.assertFalse(resultado["promueve_estrategia"])
        self.assertEqual(len(resultado["baseline_por_dia"]), 4)
        self.assertEqual(sum(x["n"] for x in resultado["baseline_por_dia"]), 12)
        self.assertTrue(all("neto" in x for x in resultado["baseline_por_dia"]))
        grupos = resultado["grupos_exploratorios"]
        self.assertTrue(grupos)
        patron_a = next(g for g in grupos if g["campo"] == "patron" and g["valor"] == "A")
        self.assertEqual(patron_a["n"], 12)
        self.assertEqual(patron_a["neto"], 249.0)
        self.assertEqual(len(patron_a["por_dia"]), 4)
        self.assertTrue(all(not g["autoriza_operaciones"] for g in grupos))
        self.assertFalse(resultado["autoriza_operaciones"])

    def test_rechaza_parametros_invalidos(self):
        with self.assertRaisesRegex(ValueError, "MIN_TRAIN"):
            analizar([], min_train=1)
        with self.assertRaisesRegex(ValueError, "PROPORCION"):
            analizar([], proporcion_dias_train=float("nan"))

    def test_lee_csv_dentro_de_zip_sin_extraerlo(self):
        filas = [fila(1, 10, "A", 20.75)]
        with tempfile.TemporaryDirectory() as temp:
            carpeta = Path(temp)
            csv_path = carpeta / "historial_bot.csv"
            zip_path = carpeta / "historial.zip"
            escribir_csv(csv_path, filas)
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.write(csv_path, "historial_bot.csv")
            self.assertEqual(leer_filas(zip_path), filas)


if __name__ == "__main__":
    unittest.main()
