import unittest
from auditoria_pullback_secuencial_f3 import _metrica, evaluar_velas


def v(i, o, c, hi, lo):
    return {"from":str(1793000000+i*60), "open":str(o),
            "close":str(c), "max":str(hi), "min":str(lo)}


class PullbackSecuencialF3Tests(unittest.TestCase):
    def test_estricto_simultaneo_es_matematicamente_imposible(self):
        for dir in ("call","put"):
            for cuerpo in (0.0, 0.01, 1.0, 10.0):
                if dir == "call":
                    o, c, hi, lo = 10, 10+cuerpo, 10+cuerpo, 10-1.3*cuerpo
                else:
                    o, c, hi, lo = 10, 10-cuerpo, 10+1.3*cuerpo, 10-cuerpo
                rechazo, impulso = _metrica(v(0,o,c,hi,lo), dir)
                self.assertFalse(rechazo and impulso)

    def test_rechazo_previo_recuperacion_impulso_siguiente(self):
        filas = [v(i,10,10,10.1,9.9) for i in range(3)]
        filas.extend([v(3,10,11,11,8),v(4,11,12,12.2,10.9),
                      v(5,12,12.5,12.6,11.9)])
        out = evaluar_velas(filas)
        self.assertEqual(out["triple_misma_vela"],0)
        self.assertEqual(len(out["eventos"]),1)
        self.assertEqual(out["eventos"][0]["resultado"],"WIN")

    def test_sin_datos_futuros_ni_huecos(self):
        filas = [v(i,10,10,10.1,9.9) for i in range(3)]
        filas.extend([v(3,10,11,11,8),v(4,11,12,12.2,10.9)])
        self.assertEqual(len(evaluar_velas(filas)["eventos"]),0)
        filas[-1]["from"]=str(1793000000+9*60)
        with self.assertRaises(ValueError):
            evaluar_velas(filas)


if __name__ == "__main__":
    unittest.main()
