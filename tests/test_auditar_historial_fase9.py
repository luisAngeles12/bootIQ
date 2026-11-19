"""R9-07: diagnóstico del historial sin alterar archivos ni entrenar."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.auditar_historial_fase9 import analizar_historial


class AuditarHistorialFase9Tests(unittest.TestCase):
    def crear_csv(self, carpeta, filas):
        ruta = Path(carpeta) / "historial_bot.csv"
        with ruta.open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=[
                "order_id", "resultado", "estado_operacion", "fecha",
                "modo_cuenta_configurado", "origen_autoridad",
            ])
            escritor.writeheader()
            escritor.writerows(filas)
        return ruta

    def test_candidatas_requieren_id_practice_cierre_y_win_loss(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = self.crear_csv(carpeta, [
                {"order_id": "1", "resultado": "WIN", "estado_operacion": "CERRADA",
                 "fecha": "100", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "2", "resultado": "LOSS", "estado_operacion": "ABIERTA",
                 "fecha": "101", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "3", "resultado": "WIN", "estado_operacion": "CERRADA",
                 "fecha": "102", "modo_cuenta_configurado": "REAL"},
                {"order_id": "", "resultado": "LOSS", "estado_operacion": "CERRADA",
                 "fecha": "103", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "4", "resultado": "20.75", "estado_operacion": "CERRADA",
                 "fecha": "104", "modo_cuenta_configurado": "PRACTICE"},
            ])
            datos = analizar_historial(ruta)
            self.assertEqual(datos["filas_candidatas_preliminares_practice"], 1)
            self.assertEqual(datos["filas_sin_order_id"], 1)
            self.assertEqual(datos["ids_candidatos_distintos"], 1)

    def test_detecta_ids_repetidos_y_meta_diferentes(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = self.crear_csv(carpeta, [
                {"order_id": "111", "resultado": "", "estado_operacion": "ABIERTA",
                 "fecha": "100", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "111", "resultado": "WIN", "estado_operacion": "CERRADA",
                 "fecha": "101", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "222", "resultado": "LOSS", "estado_operacion": "CERRADA",
                 "fecha": "102", "modo_cuenta_configurado": "PRACTICE"},
            ])
            datos = analizar_historial(ruta)
            self.assertEqual(datos["order_ids_repetidos"], 1)
            self.assertEqual(datos["order_ids_con_metadatos_distintos"], 1)
            self.assertEqual(datos["order_ids_distintos"], 2)

    def test_no_fabrica_fechas_ni_cambia_csv(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = self.crear_csv(carpeta, [
                {"order_id": "11", "resultado": "WIN", "estado_operacion": "CERRADA",
                 "fecha": "sin_fecha", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "12", "resultado": "LOSS", "estado_operacion": "CERRADA",
                 "fecha": "nan", "modo_cuenta_configurado": "PRACTICE"},
            ])
            antes = ruta.read_bytes()
            datos = analizar_historial(ruta)
            self.assertEqual(datos["candidatas_fechadas"], 0)
            self.assertIsNone(datos["min_fecha_candidata"])
            self.assertEqual(ruta.read_bytes(), antes)


    def test_importes_monetarios_cierre_practice_separados_de_etiquetas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = self.crear_csv(carpeta, [
                {"order_id": "1", "resultado": "20.75", "estado_operacion": "OPERADA_DIRECTA",
                 "fecha": "2026-11-19 14:30:00", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "2", "resultado": "-25.0", "estado_operacion": "OPERADA_DIRECTA",
                 "fecha": "2026-11-19T14:31:00", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "3", "resultado": "0.0", "estado_operacion": "OPERADA_DIRECTA",
                 "fecha": "2026-11-19T14:32:00", "modo_cuenta_configurado": "PRACTICE"},
            ])
            datos = analizar_historial(ruta)
            self.assertEqual(datos["filas_con_fecha_iso"], 3)
            self.assertEqual(datos["tipos_resultado_monetario"]["GANANCIA"], 1)
            self.assertEqual(datos["tipos_resultado_monetario"]["PERDIDA"], 1)
            self.assertEqual(datos["tipos_resultado_monetario"]["EMPATE"], 1)
            self.assertEqual(datos["ids_practice_cierre_con_pnl_finito"], 0)
            self.assertEqual(datos["filas_candidatas_preliminares_practice"], 0)

    def test_cierre_explicito_distinto_de_entrada_abierta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "historial_bot.csv"
            with ruta.open("w", encoding="utf-8", newline="") as archivo:
                escritor = csv.DictWriter(archivo, fieldnames=[
                    "order_id", "resultado", "estado", "estado_operacion",
                    "fecha", "modo_cuenta_configurado", "origen_autoridad",
                ])
                escritor.writeheader()
                escritor.writerows([
                    {"order_id": "1", "resultado": "20.75", "estado": "CERRADA",
                     "estado_operacion": "OPERADA_DIRECTA",
                     "fecha": "2026-11-19T14:30:00", "modo_cuenta_configurado": "PRACTICE"},
                    {"order_id": "2", "resultado": "-25", "estado": "ABIERTA",
                     "estado_operacion": "OPERADA_DIRECTA",
                     "fecha": "2026-11-19T14:31:00", "modo_cuenta_configurado": "PRACTICE"},
                ])
            datos = analizar_historial(ruta)
            self.assertEqual(datos["filas_cierre_con_pnl_finito_por_modo"]["PRACTICE"], 1)
            self.assertEqual(datos["ids_practice_cierre_con_pnl_finito"], 1)
            self.assertEqual(datos["cierre_practice_con_fecha_iso"], 1)

    def test_pnl_no_finito_y_modo_ausente_no_se_promueven(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = self.crear_csv(carpeta, [
                {"order_id": "1", "resultado": "nan", "estado_operacion": "CERRADA",
                 "fecha": "no-fecha", "modo_cuenta_configurado": "PRACTICE"},
                {"order_id": "2", "resultado": "25.0", "estado_operacion": "CERRADA",
                 "fecha": "2026-11-19T14:30:00", "modo_cuenta_configurado": ""},
            ])
            datos = analizar_historial(ruta)
            self.assertEqual(datos["tipos_resultado_monetario"]["NO_FINITO"], 1)
            self.assertEqual(datos["ids_practice_cierre_con_pnl_finito"], 0)


if __name__ == "__main__":
    unittest.main()
