"""Pruebas de permiso bootstrap PRACTICE (sin ordenes ni red)."""
import unittest
from itertools import product
from unittest.mock import Mock, patch

import bootstrap_practice as b


def decision_sin_datos():
    return {
        "decision": "NO_OPERAR",
        "bloquear_por_riesgo": False,
        "resultado_decision_estadistica_sombra": {
            "decision": "SIN_DATOS_ESTADISTICOS",
        },
        "resultado_decision_oficial": {
            "motivo": "V3 estadistico no autorizo operacion. Sin fuente histórica principal utilizable."
        },
    }


def evidencia():
    return {
        "calidad_mercado": "NORMAL",
        "validacion_mercado_ok": True,
        "validacion_zona_sr_ok": True,
        "validacion_accion_precio_ok": True,
        "accion_precio": "CALL_ZONA_NEUTRA",
        "riesgo_estructural_critico_setup": False,
        "requiere_confirmacion_setup": False,
        "requiere_ruptura_setup": False,
        "modo_entrada_setup": "DIRECTA",
        "prioridad": 3,
    }


class BootstrapPracticeTest(unittest.TestCase):
    def test_autoriza_solo_si_es_unicamente_falta_de_memoria(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            self.assertTrue(b.habilitable_sin_memoria(evidencia(), decision_sin_datos()))

    def test_no_puede_usarse_en_real(self):
        with patch.object(b, "MODO_CUENTA", "REAL"):
            self.assertFalse(b.habilitable_sin_memoria(evidencia(), decision_sin_datos()))
            self.assertFalse(b.cuenta_practice_verificada(Mock()))

    def test_rechazos_tecnicos_siguen_bloqueados(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            for cambio in (
                {"calidad_mercado": "SUCIO"},
                {"calidad_mercado": "CAOTICO"},
                {"validacion_mercado_ok": False},
                {"validacion_zona_sr_ok": False},
                {"validacion_zona_sr_ok": None},
                {"validacion_accion_precio_ok": None},
                {"accion_precio": ""},
                {"accion_precio": "SIN_DATOS"},
                {"accion_precio": "RANGO_INVALIDO"},
                {"accion_precio": "ERROR"},
                {"accion_precio": "DIRECCION_INVALIDA"},
                {"accion_precio_requiere_pendiente": True},
                {"validacion_accion_precio_ok": False},
                {"riesgo_estructural_critico_setup": True},
                {"requiere_confirmacion_setup": True},
                {"requiere_ruptura_setup": True},
                {"modo_entrada_setup": "PROTOCOLO"},
                {"prioridad": 1},
            ):
                with self.subTest(cambio=cambio):
                    datos = evidencia()
                    datos.update(cambio)
                    self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))

    def test_pa_ausente_y_zona_sin_validar_no_autorizan_bootstrap(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            datos = evidencia()
            datos["validacion_accion_precio_ok"] = False
            self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))
            datos["validacion_accion_precio_ok"] = True
            self.assertTrue(b.habilitable_sin_memoria(datos, decision_sin_datos()))
            datos.pop("validacion_accion_precio_ok")
            self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))
            datos["validacion_accion_precio_ok"] = True
            datos.pop("validacion_zona_sr_ok")
            self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))

    def test_put_soporte_cerca_sin_ruptura_no_puede_saltarse_por_bootstrap(self):
        # Caso reproducido en bloque 2: permiso sin muestra V3 pese a PA
        # identificando soporte cercano sin ruptura para una venta.
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            datos = evidencia()
            datos.update({
                "direccion": "put",
                "accion_precio": "PUT_SOPORTE_CERCA_SIN_RUPTURA",
                "validacion_accion_precio_ok": True,
            })
            self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))
            datos["validacion_accion_precio_ok"] = None
            self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))
            # El cambio es exclusivo del riesgo probado; no veta cualquier PUT.
            datos["accion_precio"] = "RECHAZO_VENDEDOR_RESISTENCIA"
            datos["validacion_accion_precio_ok"] = True
            self.assertTrue(b.habilitable_sin_memoria(datos, decision_sin_datos()))
            datos["accion_precio"] = "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            datos["direccion"] = "call"
            self.assertTrue(b.habilitable_sin_memoria(datos, decision_sin_datos()))

    def test_call_resistencia_sin_ruptura_no_se_convierte_en_directa(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            datos = evidencia()
            datos.update({
                "direccion": "call",
                "accion_precio": "CALL_RESISTENCIA_CERCA_SIN_RUPTURA",
                "accion_precio_requiere_pendiente": None,
            })
            self.assertFalse(b.habilitable_sin_memoria(datos, decision_sin_datos()))
            datos["accion_precio"] = "RECHAZO_COMPRADOR_SOPORTE"
            self.assertTrue(b.habilitable_sin_memoria(datos, decision_sin_datos()))

    def test_matriz_2400_combinaciones_sin_bypasses(self):
        """Cruza 5 zonas, 5 PA, 3 pendientes, 8 acciones, 2 direcciones,
        2 prioridades y 2 cuentas: 4,800 casos, sin red ni broker.
        """
        zonas = (True, False, None, "True", 1)
        pa_vals = (True, False, None, "True", 1)
        pendientes = (False, True, None)
        acciones = (
            "CALL_ZONA_NEUTRA", "PUT_ZONA_NEUTRA",
            "PUT_SOPORTE_CERCA_SIN_RUPTURA",
            "CALL_RESISTENCIA_CERCA_SIN_RUPTURA",
            "SIN_DATOS", "RANGO_INVALIDO", "ERROR",
            "DIRECCION_INVALIDA",
        )
        esperado_casos = 0
        for modo in ("PRACTICE", "REAL"):
            with patch.object(b, "MODO_CUENTA", modo):
                for zona, pa_ok, pendiente, accion, direccion, prioridad in product(
                    zonas, pa_vals, pendientes, acciones,
                    ("call", "put"), (1, 3)
                ):
                    datos = evidencia()
                    datos.update({
                        "validacion_zona_sr_ok": zona,
                        "validacion_accion_precio_ok": pa_ok,
                        "accion_precio_requiere_pendiente": pendiente,
                        "accion_precio": accion, "direccion": direccion,
                        "prioridad": prioridad,
                    })
                    valido = (
                        modo == "PRACTICE"
                        and zona is True and pa_ok is True
                        and pendiente is not True and prioridad == 3
                        and accion in ("CALL_ZONA_NEUTRA", "PUT_ZONA_NEUTRA")
                    )
                    resultado = b.habilitable_sin_memoria(
                        datos, decision_sin_datos()
                    )
                    self.assertEqual(
                        resultado, valido,
                        (modo, zona, pa_ok, pendiente, accion, direccion, prioridad)
                    )
                    esperado_casos += 1
        self.assertEqual(esperado_casos, 4800)

    def test_otros_motivos_no_se_saltan(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            for cambio in (
                {"bloquear_por_riesgo": True},
                {"riesgo_compuesto": {"bloquear_por_riesgo": True, "riesgo_nivel": "ALTO"}},
                {"riesgo_compuesto": {"bloquear_por_riesgo": True, "riesgo_nivel": "EXTREMO"}},
                {"decision": "ERROR"},
                {"resultado_decision_estadistica_sombra": {"decision": "NO_OPERAR_SOMBRA"}},
                {"resultado_decision_oficial": {"motivo": "riesgo tecnico"}},
            ):
                with self.subTest(cambio=cambio):
                    decision = decision_sin_datos()
                    decision.update(cambio)
                    self.assertFalse(b.habilitable_sin_memoria(evidencia(), decision))

    def test_bootstrap_no_puede_saltarse_veto_estructural(self):
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            for nivel in ("ALTO", "EXTREMO"):
                with self.subTest(nivel=nivel):
                    decision = decision_sin_datos()
                    decision["riesgo_compuesto"] = {
                        "bloquear_por_riesgo": True,
                        "riesgo_nivel": nivel,
                    }
                    # El V3 oficial no propaga el veto estructural.
                    self.assertFalse(decision["bloquear_por_riesgo"])
                    self.assertFalse(b.habilitable_sin_memoria(evidencia(), decision))

    def test_validacion_cuenta_justo_antes_de_compra(self):
        iq = Mock()
        with patch.object(b, "MODO_CUENTA", "PRACTICE"):
            iq.get_balance_mode.return_value = "PRACTICE"
            self.assertTrue(b.cuenta_practice_verificada(iq))
            iq.get_balance_mode.return_value = "REAL"
            self.assertFalse(b.cuenta_practice_verificada(iq))
            iq.get_balance_mode.side_effect = RuntimeError("offline")
            self.assertFalse(b.cuenta_practice_verificada(iq))


if __name__ == "__main__":
    unittest.main()
