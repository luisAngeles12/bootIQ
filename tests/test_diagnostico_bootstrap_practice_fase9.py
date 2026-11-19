"""Pruebas R9-25.14: atribucion no certificada y denominador completo."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.diagnostico_bootstrap_practice_fase9 import diagnosticar

CAMPOS = [
    "order_id", "modo_cuenta_configurado", "estado", "resultado", "fecha",
    "familia_setup", "regimen_mercado", "direccion", "origen_autoridad",
]


def fila(oid, pnl="20.75", modo="PRACTICE", fecha="2026-11-19 12:00:00",
         familia="CONTINUACIÓN", regimen="TENDENCIA_SUCIA", direccion="call"):
    return dict(order_id=oid, resultado=pnl, modo_cuenta_configurado=modo,
                estado="CERRADA", fecha=fecha, familia_setup=familia,
                regimen_mercado=regimen, direccion=direccion,
                origen_autoridad="BOOTSTRAP_PRACTICE_SIN_HISTORIAL")


class DiagnosticoBootstrapTests(unittest.TestCase):
    def crear(self, carpeta, filas, columnas=CAMPOS):
        ruta = Path(carpeta) / "historial.csv"
        with ruta.open("w", encoding="utf-8", newline="") as archivo:
            writer = csv.DictWriter(archivo, fieldnames=columnas)
            writer.writeheader()
            writer.writerows(filas)
        return ruta

    def test_desglose_suma_sin_certificar_ni_modificar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = self.crear(carpeta, [
                fila("001", "20.75"),
                fila("002", "-25.00"),
                fila("003", "-25", fecha="2026-11-18 10:00:00",
                     familia="REVERSIÓN", regimen="RANGO_LIMPIO", direccion="put"),
                fila("004", "20.75", modo=""),
            ])
            antes = ruta.read_bytes()
            r = diagnosticar(ruta)
            self.assertEqual(r["estado"], "DESCRIPTIVO_NO_VERIFICADO_BROKER")
            self.assertEqual(r["resumen"]["n"], 3)
            self.assertEqual(r["resumen"]["wins"], 1)
            self.assertEqual(r["resumen"]["losses"], 2)
            self.assertEqual(r["resumen"]["neto"], "-29.25")
            self.assertTrue(r["conteo_conservado"])
            self.assertEqual(r["motivos_exclusion"]["CUENTA_DESCONOCIDA"], 1)
            self.assertEqual(len(r["desgloses"]["familias"]), 2)
            self.assertFalse(r["procedencia_iq_verificada"])
            self.assertFalse(r["validacion_oos"])
            self.assertFalse(r["habilita_trading"])
            self.assertEqual(ruta.read_bytes(), antes)

    def test_exclusion_exclusiva_y_duplicados_globales(self):
        with tempfile.TemporaryDirectory() as carpeta:
            sin_cierre = fila("2")
            sin_cierre["estado"] = "ABIERTA"
            rutas = [
                fila("001"), fila("001"), fila("009", modo="REAL"),
                sin_cierre, fila("3", "0"),
                fila("4", "0.001"), fila("5", "nan"),
                fila("6", fecha="no_fecha"), fila("", "20.75"),
            ]
            r = diagnosticar(self.crear(carpeta, rutas))
            self.assertEqual(r["filas_practice_descriptivas"], 0)
            self.assertEqual(r["filas_excluidas"], len(rutas))
            self.assertEqual(r["motivos_exclusion"]["PRACTICE_ID_AUSENTE_O_DUPLICADO"], 3)
            self.assertEqual(r["motivos_exclusion"]["NO_PRACTICE"], 1)
            self.assertEqual(r["motivos_exclusion"]["PRACTICE_NO_CERRADA"], 1)
            self.assertEqual(r["motivos_exclusion"]["PRACTICE_EMPATE"], 1)
            self.assertEqual(r["motivos_exclusion"]["PRACTICE_PNL_INVALIDO"], 2)
            self.assertEqual(r["motivos_exclusion"]["PRACTICE_FECHA_INVALIDA"], 1)
            self.assertEqual(r["estado"], "SIN_MUESTRA_PRACTICE_APTA")

    def test_n_pequena_no_se_etiqueta_como_ventaja_validada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            r = diagnosticar(self.crear(carpeta, [
                fila(str(i), "20.75") for i in range(3)
            ]))
            self.assertEqual(r["resumen"]["winrate_pct"], 100.0)
            self.assertTrue(r["resumen"]["muestra_menor_20"])
            self.assertFalse(r["validacion_oos"])
            self.assertFalse(r["permite_reconfigurar_estrategia"])

    def test_esquema_incompleto_falla_cerrado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            r = diagnosticar(self.crear(carpeta, [{"order_id": "1"}],
                                          columnas=["order_id"]))
            self.assertEqual(r["causa"], "COLUMNAS_FALTANTES")
            self.assertFalse(r["habilita_trading"])

    def test_archivo_ausente_falla_cerrado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            r = diagnosticar(Path(carpeta) / "no_existe.csv")
            self.assertEqual(r["causa"], "ARCHIVO_ILEGIBLE")
            self.assertFalse(r["memoria_generada"])


if __name__ == "__main__":
    unittest.main()
