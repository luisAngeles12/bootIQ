"""Informe consolidado, solo lectura, para la memoria V3 en PRACTICE.

No mezcla operaciones antiguas declaradas por el usuario con cierres
identificados en el CSV sin conservar la procedencia de cada grupo.
Solo evaluacion retrospectiva, nunca autoriza operaciones ni activa memoria.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from construir_memoria_ejecutadas_train_practice import _limpiar, _resumen
from evaluar_memoria_walk_forward_practice import evaluar_walk_forward


def generar_informe(filas):
    registros = list(filas)
    validos, descartes = _limpiar(registros)
    por_origen = {}
    for origen in ("CSV_MODO_PRACTICE", "USUARIO_DECLARADO_LEGADO_SIN_MODO"):
        muestra = [x for x in validos if x[3].get("_procedencia_practice_auditoria") == origen]
        por_origen[origen] = _resumen(muestra)
    wf = evaluar_walk_forward(registros)
    total = sum(d["n"] for d in por_origen.values())
    if total != len(validos):
        raise ValueError("UNIVERSOS_PROCEDENCIA_NO_CUADRAN")
    if sum(c["test"]["n"] for c in wf["cortes"]) != wf["baseline_dias_test"]["n"]:
        raise ValueError("UNIVERSO_WALK_FORWARD_NO_CUADRA")
    modos_originales = dict(sorted(Counter(
        str(f.get("modo_cuenta_configurado") or "").strip().upper() or "VACIO"
        for f in registros
    ).items()))
    return {
        "modo": "AUDITORIA_MEMORIA_V3_PRACTICE_SOLO_LECTURA",
        "total_filas_originales": len(registros),
        "modos_originales": modos_originales,
        "evaluables_total": total,
        "resumen_por_procedencia": por_origen,
        "descartes_y_procedencia": descartes,
        "evaluacion_temporal": wf,
        "advertencias": [
            "PRACTICE declarado en legado es confirmacion del usuario y no etiqueta historica del broker.",
            "Cada dia evaluado entrena exclusivamente con dias anteriores.",
            "El historial es de ordenes ejecutadas; no representa las senales rechazadas.",
            "La muestra evaluada no demuestra que un modelo sea rentable en el futuro.",
        ],
        "memoria_productiva_modificada": False,
        "autoriza_operaciones": False,
        "cambios_operativos_autorizados": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = ap.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        resultado = generar_informe(csv.DictReader(f))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
