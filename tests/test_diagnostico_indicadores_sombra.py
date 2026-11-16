"""Diagnostico de indicadores independiente de autorizaciones PRACTICE."""
import unittest

from constructor_evidencia import construir_evidencia_operacion
from diagnostico_indicadores_sombra import diagnosticar_indicadores_sombra
from motor_decision import evaluar_veto_tecnico_sombra, _num, evaluar_price_action_decision


class DiagnosticoIndicadoresSombraTest(unittest.TestCase):
    def evidencia(self, **opciones):
        senal = {
            "direccion": "call", "ema9": 101, "ema21": 100,
            "bb_superior": 105, "bb_media": 100,
            "bb_inferior": 95, "ultima_close": 102,
            "ema_alcista": True, "ema_bajista": False,
        }
        senal.update(opciones)
        return construir_evidencia_operacion(senal, {})

    def test_ema_favorable_y_bollinger_superior(self):
        e = self.evidencia()
        d = diagnosticar_indicadores_sombra(e)
        self.assertEqual(d["alineacion_ema"], "A_FAVOR")
        self.assertEqual(d["posicion_bollinger"], "MITAD_SUPERIOR")
        self.assertFalse(d["autoriza"])
        self.assertFalse(d["bloquea"])

    def test_ema_contraria_y_banda_inferior(self):
        d = diagnosticar_indicadores_sombra(
            self.evidencia(direccion="put", ultima_close=94)
        )
        self.assertEqual(d["alineacion_ema"], "EN_CONTRA")
        self.assertEqual(d["posicion_bollinger"], "BAJO_BANDA_INFERIOR")

    def test_sin_precio_no_inventa_brecha_de_bollinger(self):
        e = self.evidencia(ultima_close=None)
        self.assertIsNone(e["precio_cierre_indicadores"])
        self.assertEqual(
            diagnosticar_indicadores_sombra(e)["posicion_bollinger"],
            "SIN_DATOS",
        )

    def test_inconsistencia_de_flags_es_solo_alerta(self):
        d = diagnosticar_indicadores_sombra(
            self.evidencia(ema_alcista=False)
        )
        self.assertIn(
            "INCONSISTENCIA_EMA_ALCISTA", d["alertas_calidad"]
        )

    def test_bandas_invalidas_no_son_brecha_operativa(self):
        d = diagnosticar_indicadores_sombra(self.evidencia(
            bb_inferior=106
        ))
        self.assertIn("BOLLINGER_ORDEN_INVALIDO", d["alertas_calidad"])
        self.assertEqual(d["posicion_bollinger"], "SIN_DATOS")

    def test_bollinger_ancho_nulo_no_inventa_posicion(self):
        e = self.evidencia(
            bb_superior=100, bb_media=100, bb_inferior=100,
            ultima_close=100,
        )
        d = diagnosticar_indicadores_sombra(e)
        self.assertIn("BOLLINGER_ANCHO_NULO", d["alertas_calidad"])
        self.assertEqual(d["posicion_bollinger"], "SIN_DATOS")
        self.assertFalse(d["autoriza"])
        self.assertFalse(d["bloquea"])

    def test_rsi_cerrado_y_valido_es_diagnostico_no_operativo(self):
        for valor, esperado in (
            (20, "SOBREVENTA"),
            (30, "NEUTRO"),
            (70, "NEUTRO"),
            (80, "SOBRECOMPRA"),
        ):
            with self.subTest(rsi=valor):
                e = self.evidencia(rsi=valor)
                d = diagnosticar_indicadores_sombra(e)
                self.assertEqual(d["estado_rsi"], esperado)
                self.assertFalse(d["autoriza"])
                self.assertFalse(d["bloquea"])

    def test_rsi_ausente_no_se_convierte_en_sobreventa(self):
        e = self.evidencia()
        self.assertIsNone(e["rsi_indicador"])
        self.assertEqual(
            diagnosticar_indicadores_sombra(e)["estado_rsi"], "SIN_DATOS"
        )

    def test_rsi_invalido_se_separa_de_decision(self):
        for valor in (-1, 101):
            with self.subTest(rsi=valor):
                d = diagnosticar_indicadores_sombra(self.evidencia(rsi=valor))
                self.assertIn("RSI_FUERA_DE_RANGO", d["alertas_calidad"])
                self.assertEqual(d["estado_rsi"], "SIN_DATOS")
                self.assertFalse(d["autoriza"])
        d = diagnosticar_indicadores_sombra(self.evidencia(rsi=float("nan")))
        self.assertEqual(d["estado_rsi"], "SIN_DATOS")

    def test_conversion_numero_cerebro_rechaza_no_finitos(self):
        for valor in (float("nan"), float("inf"), float("-inf"), "NaN", "Infinity"):
            with self.subTest(valor=str(valor)):
                self.assertEqual(_num(valor, 50.0), 50.0)
        self.assertEqual(_num("63.5", 50.0), 63.5)

    def test_pa_no_propaga_nan_ni_infinito_a_ajuste(self):
        evidencia = {
            "direccion": "call",
            "pa_evidencias": [
                {"tipo": "rechazo", "direccion": "CALL",
                 "peso": float("nan"), "fuerza": float("inf"),
                 "confirmada": False},
            ],
        }
        r = evaluar_price_action_decision(evidencia)
        self.assertEqual(r["ajuste"], 0.5)
        self.assertFalse(r["ajuste"] != r["ajuste"])

    def test_evidencia_pa_duplicada_no_duplica_ajuste(self):
        observacion = {
            "tipo": "RECHAZO_CONFIRMADO", "direccion": "CALL",
            "peso": 30, "fuerza": 0.8, "confirmada": True,
        }
        simple = evaluar_price_action_decision({
            "direccion": "call", "pa_evidencias": [observacion],
        })
        doble = evaluar_price_action_decision({
            "direccion": "call", "pa_evidencias": [observacion, dict(observacion)],
        })
        self.assertEqual(simple["ajuste"], doble["ajuste"])
        self.assertEqual(doble["evidencias_validas"], 1)
        self.assertEqual(doble["evidencias_duplicadas"], 1)
        self.assertEqual(doble["total_evidencias"], 2)

    def test_pa_confirmacion_false_en_texto_no_otorga_bono(self):
        base = {
            "direccion": "call",
            "pa_evidencias": [{
                "tipo": "IMPULSO", "direccion": "CALL",
                "peso": 18, "fuerza": 0.8, "confirmada": "False",
            }],
        }
        r = evaluar_price_action_decision(base)
        self.assertEqual(r["ajuste"], 1.8)
        self.assertEqual(r["evidencias_duplicadas"], 0)

    def test_pa_distintos_hechos_se_conservan(self):
        r = evaluar_price_action_decision({
            "direccion": "call", "pa_evidencias": [
                {"tipo": "RECHAZO", "direccion": "CALL",
                 "peso": 30, "fuerza": .8, "confirmada": True},
                {"tipo": "IMPULSO", "direccion": "CALL",
                 "peso": 18, "fuerza": .8, "confirmada": True},
            ],
        })
        self.assertEqual(r["evidencias_validas"], 2)
        self.assertEqual(r["evidencias_duplicadas"], 0)

    def test_diagnostico_del_cerebro_no_agrega_vetos(self):
        e = self.evidencia()
        antes = dict(e)
        r = evaluar_veto_tecnico_sombra(e)
        self.assertEqual(e, antes)
        self.assertEqual(r["vetos_tecnicos_sombra"], [])
        self.assertFalse(r["veto_tecnico_sombra"])
        self.assertEqual(r["indicadores_sombra"]["modo"], "SHADOW_SIN_AUTORIDAD")


if __name__ == "__main__":
    unittest.main()
