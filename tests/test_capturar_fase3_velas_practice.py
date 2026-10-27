import csv
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from capturar_fase3_velas_practice import (
    CORTE_F3_UTC,
    capturar,
    seleccionar_velas_cerradas_vigentes,
    validar_top_oficial,
)


def mod(nombre, **datos):
    objeto = types.ModuleType(nombre)
    for clave, valor in datos.items():
        setattr(objeto, clave, valor)
    return objeto


class CapturaFase3PracticeTests(unittest.TestCase):
    def test_top_1_a_20_sin_duplicaciones(self):
        top = [{"activo": "A", "tipo": "turbo"}]
        self.assertEqual(validar_top_oficial(top), top)
        with self.assertRaises(ValueError):
            validar_top_oficial([])
        with self.assertRaises(ValueError):
            validar_top_oficial(top * 21)
        with self.assertRaises(ValueError):
            validar_top_oficial(top * 2)
        with self.assertRaises(ValueError):
            validar_top_oficial([{"activo": "A", "tipo": "binary"}])

    def test_bloquea_real_antes_de_conectar(self):
        modulos = {"config": mod("config", MODO_CUENTA="REAL")}
        with patch.dict(sys.modules, modulos):
            with self.assertRaisesRegex(RuntimeError, "PRACTICE"):
                capturar()

    def test_captura_aislada_sin_borrar_archivos_previos(self):
        class Balance:
            def get_balance_mode(self):
                return "PRACTICE"

        referencia = int(CORTE_F3_UTC) + 86400 + 201*60

        def descarga(tipo, activo):
            ruta = Path(backtest.CARPETA_DATA) / (tipo + "_" + activo + ".csv")
            with ruta.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["tipo", "activo", "from", "open", "close", "max", "min", "volume"])
                for n in range(201):
                    writer.writerow([tipo, activo, referencia - (200-n)*60,
                                     1, 1, 2, 0, 0])
            return True

        backtest = mod("backtest_data", descargar_velas_activo=descarga)
        modulos = {
            "config": mod("config", MODO_CUENTA="PRACTICE"),
            "conexion": mod("conexion", conectar=lambda: None),
            "mercado": mod("mercado", obtener_activos=lambda: [
                {"activo": "ACTIVO", "tipo": "turbo"}
            ], _timestamp_servidor_iq=lambda: referencia),
            "backtest_data": backtest,
            "estado": mod("estado", Iq=Balance()),
        }
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            previo = raiz / "previo.csv"
            previo.write_text("dato anterior", encoding="utf-8")
            with patch.dict(sys.modules, modulos):
                ruta, r = capturar(raiz)
            self.assertTrue(previo.exists())
            self.assertEqual(previo.read_text(encoding="utf-8"), "dato anterior")
            self.assertEqual(r["modo"], "PRACTICE")
            self.assertFalse(r["autoriza_operaciones"])
            self.assertEqual(r["total_activos"], 1)
            self.assertEqual(len(r["datasets"][0]["sha256"]), 64)
            self.assertEqual(r["datasets"][0]["velas"], 200)
            self.assertEqual(len(list(csv.DictReader((ruta/"turbo_ACTIVO.csv").open()))), 201)
            self.assertEqual(len(list(csv.DictReader((ruta/"cerradas"/"turbo_ACTIVO.csv").open()))), 200)
            self.assertEqual(json.loads((ruta/"manifest.json").read_text())["total_activos"], 1)

    def test_diagnostico_acumula_fallos_y_no_aprueba_top_parcial(self):
        class Balance:
            def get_balance_mode(self):
                return "PRACTICE"

        referencia = int(CORTE_F3_UTC) + 86400 + 201*60

        def descarga(tipo, activo):
            ruta = Path(backtest.CARPETA_DATA) / (tipo + "_" + activo + ".csv")
            with ruta.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["tipo", "activo", "from", "open", "close", "max", "min", "volume"])
                desplazamiento = 100000 if activo.startswith("STALE") else 0
                for n in range(201):
                    writer.writerow([tipo, activo, referencia - (200-n)*60 - desplazamiento,
                                     1, 1, 2, 0, 0])
            return True

        backtest = mod("backtest_data", descargar_velas_activo=descarga)
        modulos = {
            "config": mod("config", MODO_CUENTA="PRACTICE"),
            "conexion": mod("conexion", conectar=lambda: None),
            "mercado": mod("mercado", obtener_activos=lambda: [
                {"activo": "STALE", "tipo": "turbo"},
                {"activo": "OK", "tipo": "turbo"},
                {"activo": "STALE2", "tipo": "turbo"},
            ], _timestamp_servidor_iq=lambda: referencia),
            "backtest_data": backtest,
            "estado": mod("estado", Iq=Balance()),
        }
        with tempfile.TemporaryDirectory() as temporal:
            with patch.dict(sys.modules, modulos):
                with self.assertRaisesRegex(RuntimeError, "2/3"):
                    capturar(temporal)
            directorios = list(Path(temporal).iterdir())
            self.assertEqual(len(directorios), 1)
            destino = directorios[0]
            self.assertFalse((destino / "manifest.json").exists())
            self.assertTrue((destino / "turbo_OK.csv").exists())
            self.assertTrue((destino / "cerradas" / "turbo_OK.csv").exists())
            diag = json.loads((destino / "diagnostico_no_validado.json").read_text(encoding="utf-8"))
            self.assertEqual(diag["total_activos_top"], 3)
            self.assertEqual(diag["activos_cerrados_validos"], 1)
            self.assertEqual([x["activo"] for x in diag["fallos"]], ["STALE", "STALE2"])
            self.assertFalse(diag["autoriza_replay"])

    def test_no_incluye_vela_abierta_ni_acepta_stale(self):
        referencia = int(CORTE_F3_UTC) + 86400 + 201*60
        filas = [{"from": str(referencia - (200-n)*60)} for n in range(201)]
        cerradas = seleccionar_velas_cerradas_vigentes(filas, referencia)
        self.assertEqual(len(cerradas), 200)
        self.assertEqual(int(cerradas[-1]["from"]), referencia - 60)
        antiguas = [
            {"from": str(referencia - (220-n)*60)} for n in range(201)
        ]
        with self.assertRaisesRegex(ValueError, "DESACTUALIZADA"):
            seleccionar_velas_cerradas_vigentes(antiguas, referencia)
        con_hueco = [{"from": str(referencia - 201*60)}] + filas[:100] + filas[101:]
        with self.assertRaisesRegex(ValueError, "HUECO_TEMPORAL"):
            seleccionar_velas_cerradas_vigentes(con_hueco, referencia)



if __name__ == "__main__":
    unittest.main()
