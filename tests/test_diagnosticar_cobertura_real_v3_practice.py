"""Cobertura oficial de memoria V3 sin tocar broker, datos ni criterios."""
import unittest
from unittest.mock import patch

import diagnosticar_cobertura_real_v3_practice as d


def fila(oid="1", muestra="0"):
    return {
        "order_id": oid,
        "estado": "CERRADA",
        "modo_cuenta_configurado": "PRACTICE",
        "direccion": "CALL",
        "patron": "CHOCH bajista",
        "muestra_probabilidad": muestra,
    }


class CoberturaRealV3Tests(unittest.TestCase):
    def test_vacia_no_equivale_a_estrategia_perdedora(self):
        r = d.diagnosticar_cobertura_real([fila()], memoria={})
        self.assertEqual(r["causas"]["MEMORIA_VACIA_O_AUSENTE"], 1)
        self.assertFalse(r["autorizacion_operativa"])

    def test_clave_ausente_y_clave_insuficiente(self):
        with patch.object(d.mah, "_claves_jerarquicas", return_value=[
            {"nivel": "FAMILIA", "clave": "FAMILIA|REVERSIÓN"}]):
            r = d.diagnosticar_cobertura_real([fila()], memoria={"OTRA": {"total": 30}})
            self.assertEqual(r["causas"]["SIN_CLAVES_COINCIDENTES"], 1)
            r = d.diagnosticar_cobertura_real([fila()], memoria={
                "FAMILIA|REVERSIÓN": {"total": 1}})
            self.assertEqual(r["causas"]["CLAVES_CON_MUESTRA_INSUFICIENTE"], 1)

    def test_elegible_sin_promover_autorizacion(self):
        with patch.object(d.mah, "_claves_jerarquicas", return_value=[
            {"nivel": "FAMILIA", "clave": "FAMILIA|REVERSIÓN"}]):
            r = d.diagnosticar_cobertura_real([fila()], memoria={
                "FAMILIA|REVERSIÓN": {"total": 30}})
            self.assertEqual(r["causas"]["FUENTE_PRINCIPAL_ELEGIBLE_ACTUALMENTE"], 1)
            self.assertEqual(
                r["muestra_v3_cero_al_abrir_por_cobertura_actual"]
                ["FUENTE_PRINCIPAL_ELEGIBLE_ACTUALMENTE"], 1)
            self.assertFalse(r["memoria_modificada"])

    def test_solo_cerradas_practice_y_order_id_unico(self):
        rows = [fila(), fila(), {**fila("2"), "estado": "ABIERTA"},
                {**fila("3"), "modo_cuenta_configurado": "REAL"}]
        r = d.diagnosticar_cobertura_real(rows, memoria={})
        self.assertEqual(r["causas"]["MEMORIA_VACIA_O_AUSENTE"], 1)
        self.assertEqual(r["causas"]["DESCARTE_ID_INVALIDO_O_DUPLICADO"], 1)
        self.assertEqual(r["causas"]["DESCARTE_NO_CERRADA"], 1)
        self.assertEqual(r["causas"]["DESCARTE_NO_PRACTICE"], 1)


if __name__ == "__main__":
    unittest.main()
