"""Regresiones de memoria candidata basada en cierres PRACTICE."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import construir_memoria_ejecutadas_train_practice as c


def row(i, day, pnl, modo="PRACTICE", estado="CERRADA"):
    return {
        "order_id": str(i),
        "fecha": f"2026-11-{day:02d} 12:00:00",
        "estado": estado, "modo_cuenta_configurado": modo,
        "estado_operacion": "OPERADA_DIRECTA",
        "resultado": str(pnl), "direccion": "call",
        "patron": "CHOCH alcista", "tipo_mercado": "TENDENCIA_ALCISTA",
        "familia_setup": "REVERSIÓN_ESTRUCTURAL",
    }


class MemoriaCandidataTest(unittest.TestCase):
    def test_legado_usuario_declarado_solo_fechas_y_firma_conocidas(self):
        antigua = row("14463350071", 10, 20.75, modo="")
        antigua["origen_autoridad"] = "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"
        fuera = {**antigua, "order_id": "14463350072", "fecha": "2026-11-09 12:00:00"}
        sin_autoridad = {**antigua, "order_id": "14463350073",
                         "origen_autoridad": "OTRA"}
        real = {**antigua, "order_id": "14463350074", "modo_cuenta_configurado": "REAL"}
        practice = row("14463350075", 11, -25)
        validos, descartes = c._limpiar(
            [antigua, fuera, sin_autoridad, real, practice]
        )
        self.assertEqual(len(validos), 2)
        self.assertEqual(descartes["LEGADO_PRACTICE_DECLARADO_INCLUIDO"], 1)
        self.assertEqual(descartes["NO_PRACTICE"], 3)
        self.assertEqual(
            validos[0][3]["_procedencia_practice_auditoria"],
            "USUARIO_DECLARADO_LEGADO_SIN_MODO"
        )
        self.assertEqual(antigua["modo_cuenta_configurado"], "")

    def test_legado_no_acepta_order_id_corto_o_modo_real(self):
        antigua = row("14463350071", 14, 20, modo="")
        antigua["origen_autoridad"] = "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"
        invalida = {**antigua, "order_id": "1234"}
        real = {**antigua, "order_id": "14463350072",
                "modo_cuenta_configurado": "REAL"}
        validos, desc = c._limpiar([invalida, real])
        self.assertEqual(len(validos), 0)
        self.assertEqual(desc["NO_PRACTICE"], 2)

    def test_no_genera_si_no_hay_dias_independientes(self):
        r = c.preparar_candidata([row(i, 15, 20) for i in range(50)])
        self.assertEqual(r["estado"], "SIN_DIAS_INDEPENDIENTES")

    def test_excluye_real_abiertas_empates_y_duplicados(self):
        rows = [row(1, 12, 20), row(2, 12, 20, modo="REAL"),
                row(3, 12, -25, estado="ABIERTA"), row(1, 12, 20),
                row(4, 12, 0)]
        v, descartes = c._limpiar(rows)
        self.assertEqual(len(v), 0)
        self.assertEqual(descartes["ORDENES_AMBIGUAS_EXCLUIDAS"], 1)
        self.assertEqual(descartes["NO_PRACTICE"], 1)
        self.assertEqual(descartes["NO_CERRADA"], 1)
        self.assertEqual(descartes["ID_INVALIDO_O_DUPLICADO"], 1)
        self.assertEqual(descartes["EMPATE"], 1)

    def test_duplicado_con_pnl_contradictorio_no_entrena_ningun_cierre(self):
        rows = [row("000123", 10, 20.75), row("000123", 10, -25),
                row("000124", 11, 20.75)]
        v, descartes = c._limpiar(rows)
        self.assertEqual([x[1] for x in v], ["000124"])
        self.assertEqual(descartes["ORDENES_AMBIGUAS_EXCLUIDAS"], 1)

    def test_duplicado_antes_de_validacion_no_contamina_entrenamiento(self):
        rows = [row("000123", 10, 20.75),
                {**row("000123", 11, -25), "resultado": "NO_NUMERICO"},
                row("000124", 12, 20.75)]
        v, _ = c._limpiar(rows)
        self.assertEqual([x[1] for x in v], ["000124"])

    def test_entrenamiento_solo_anterior_y_resultados_convertidos(self):
        rows = []
        for day in range(10, 20):
            for k in range(10):
                rows.append(row(day*100+k, day, 20.75 if k%2 else -25))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(c.mah, "_buscar_fuentes_aprendizaje",
                              return_value=([], [])), patch.object(
                              c.mah, "_seleccionar_fuente_principal",
                              return_value=None):
                r = c.preparar_candidata(rows, carpeta=tmp)
            self.assertEqual(r["estado"], "CANDIDATA_AISLADA_CREADA")
            self.assertEqual(r["train"]["n"], 70)
            self.assertEqual(r["test_oos"]["n"], 30)
            self.assertEqual(r["cobertura_test_oos"]["con_fuente_n"], 0)
            path = Path(r["destino"])
            self.assertTrue(path.is_file())
            with path.open(encoding="utf-8-sig", newline="") as f:
                keys = list(csv.DictReader(f))
            self.assertGreater(len(keys), 0)
            self.assertEqual(
                next(x for x in keys if x["nivel"] == "FAMILIA")["total"], "70"
            )
            self.assertFalse(r["memoria_productiva_modificada"])
            self.assertFalse(r["autoriza_operaciones"])

    def test_no_sobrescribe_candidata(self):
        rows = [row(day*100+k, day, 20.75) for day in range(10,20)
                for k in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "memoria_ejecutadas_train_candidata.csv"
            existing.write_bytes(b"no sobrescribir")
            with self.assertRaisesRegex(FileExistsError, "CANDIDATA_EXISTENTE"):
                c.preparar_candidata(rows, carpeta=tmp)
            self.assertEqual(existing.read_bytes(), b"no sobrescribir")

    def test_no_entrena_con_holdout_si_cambia_su_resultado(self):
        rows = [row(day*100+k, day, 20.75 if k%2 else -25)
                for day in range(10, 20) for k in range(10)]
        changed = [dict(x) for x in rows]
        for item in changed:
            if int(item["fecha"][8:10]) >= 17:
                item["resultado"] = "-25"
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            a = c.preparar_candidata(rows, carpeta=tmp1)
            b = c.preparar_candidata(changed, carpeta=tmp2)
            self.assertEqual(Path(a["destino"]).read_bytes(),
                             Path(b["destino"]).read_bytes())
            self.assertNotEqual(a["test_oos"], b["test_oos"])


    def test_calibracion_oos_no_se_reentrena_con_resultados_test(self):
        rows = [row(day*100+k, day, 20.75 if k%2 else -25)
                for day in range(10, 20) for k in range(10)]
        def evaluacion(_senal, memoria=None):
            self.assertIsInstance(memoria, dict)
            return {
                "fuente_probabilidad_principal": {"nivel": "FAMILIA", "clave": "FAMILIA|CONTINUACION"},
                "probabilidad_estimada": 70.0, "muestra_historica": 25,
            }
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(c.mah, "evaluar_aprendizaje_historico", side_effect=evaluacion):
                resultado = c.preparar_candidata(rows, carpeta=tmp)
        self.assertEqual(resultado["calibracion_oos_solo_ejecutadas"]["n"], 30)
        self.assertEqual(resultado["hipotesis_probabilidad_oos"]["operaciones_que_superan_ambos"]["n"], 30)
        self.assertEqual(resultado["hipotesis_probabilidad_oos"]["operaciones_que_superan_ambos"]["neto"], -63.75)
        self.assertFalse(resultado["hipotesis_probabilidad_oos"]["no_autoriza_operaciones"] is False)
        self.assertFalse(resultado["calibracion_oos_solo_ejecutadas"]["mejora_brier_contra_prior"])

    def test_sin_fuente_no_inventa_calibracion(self):
        rows = [row(day*100+k, day, -25)
                for day in range(10, 20) for k in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(c.mah, "evaluar_aprendizaje_historico", return_value={
                "fuente_probabilidad_principal": None,
                "probabilidad_estimada": 49.25,
                "muestra_historica": 0,
            }):
                resultado = c.preparar_candidata(rows, carpeta=tmp)
        self.assertIsNone(resultado["calibracion_oos_solo_ejecutadas"]["brier_v3"])
        self.assertEqual(resultado["hipotesis_probabilidad_oos"]["operaciones_que_superan_ambos"]["n"], 0)
        self.assertFalse(resultado["autoriza_operaciones"])


if __name__ == "__main__":
    unittest.main()
