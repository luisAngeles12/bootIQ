"""Regresiones de paridad causal en sombra, sin broker ni ordenes.

La referencia causal elimina minutos que no estuvieron completos al cierre;
no confunde igualdad causal con replay historico que conoce datos tardios.
"""
import unittest

from paridad_sombra_practice import evaluar_flujo, reproducir_cierres


def crear_velas(minutos=30):
    salida = {}
    for t in range(minutos * 60):
        p = 100 + (t % 43) * 0.0001
        salida[t] = {
            "from": t, "open": p, "max": p + 0.0002,
            "min": p - 0.0001, "close": p + 0.00005,
        }
    return salida


def evaluar_paridad_causal(velas, latencias):
    if set(velas) != set(latencias):
        raise ValueError("LATENCIAS_INCOMPLETAS")
    llegadas = sorted(
        ((t + 1 + latencias[t], dict(v)) for t, v in velas.items()),
        key=lambda x: (x[0], x[1]["from"]),
    )
    flujo = evaluar_flujo(llegadas)
    elegibles = set()
    for t in velas:
        fin = (t // 60 + 1) * 60
        inicio = fin - 60
        if all(k in velas and k in latencias
               and t0 + 1 + latencias[t0] <= fin
               for t0 in range(inicio, fin) for k in (t0,)):
            elegibles.add(fin)
    referencia = reproducir_cierres({
        t: v for t, v in velas.items()
        if (t // 60 + 1) * 60 in elegibles
    })
    return flujo, referencia


class TestParidadCausal(unittest.TestCase):
    def test_sin_latencias(self):
        v = crear_velas()
        f, r = evaluar_paridad_causal(v, {t: 0 for t in v})
        self.assertEqual(f, r)
        self.assertEqual(len(f), 30)
        self.assertTrue(all(x["arbitraje"]["operable"] is False for _, x in f))

    def test_retraso_intermedio_descarta_solo_minuto_afectado(self):
        v = crear_velas()
        lat = {t: 0 for t in v}
        lat[10] = 80
        f, r = evaluar_paridad_causal(v, lat)
        self.assertEqual(f, r)
        self.assertEqual(len(f), 29)
        self.assertNotIn(60, dict(f))

    def test_dos_velas_en_segundo_de_cierre(self):
        v = crear_velas()
        lat = {t: 0 for t in v}
        lat[58] = 1
        f, r = evaluar_paridad_causal(v, lat)
        self.assertEqual(f, r)
        self.assertEqual(len(f), 30)

    def test_retrasos_multiples_no_reutilizan_contexto(self):
        v = crear_velas(50)
        lat = {t: (90 if t in (10, 1230, 2440) else 0) for t in v}
        f, r = evaluar_paridad_causal(v, lat)
        self.assertEqual(f, r)
        self.assertEqual(len(f), 47)
        self.assertTrue(all(x["arbitraje"]["operable"] is False for _, x in f))

    def test_sin_minutos_elegibles_no_hay_decisiones(self):
        v = crear_velas()
        lat = {t: 1 for t in v}
        f, r = evaluar_paridad_causal(v, lat)
        self.assertEqual(f, [])
        self.assertEqual(r, [])

    def test_falta_latencia_rechazada(self):
        v = crear_velas(1)
        with self.assertRaisesRegex(ValueError, "LATENCIAS_INCOMPLETAS"):
            evaluar_paridad_causal(v, {})


if __name__ == "__main__":
    unittest.main()
