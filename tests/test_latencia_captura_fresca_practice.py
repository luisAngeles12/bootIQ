import csv
import tempfile
import unittest

from captura_fresca_practice import guardar_captura_fresca
from evaluar_captura_fresca_practice import evaluar_sesion, leer_captura, resumen_sesion


def vela(t, o=101, c=101, lo=100, hi=102):
    return {"from": t, "open": o, "close": c, "min": lo, "max": hi}


def datos():
    v = {t: vela(t) for t in range(100, 183)}
    v[120] = vela(120, 100, 99, 99, 101)
    v[121] = vela(121, 99, 101, 99, 101)
    v[122] = vela(122, 101, 101, 101, 102)
    v[182] = vela(182, 101, 102, 100, 102)
    return v


class TiempoRealistaTests(unittest.TestCase):
    def test_exportacion_incluye_retrasos_observados(self):
        with tempfile.TemporaryDirectory() as d:
            v = {100: vela(100), 101: vela(101)}
            ruta, _ = guardar_captura_fresca("USDINR-OTC", v, 100, 103,
                                             d, latencias={100: 0, 101: 17})
            with ruta.open(newline="", encoding="utf-8") as f:
                filas = list(csv.DictReader(f))
            self.assertEqual([r["latencia_primera_recepcion_s"] for r in filas],
                             ["0", "17"])
            _, cargadas = leer_captura(ruta)
            self.assertEqual(cargadas[101]["_latencia_primera_recepcion_s"], 17)

    def test_rechazo_tardio_no_se_presenta_como_tiempo_verificado(self):
        v = datos()
        for t in v:
            v[t]["_latencia_primera_recepcion_s"] = 0
        v[121]["_latencia_primera_recepcion_s"] = 17
        resumen = resumen_sesion(evaluar_sesion(v))
        self.assertEqual(resumen["detecciones_tardias"], 1)
        self.assertEqual(resumen["con_tiempo_verificado"], 0)

    def test_captura_previa_sin_columna_no_finge_latencia(self):
        resumen = resumen_sesion(evaluar_sesion(datos()))
        self.assertEqual(resumen["sin_latencia_registrada"], 1)
        self.assertEqual(resumen["con_tiempo_verificado"], 0)


    def test_un_segundo_de_demora_final_invalida_timing_entrada(self):
        v = datos()
        for t in v:
            v[t]["_latencia_primera_recepcion_s"] = 0
        v[122]["_latencia_primera_recepcion_s"] = 1
        r = evaluar_sesion(v)
        self.assertEqual(r[0]["calidad_tiempo"], "DETECCION_TARDIA")
        self.assertEqual(resumen_sesion(r)["con_tiempo_verificado"], 0)

    def test_demora_temprana_antes_de_cierre_no_invalida(self):
        v = datos()
        for t in v:
            v[t]["_latencia_primera_recepcion_s"] = 0
        v[120]["_latencia_primera_recepcion_s"] = 2
        self.assertEqual(evaluar_sesion(v)[0]["calidad_tiempo"],
                         "TIEMPO_VERIFICADO")


if __name__ == "__main__":
    unittest.main()
