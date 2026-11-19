"""R9-20: clasificación exclusiva sin imputaciones ni escritura."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.clasificar_historial_fase9 import clasificar_historial


CAMPOS = [
    "order_id", "modo_cuenta_configurado", "estado", "resultado", "fecha",
    "fecha_apertura_registro_local_utc", "fecha_conciliacion_local_utc",
]


def fila(oid, modo="PRACTICE", estado="CERRADA", pnl="20.75",
         apertura="2026-11-19T18:00:00+00:00",
         cierre="2026-11-19T18:02:00+00:00"):
    return {
        "order_id": oid, "modo_cuenta_configurado": modo,
        "estado": estado, "resultado": pnl, "fecha": apertura,
        "fecha_apertura_registro_local_utc": apertura,
        "fecha_conciliacion_local_utc": cierre,
    }


class ClasificarHistorialFase9Tests(unittest.TestCase):
    def crear(self, carpeta, filas, campos=CAMPOS):
        ruta = Path(carpeta) / "historial.csv"
        with ruta.open("w", encoding="utf-8", newline="") as a:
            w = csv.DictWriter(a, fieldnames=campos)
            w.writeheader()
            w.writerows(filas)
        return ruta

    def test_clasifica_modoreal_sinmodo_y_cierres_sin_inventar(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = [
                fila("001"), fila("002", modo=""),
                fila("003", modo="REAL"), fila("004", estado="ABIERTA"),
                fila("005", pnl="0"), fila("006", pnl="nan"),
                fila("007", cierre=""), fila("008", apertura="2026-11-19T18:00:00"),
                fila("009", apertura="2026-11-19T18:03:00Z"),
            ]
            ruta = self.crear(tmp, datos)
            antes = ruta.read_bytes()
            r = clasificar_historial(ruta)
            self.assertEqual(r["filas"], len(datos))
            self.assertTrue(r["integridad_conteo"])
            self.assertEqual(r["grupos_excluyentes"]["CUENTA_DESCONOCIDA"], 1)
            self.assertEqual(r["grupos_excluyentes"]["NO_PRACTICE"], 1)
            self.assertEqual(r["grupos_excluyentes"]["PRACTICE_CANDIDATA_NO_CERTIFICADA"], 2)
            self.assertEqual(r["grupos_excluyentes"]["PRACTICE_SOLO_DESCRIPTIVO"], 1)
            self.assertEqual(r["grupos_excluyentes"]["PRACTICE_NO_APTO"], 4)
            self.assertFalse(r["memoria_generada"])
            self.assertFalse(r["habilita_trading"])
            self.assertEqual(antes, ruta.read_bytes())

    def test_ids_duplicados_y_ceros_iniciales_distintos(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = clasificar_historial(self.crear(tmp, [
                fila("001"), fila("001"), fila("1"), fila(""),
            ]))
            self.assertEqual(r["grupos_excluyentes"]["PRACTICE_NO_APTO"], 3)
            self.assertEqual(r["grupos_excluyentes"]["PRACTICE_CANDIDATA_NO_CERTIFICADA"], 1)

    def test_no_promueve_legacy_sin_zona_ni_cierre(self):
        with tempfile.TemporaryDirectory() as tmp:
            registro = fila("1")
            registro["fecha_apertura_registro_local_utc"] = ""
            registro["fecha"] = "2026-11-19 14:00:00"
            r = clasificar_historial(self.crear(tmp, [registro]))
            self.assertEqual(r["razones_excluyentes"]["APERTURA_SIN_ZONA_CONFIRMADA"], 1)

    def test_archivo_incompleto_falla_cerrado(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = clasificar_historial(self.crear(tmp, [
                {"order_id": "1"},
            ], campos=["order_id"]))
            self.assertEqual(r["estado"], "NO_APTO")
            self.assertEqual(r["causa"], "ESQUEMA_INCOMPLETO_O_MALFORMADO")

    def test_no_infiere_fecha_cierre_del_timestamp_configuracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            registro = fila("1", cierre="")
            r = clasificar_historial(self.crear(tmp, [registro]))
            self.assertEqual(r["grupos_excluyentes"]["PRACTICE_SOLO_DESCRIPTIVO"], 1)
            self.assertEqual(r["razones_excluyentes"]["FALTA_CONCILIACION_UTC"], 1)


if __name__ == "__main__":
    unittest.main()
