import csv
import tempfile
import unittest
from pathlib import Path

from captura_fresca_practice import guardar_captura_fresca
from evaluar_captura_fresca_practice import (
    evaluar_sesion, leer_captura, resumen_sesion,
)


def vela(t, open_=101, close=101, low=100, high=102):
    return {"from": t, "open": open_, "close": close, "min": low, "max": high}


def caso_call(salida=102, con_futuro=True):
    datos = {t: vela(t) for t in range(100, 120)}
    datos[120] = vela(120, open_=100, close=99, low=99, high=101)
    datos[121] = vela(121, open_=99, close=101, low=99, high=101)
    datos[122] = vela(122, open_=101, close=101, low=101, high=102)
    if con_futuro:
        for t in range(123, 183):
            datos[t] = vela(t, close=101)
        datos[182] = vela(182, close=salida, high=max(102, salida),
                          low=min(100, salida))
    return datos


class EvaluarCapturaFrescaTests(unittest.TestCase):
    def test_win_loss_y_empate_60s_sin_futuro_filtrado(self):
        for precio, esperado in ((102, "WIN"), (100, "LOSS"), (101, "EMPATE")):
            with self.subTest(precio=precio):
                eventos = evaluar_sesion(caso_call(precio))
                self.assertEqual(eventos[0]["resultado"], esperado)
                self.assertEqual(eventos[0]["timestamp_senal"], 122)

    def test_sin_vela_futura_no_inventa_resultado(self):
        eventos = evaluar_sesion(caso_call(con_futuro=False))
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["resultado"], "SIN_FUTURO")
        self.assertIsNone(resumen_sesion(eventos)["wr_hipotetico"])

    def test_rachas_solapadas_no_se_cuentan_dos_veces(self):
        datos = caso_call()
        # Otra ruptura/rechazo sobre la misma resistencia 1s después.
        # Aunque aparezca, una posición de 60 segundos está bloqueada.
        eventos = evaluar_sesion(datos)
        self.assertEqual(len(eventos), 1)

    def test_lectura_falla_con_duplicados_y_sesiones_mezcladas(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta, _ = guardar_captura_fresca(
                "USDINR-OTC", {100: vela(100), 101: vela(101)},
                100, 103, temporal
            )
            activo, datos = leer_captura(ruta)
            self.assertEqual(activo, "USDINR-OTC")
            self.assertEqual(sorted(datos), [100, 101])
            with ruta.open("a", encoding="utf-8", newline="") as archivo:
                csv.writer(archivo).writerow(
                    ["USDINR-OTC", 101, 101, 102, 100, 101,
                     "2026-10-28T00:00:00+00:00"]
                )
            with self.assertRaisesRegex(ValueError, "SESIONES_MEZCLADAS|TIMESTAMP_DUPLICADO"):
                leer_captura(ruta)

    def test_rechaza_marcas_de_captura_falsas_o_no_utc(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta, _ = guardar_captura_fresca(
                "USDINR-OTC", {100: vela(100)}, 100, 102, temporal
            )
            with ruta.open(newline="", encoding="utf-8") as archivo:
                filas = list(csv.DictReader(archivo))
                columnas = list(filas[0])
            for marca, motivo in (
                ("fecha_invalida", "MARCA_CAPTURA_INVALIDA"),
                ("2026-10-28T00:00:00", "MARCA_CAPTURA_NO_UTC"),
                ("2026-10-28T01:00:00+01:00", "MARCA_CAPTURA_NO_UTC"),
                ("2999-01-01T00:00:00+00:00", "MARCA_CAPTURA_EN_FUTURO"),
                ("1970-01-01T00:00:00+00:00", "VELA_POSTERIOR_A_CAPTURA"),
            ):
                with self.subTest(marca=marca):
                    filas[0]["capturado_en_utc"] = marca
                    with ruta.open("w", newline="", encoding="utf-8") as archivo:
                        escritor = csv.DictWriter(archivo, fieldnames=columnas)
                        escritor.writeheader()
                        escritor.writerows(filas)
                    with self.assertRaisesRegex(ValueError, motivo):
                        leer_captura(ruta)

    def test_rechaza_huecos_en_evaluacion(self):
        datos = caso_call()
        del datos[110]
        with self.assertRaisesRegex(ValueError, "HUECO_TEMPORAL"):
            evaluar_sesion(datos)


    def test_apertura_futura_evitar_win_por_cierre_no_ejecutable(self):
        datos = caso_call(102)
        # Cierre de confirmacion 101, apertura futura 110, salida 102.
        datos[123] = vela(123, open_=110, close=101, low=100, high=111)
        evento = evaluar_sesion(datos)[0]
        self.assertEqual(evento["resultado"], "LOSS")
        self.assertEqual(evento["timestamp_entrada_hipotetica"], 123)
        self.assertEqual(evento["modelo_entrada"],
                         "APERTURA_PRIMERA_VELA_FUTURA_NO_EJECUTADA")


if __name__ == "__main__":
    unittest.main()
