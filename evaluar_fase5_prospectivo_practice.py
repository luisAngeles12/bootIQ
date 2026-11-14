"""Comparacion prospectiva descriptiva de hipotesis Fase 5, solo PRACTICE.

NO cambia autorizaciones, NO opera, NO entrena y NO selecciona ganador.
Lee exclusivamente ordenes nuevas que no esten en la referencia congelada.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

NOMBRE = "pullback alcista a EMA"
LIMPIA = "TENDENCIA_LIMPIA"
SUCIA = "TENDENCIA_SUCIA"


def evaluar(filas, baseline):
    if baseline.get("solo_practice") is not True:
        raise ValueError("Baseline sin marca solo_practice")
    ids = baseline.get("order_ids")
    if not isinstance(ids, list) or len(ids) != baseline.get("total_filas"):
        raise ValueError("Baseline inconsistente: order_ids / total_filas")
    if not all(isinstance(i, str) and i for i in ids):
        raise ValueError("Baseline con IDs vacios o invalidos")
    originales = set(ids)
    nuevos = []
    descartes = Counter()
    ids_nuevos = set()
    for f in filas:
        oid = str(f.get("order_id", "")).strip()
        if not oid:
            descartes["sin_order_id"] += 1
            continue
        if oid in originales:
            descartes["baseline"] += 1
            continue
        if oid in ids_nuevos:
            raise ValueError("ID de orden nuevo duplicado: " + oid)
        ids_nuevos.add(oid)
        if str(f.get("estado", "")).upper().strip() != "CERRADA":
            descartes["no_cerrada"] += 1
            continue
        if not str(f.get("regimen_mercado", "")).strip():
            descartes["sin_regimen"] += 1
            continue
        try:
            valor = float(f["resultado"])
        except (ValueError, TypeError, KeyError):
            descartes["resultado_invalido"] += 1
            continue
        if not (-float("inf") < valor < float("inf")):
            descartes["resultado_no_finito"] += 1
            continue
        nuevos.append((f, valor))

    def resumen(escenario):
        elegibles = []
        excluidas = []
        for f, valor in nuevos:
            pullback = str(f.get("patron", "")).strip().lower() == NOMBRE
            regimen = str(f.get("regimen_mercado", "")).strip()
            quitar = pullback and (
                (escenario == 1 and regimen == LIMPIA)
                or (escenario == 2 and regimen in (LIMPIA, SUCIA))
            )
            (excluidas if quitar else elegibles).append(valor)
        return {
            "conservadas": len(elegibles),
            "excluidas": len(excluidas),
            "ganadas": sum(v > 0 for v in elegibles),
            "perdidas": sum(v < 0 for v in elegibles),
            "empates": sum(v == 0 for v in elegibles),
            "neto_conservado": round(sum(elegibles), 2),
            "neto_excluido": round(sum(excluidas), 2),
        }

    return {
        "tipo": "EVALUACION_PROSPECTIVA_DESCRIPTIVA_PRACTICE",
        "referencia_total_filas": baseline["total_filas"],
        "ordenes_nuevas_evaluables": len(nuevos),
        "descartes": dict(descartes),
        "escenarios": {
            "original": resumen(0),
            "filtro_1": resumen(1),
            "filtro_2": resumen(2),
        },
        "estado": "SIN_DATOS_NUEVOS" if not nuevos else "DESCRIPTIVO_NO_VALIDADO",
        "advertencias": [
            "Los filtros fueron definidos con datos antiguos; nunca elegir un ganador por el neto prospectivo inicial.",
            "Las operaciones observadas proceden de la politica original; excluir entradas no simula oportunidades alternativas.",
            "Comparacion descriptiva, sin inferencia causal, independencia garantizada ni ventaja financiera demostrada.",
            "No cambiar produccion ni activar REAL a partir de este informe.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", default="auditoria_fase5_baseline.json")
    p.add_argument("--historial", default="historial_bot.csv")
    args = p.parse_args()
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    with open(args.historial, newline="", encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))
    print(json.dumps(evaluar(filas, baseline), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
