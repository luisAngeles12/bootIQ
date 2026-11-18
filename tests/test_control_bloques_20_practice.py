"""Pruebas de bloques de veinte cierres PRACTICE sin broker ni credenciales."""
import ast
import csv
import json
import tempfile
import unittest
from pathlib import Path

import control_bloques_20_practice as b


def fila(i, pnl, estado="CERRADA", modo="PRACTICE"):
    return {
        "order_id": str(i), "fecha": "2026-11-18 09:01:00",
        "estado": estado, "estado_operacion": "OPERADA_DIRECTA",
        "modo_cuenta_configurado": modo, "resultado": str(pnl),
        "activo": "EURUSD-OTC" if i % 2 else "GBPUSD-OTC",
        "patron": "CHOCH BAJISTA" if i % 2 else "PULLBACK A EMA",
        "direccion": "PUT" if i % 2 else "CALL",
        "tipo_mercado": "TENDENCIA_BAJISTA",
        "calidad_mercado": "LIMPIO", "estado_tendencia": "BAJISTA_NORMAL",
        "pa_tipo": "RECHAZO_VENDEDOR", "accion_precio": "RECHAZO",
        "rsi": "65", "ema9": "99", "ema21": "100",
        "bb_superior": "105", "bb_media": "100", "bb_inferior": "95",
        "precio_cierre_indicadores": "99",
        "origen_autoridad": "PROBABILIDAD_HISTORICA_V3",
        "protocolo_sugerido": "PROTOCOLO_CHOCH",
    }


def escribir(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Bloque20Tests(unittest.TestCase):
    def setUp(self):
        b.iniciar("PRACTICE", True)

    def test_solo_practice_y_sin_permiso_real(self):
        self.assertFalse(b.iniciar("REAL", True))
        self.assertTrue(b.admite_apertura())
        self.assertFalse(b.registrar_apertura("100"))
        self.assertFalse(b.cupo_alcanzado())
        self.assertTrue(b.iniciar("PRACTICE", True))

    def test_cupo_exactamente_20_y_prohibicion_de_21(self):
        for i in range(1, 21):
            self.assertTrue(b.admite_apertura())
            self.assertEqual(b.registrar_apertura(str(i)), i == 20)
        self.assertTrue(b.cupo_alcanzado())
        self.assertFalse(b.admite_apertura())
        with self.assertRaisesRegex(RuntimeError, "CUPO"):
            b.registrar_apertura("21")
        self.assertEqual(b.progreso()["abiertas_confirmadas_bloque"],20)

    def test_no_informa_si_una_operacion_sigue_abierta(self):
        with tempfile.TemporaryDirectory() as temp:
            for i in range(1,21):
                b.registrar_apertura(str(i))
            path = Path(temp) / "historial.csv"
            escribir(path, [fila(i, 20.75) for i in range(1,21)])
            out = Path(temp) / "reportes"
            self.assertIsNone(b.finalizar_si_corresponde(path, [object()], out))
            self.assertFalse(out.exists())
            self.assertEqual(b.progreso()["abiertas_confirmadas_bloque"],20)

    def test_reporte_20_y_todas_las_dimensiones(self):
        with tempfile.TemporaryDirectory() as temp:
            for i in range(1,21):
                b.registrar_apertura(str(i))
            path = Path(temp) / "historial.csv"
            escribir(path, [fila(i, 20.75 if i <= 12 else -25) for i in range(1,21)])
            out = Path(temp) / "reportes"
            reporte = b.finalizar_si_corresponde(path, [], out)
            self.assertEqual(reporte["estado"], "BLOQUE_20_CERRADO")
            self.assertEqual(reporte["resultado"]["total"],20)
            self.assertEqual(reporte["resultado"]["ganadas"],12)
            self.assertEqual(reporte["resultado"]["perdidas"],8)
            self.assertEqual(reporte["resultado"]["winrate_pct"],60)
            self.assertEqual(reporte["resultado"]["neto"],49)
            self.assertTrue(reporte["objetivo_60_pct_y_neto"])
            self.assertEqual(len(reporte["operaciones"]),20)
            self.assertEqual(reporte["operaciones"][0]["rsi_zona"],"60_70")
            self.assertEqual(reporte["operaciones"][0]["ema_alineacion"],
                             "EMA9_BAJO_EMA21")
            self.assertEqual(reporte["operaciones"][0]["patron"],"CHOCH BAJISTA")
            self.assertEqual(reporte["operaciones"][0]["precio_cierre_indicadores"],"99")
            self.assertEqual(reporte["operaciones"][0]["riesgo_compuesto"],"SIN_SNAPSHOT")
            self.assertEqual(reporte["operaciones"][0]["vela_senal_estructura"],"SIN_SNAPSHOT")
            for clave in ("estrategias","activos","mercados",
                          "price_action","rsi_zona","ema_alineacion",
                          "bollinger_ubicacion","autoridad","protocolo",
                          "riesgo_compuesto","vela_senal_estructura"):
                self.assertIn(clave, reporte["analisis"])
            files = list(out.glob("bloque20_*.json"))
            self.assertEqual(len(files),1)
            self.assertEqual(json.loads(files[0].read_text(encoding="utf-8"))
                             ["resultado"]["neto"],49)
            self.assertIsNone(b.finalizar_si_corresponde(path,[],out))

    def test_informe_incompleto_no_confunde_con_60(self):
        with tempfile.TemporaryDirectory() as temp:
            for i in range(1,21):
                b.registrar_apertura(str(i))
            path = Path(temp) / "historial.csv"
            escribir(path, [fila(i, 20.75) for i in range(1,20)])
            reporte = b.finalizar_si_corresponde(path, [], Path(temp)/"out")
            self.assertEqual(reporte["estado"], "INFORME_INCOMPLETO_NO_CONCLUYENTE")
            self.assertFalse(reporte["reanudacion_automatica"])
            self.assertNotIn("objetivo_60_pct_y_neto", reporte)

    def test_riesgo_y_vela_son_snapshots_no_reconstrucciones(self):
        registro = fila(1,20.75)
        registro.update({
            "auditoria_riesgo_compuesto_json": '{"riesgo_nivel":"MEDIO","riesgo_puntos":3}',
            "precio_senal_open":"100", "precio_senal_close":"102",
            "precio_senal_high":"103", "precio_senal_low":"99",
        })
        self.assertEqual(b._riesgo_guardado(registro),"MEDIO")
        self.assertEqual(b._vela_guardada(registro),"ALCISTA_CUERPO_MODERADO")
        registro["precio_senal_high"] = ""
        self.assertEqual(b._vela_guardada(registro),"SIN_SNAPSHOT")
        registro["auditoria_riesgo_compuesto_json"] = "{roto"
        self.assertEqual(b._riesgo_guardado(registro),"SNAPSHOT_INVALIDO")

    def test_duplicado_o_real_no_se_declaran_cierres_validos(self):
        rows = [fila(i,20.75) for i in range(1,21)]
        rows[4] = fila(5,20.75,modo="REAL")
        report = b.preparar_informe(rows,list(range(1,21)),"inicio")
        self.assertEqual(report["estado"],"INFORME_INCOMPLETO_NO_CONCLUYENTE")

    def test_integracion_compra_y_loop_son_guardias_reales(self):
        root = Path(__file__).resolve().parents[1]
        operaciones = (root/"operaciones.py").read_text(encoding="utf-8")
        bot = (root/"bot.py").read_text(encoding="utf-8")
        ast.parse(operaciones)
        ast.parse(bot)
        self.assertIn("if not admite_apertura():", operaciones)
        self.assertIn("registrar_apertura(order_id)", operaciones)
        self.assertIn("if cupo_bloque20():", bot)
        self.assertIn("cerrar_bloque20(", bot)
        self.assertIn("revisar_operaciones_abiertas()", bot)


if __name__ == "__main__":
    unittest.main()
