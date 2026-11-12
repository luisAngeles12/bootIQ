"""Pruebas de segmentacion PA/riesgo sin autorizacion de operaciones."""
import json
import unittest
from diagnostico_pa_riesgo_practice import analizar_pa_riesgo


def fila(i, direccion="CALL", pa="CALL", pnl=20.75, riesgo=None):
    return {
        "order_id": str(i), "estado": "CERRADA",
        "fecha": "2026-11-11 10:00:00", "direccion": direccion,
        "pa_direccion": pa, "resultado": str(pnl),
        "auditoria_riesgo_compuesto_json": (
            json.dumps({"riesgo_nivel": riesgo}) if riesgo else ""
        ),
    }


class DiagnosticoPaRiesgoPracticeTests(unittest.TestCase):
    def test_separa_alineada_contraria_neutra_y_sin_datos(self):
        filas = [
            fila(1, "CALL", "CALL", 20.75, "BAJO"),
            fila(2, "PUT", "CALL", -25, "MEDIO"),
            fila(3, "CALL", "NEUTRA", 20.75),
            fila(4, "CALL", "", -25),
        ]
        r = analizar_pa_riesgo(filas)
        grupos = {x["alineacion_pa"]: x for x in r["grupos"]}
        self.assertEqual(set(grupos), {"ALINEADA", "CONTRARIA", "NEUTRA", "SIN_DATO_PA"})
        self.assertEqual(grupos["CONTRARIA"]["losses"], 1)
        self.assertFalse(r["cambios_operativos_autorizados"])

    def test_no_confunde_snapshot_ausente_con_riesgo_bajo(self):
        r = analizar_pa_riesgo([fila(1, riesgo="BAJO"), fila(2)])
        riesgos = {x["riesgo"] for x in r["grupos"]}
        self.assertEqual(riesgos, {"BAJO", "SIN_SNAPSHOT"})

    def test_duplicados_empates_y_abiertas_no_alteran_muestra(self):
        rows = [fila(1), fila(1), fila(2, pnl=0), fila(3)]
        rows[3]["estado"] = "ABIERTA"
        r = analizar_pa_riesgo(rows)
        self.assertEqual(sum(x["n"] for x in r["grupos"]), 1)
        self.assertEqual(r["descartes"]["ID_AUSENTE_O_DUPLICADO"], 1)
        self.assertEqual(r["descartes"]["EMPATE"], 1)
        self.assertEqual(r["descartes"]["NO_CERRADA"], 1)

    def test_json_invalido_no_rompe_lectura(self):
        row = fila(1)
        row["auditoria_riesgo_compuesto_json"] = "{mal"
        r = analizar_pa_riesgo([row])
        self.assertEqual(r["grupos"][0]["riesgo"], "JSON_INVALIDO")


if __name__ == "__main__":
    unittest.main()
