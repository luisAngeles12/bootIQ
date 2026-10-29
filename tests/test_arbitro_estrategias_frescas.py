import unittest

from arbitro_estrategias_frescas import arbitrar_candidatos


def tres(call=False, put=False):
    return [
        {"estrategia": "RUPTURA_RETEST", "estado": "CANDIDATO_SOMBRA" if call else "SIN_SENAL",
         "direccion": "call" if call else None, "operable": False},
        {"estrategia": "RECHAZO_ZONA", "estado": "CANDIDATO_SOMBRA" if put else "SIN_SENAL",
         "direccion": "put" if put else None, "operable": False},
        {"estrategia": "CONTINUACION_TENDENCIA", "estado": "SIN_SENAL",
         "direccion": None, "operable": False},
    ]


class ArbitroEstrategiasTests(unittest.TestCase):
    def test_conflicto_call_put_nunca_autoriza_operar(self):
        r = arbitrar_candidatos(tres(call=True, put=True), "RANGO")
        self.assertEqual(r["motivo"], "CONFLICTO_DE_DIRECCIONES")
        self.assertEqual(r["estado"], "NO_OPERAR")
        self.assertIsNone(r["direccion"])
        self.assertFalse(r["operable"])

    def test_unica_estrategia_se_mantiene_sombra(self):
        r = arbitrar_candidatos(tres(call=True), "TENDENCIA_ALCISTA")
        self.assertEqual(r["estado"], "CANDIDATO_SOMBRA_NO_OPERABLE")
        self.assertEqual(r["direccion"], "call")
        self.assertFalse(r["operable"])

    def test_sucio_y_caotico_permanecen_bloqueados(self):
        for estado in ("SUCIO", "CAOTICO", "SIN_DATOS", "MIXTO"):
            with self.subTest(estado=estado):
                r = arbitrar_candidatos(tres(call=True), estado)
                self.assertEqual(r["estado"], "NO_OPERAR")

    def test_no_acepta_catalogo_parcial_duplicado_o_invalido(self):
        self.assertEqual(arbitrar_candidatos(tres()[:2], "RANGO")["motivo"],
                         "CATALOGO_INCOMPLETO")
        duplicados = tres()
        duplicados[1]["estrategia"] = "RUPTURA_RETEST"
        self.assertEqual(arbitrar_candidatos(duplicados, "RANGO")["motivo"],
                         "CATALOGO_INVALIDO")

    def test_autorizacion_inadvertida_se_bloquea(self):
        datos = tres(call=True)
        datos[0]["operable"] = True
        r = arbitrar_candidatos(datos, "TENDENCIA_ALCISTA")
        self.assertEqual(r["motivo"], "AUTORIZACION_INESPERADA")
        self.assertFalse(r["operable"])


if __name__ == "__main__":
    unittest.main()
