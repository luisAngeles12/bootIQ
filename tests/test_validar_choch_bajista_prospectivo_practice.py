"""Pruebas de corte prospectivo congelado CHOCH bajista."""
import unittest

from validar_choch_bajista_prospectivo_practice import evaluar_choch_prospectivo


def fila(oid, dia, pnl, patron="CHOCH bajista", pa="PUT"):
    return {
        "fecha": f"{dia}T12:{oid % 60:02d}:00",
        "order_id": str(oid),
        "estado": "CERRADA",
        "patron": patron,
        "direccion": "PUT",
        "pa_direccion": pa,
        "resultado": str(pnl),
    }


class ProspectivaChochTests(unittest.TestCase):
    def test_datos_del_descubrimiento_no_entran_en_muestra_nueva(self):
        datos = [fila(1, "2026-11-10", 20.75), fila(2, "2026-11-11", -25)]
        r = evaluar_choch_prospectivo(datos)
        self.assertEqual(r["choch_bajista"]["n"], 0)
        self.assertEqual(r["ventanas_20_choch"]["total"], 0)
        self.assertFalse(r["criterio_de_constancia_observado"])
        self.assertFalse(r["ordenes_autorizadas"])

    def test_hipotesis_fija_sin_seleccion_de_familias_por_winrate(self):
        datos = [fila(1, "2026-11-12", 20.75, patron="CHOCH alcista"),
                 fila(2, "2026-11-12", -25, patron="CHOCH bajista", pa="CALL"),
                 fila(3, "2026-11-12", 20.75, patron="CHOCH bajista")]
        r = evaluar_choch_prospectivo(datos)
        self.assertEqual(r["operaciones_nuevas_todas_familias"], 3)
        self.assertEqual(r["choch_bajista"]["n"], 2)
        self.assertEqual(r["choch_bajista_pa_alineada"]["n"], 1)
        self.assertFalse(r["memoria_productiva_modificada"])

    def test_tres_dias_favorables_no_autorizan_live(self):
        datos = [
            fila(i + 100 * d, f"2026-11-{12 + d}", 20.75)
            for d in range(3) for i in range(20)
        ]
        r = evaluar_choch_prospectivo(datos)
        self.assertTrue(r["muestra_minima_descriptiva_alcanzada"])
        self.assertTrue(r["criterio_de_constancia_observado"])
        self.assertFalse(r["evidencia_estadistica_suficiente_para_cambiar_live"])
        self.assertFalse(r["ordenes_autorizadas"])

    def test_un_bloque_de_perdidas_invalida_constancia(self):
        datos = [
            fila(i + 100 * d, f"2026-11-{12 + d}", -25 if d == 1 else 20.75)
            for d in range(3) for i in range(20)
        ]
        r = evaluar_choch_prospectivo(datos)
        self.assertGreater(r["ventanas_20_choch"]["bajo_objetivo"], 0)
        self.assertFalse(r["criterio_de_constancia_observado"])

    def test_duplicados_y_empates_no_inflan_muestra(self):
        datos = [
            fila(1, "2026-11-12", 20.75),
            fila(1, "2026-11-12", 20.75),
            fila(2, "2026-11-12", 0),
        ]
        r = evaluar_choch_prospectivo(datos)
        self.assertEqual(r["choch_bajista"]["n"], 1)
        self.assertEqual(r["descartes"]["ID_FALTANTE_O_DUPLICADO"], 1)
        self.assertEqual(r["descartes"]["EMPATE_O_NO_FINITO"], 1)


if __name__ == "__main__":
    unittest.main()
