"""Línea base de familias de estrategia para comparaciones posteriores.

Solo resultados hipotéticos de señales; no autoriza trading.
No atribuye la causa de las pérdidas al generador sin experimento causal.
"""
from collections import defaultdict
from datetime import datetime, timezone


def _dia(fila):
    raw = fila.get("fecha_senal") or fila.get("fecha")
    try:
        if isinstance(raw, (float, int)) or str(raw).isdigit():
            return datetime.fromtimestamp(float(raw), timezone.utc).date().isoformat()
        return str(raw)[:10] if raw else "SIN_FECHA"
    except (TypeError, ValueError, OverflowError, OSError):
        return "SIN_FECHA"


def evaluar_familias(filas, minimo_por_dia=30, meta=59.0):
    grupos = defaultdict(lambda: defaultdict(list))
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        res = fila.get("resultado_hipotetico")
        if res not in ("WIN", "LOSS"):
            continue
        familia = str(fila.get("familia_setup") or "SIN_FAMILIA")
        grupos[familia][_dia(fila)].append(res)
    resumen = {}
    for familia, dias in sorted(grupos.items()):
        detalle = []
        for dia, valores in sorted(dias.items()):
            w = valores.count("WIN")
            n = len(valores)
            detalle.append({"dia": dia, "n": n, "wins": w,
                            "losses": n-w, "wr": round(100*w/n, 2)})
        suficientes = [d for d in detalle if d["n"] >= minimo_por_dia]
        resumen[familia] = {
            "dias": detalle,
            "dias_con_muestra": len(suficientes),
            "supera_meta_en_dos_dias": len(suficientes) >= 2 and all(
                d["wr"] >= meta for d in suficientes),
            "resultado_hipotetico": True,
            "autoriza_operaciones": False,
        }
    return resumen


def main():
    """Inspección histórica únicamente. No promueve familias."""
    import argparse
    import csv
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    args = p.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        resultado = evaluar_familias(csv.DictReader(archivo),
                                     minimo_por_dia=30, meta=57.0)
    print(json.dumps(resultado, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
