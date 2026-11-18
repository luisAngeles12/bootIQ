"""Telemetria de precios IQ sin red, sin reescalar y sin PII."""
import ast
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import auditoria_precio_iq_practice as audit
from auditar_entradas_bloque20_practice import _precios_iq_verificados


def eventos(oid, apertura=1.2345, cierre=1.2348):
    return {
        "option-opened": {
            "name": "option-opened",
            "msg": {"option_id": int(oid), "open_price": apertura,
                    "account_id": "NO_DEBE_PERSISTIR"},
        },
        "option-closed": {
            "name": "option-closed",
            "msg": {"option_id": int(oid), "close_price": cierre,
                    "account_id": "NO_DEBE_PERSISTIR"},
        },
        "other-data": {"token": "SECRET_NO_DEBE_PERSISTIR"},
    }


class PrecioIqAuditTests(unittest.TestCase):
    def test_extrae_solo_precio_de_la_misma_orden(self):
        txt = audit.extraer_precios_eventos("123", eventos(123))
        x = json.loads(txt)
        self.assertEqual(x["order_id"], "123")
        self.assertEqual(x["precios"]["precio_apertura_iq"], 1.2345)
        self.assertEqual(x["precios"]["precio_cierre_iq"], 1.2348)
        self.assertFalse(x["unidades_confirmadas"])
        self.assertNotIn("SECRET_NO_DEBE_PERSISTIR", txt)
        self.assertNotIn("NO_DEBE_PERSISTIR", txt)

    def test_rechaza_otro_id_malformados_no_finitos_o_valores_cero(self):
        self.assertEqual(audit.extraer_precios_eventos("124", eventos(123)), "")
        self.assertEqual(audit.extraer_precios_eventos("123", eventos(
            123, float("nan"), float("inf"))), "")
        self.assertEqual(audit.extraer_precios_eventos("123", eventos(
            123, 0, -1)), "")
        self.assertEqual(audit.extraer_precios_eventos("123", []), "")

    def test_no_fabrica_cierre_si_solo_hay_apertura(self):
        x = json.loads(audit.extraer_precios_eventos("123", {
            "option-opened": eventos(123)["option-opened"]
        }))
        self.assertEqual(x["precios"], {"precio_apertura_iq": 1.2345})

    def test_lee_cache_una_vez_y_no_llama_metodos_de_red(self):
        iq = Mock()
        iq.get_async_order.return_value = eventos(123)
        txt = audit.leer_cache_orden(iq, "123")
        self.assertTrue(txt)
        iq.get_async_order.assert_called_once_with(123)
        self.assertFalse(iq.get_position_history_v2.called)
        self.assertFalse(iq.get_order.called)
        self.assertFalse(iq.buy.called)
        iq.get_async_order.side_effect = KeyError("sin evento")
        self.assertEqual(audit.leer_cache_orden(iq, "123"), "")

    def test_reporte_muestra_sin_precio_si_no_hay_prueba(self):
        self.assertEqual(_precios_iq_verificados({
            "order_id": "123", "auditoria_orden_iq_json": ""
        }), {"estado": "SIN_PRECIO_IQ"})
        txt = audit.extraer_precios_eventos("123", eventos(123))
        x = _precios_iq_verificados({
            "order_id": "123", "auditoria_orden_iq_json": txt
        })
        self.assertEqual(x["precio_apertura_iq"], 1.2345)
        self.assertFalse(x["unidad_verificada"])
        self.assertEqual(_precios_iq_verificados({
            "order_id": "124", "auditoria_orden_iq_json": txt
        })["estado"], "PROCEDENCIA_NO_VERIFICADA")

    def test_integracion_cierre_separada_de_buy_y_con_persistencia(self):
        ruta = Path(__file__).resolve().parents[1] / "operaciones.py"
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        abrir = next(n for n in arbol.body if isinstance(n, ast.FunctionDef)
                     and n.name == "abrir_operacion")
        revisar = next(n for n in arbol.body if isinstance(n, ast.FunctionDef)
                      and n.name == "revisar_operaciones_abiertas")
        calls_abrir = [ast.unparse(n.func) for n in ast.walk(abrir)
                       if isinstance(n, ast.Call)]
        calls_revisar = [ast.unparse(n.func) for n in ast.walk(revisar)
                        if isinstance(n, ast.Call)]
        self.assertNotIn("leer_cache_orden", calls_abrir)
        self.assertIn("leer_cache_orden", calls_revisar)
        self.assertIn("actualizar_historial_cierre", calls_revisar)


if __name__ == "__main__":
    unittest.main()
