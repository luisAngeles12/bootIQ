"""Prueba pasiva de discriminación de probabilidades sobre datos históricos.

El umbral fijo 57 se declara antes de mirar el resultado del experimento.
No modifica señales, pesos, memoria ni ejecución.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt

UMBRAL = 57.0


def _fecha_dia(fila):
    try:
        return datetime.fromtimestamp(float(fila["fecha_senal"]), timezone.utc).date().isoformat()
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        return None


def _wilson(wins, n):
    if not n:
        return None
    z = 1.96
    p = wins / n
    return round(100 * (p + z*z/(2*n) - z*sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1+z*z/n), 2)


def _resumen(filas):
    n = len(filas)
    w = sum(x["resultado_hipotetico"] == "WIN" for x in filas)
    return {"n": n, "win": w, "loss": n-w,
            "wr_hipotetico": round(100*w/n, 2) if n else None,
            "wilson_inferior_95": _wilson(w, n)}


def evaluar_gate_probabilidad(filas, umbral=UMBRAL):
    if umbral != UMBRAL:
        raise ValueError("Umbral predefinido congelado en 57")
    grupos = defaultdict(list)
    invalidas = 0
    for f in filas:
        if not isinstance(f, dict) or f.get("resultado_hipotetico") not in ("WIN", "LOSS"):
            invalidas += 1
            continue
        dia = _fecha_dia(f)
        try:
            p = float(f.get("probabilidad_estimada"))
        except (TypeError, ValueError, OverflowError):
            invalidas += 1
            continue
        if dia is None or not 0 <= p <= 100:
            invalidas += 1
            continue
        grupos[dia].append((p, f))
    dias = {}
    todos, seleccionados = [], []
    for dia, entradas in sorted(grupos.items()):
        base = [f for _,f in entradas]
        elegidas = [f for p,f in entradas if p >= UMBRAL]
        dias[dia] = {"base": _resumen(base), "gate_57": _resumen(elegidas)}
        todos.extend(base)
        seleccionados.extend(elegidas)
    # Validación temporal descriptiva: umbral del percentil 90 del día anterior.
    # Las etiquetas WIN/LOSS nunca se consultan para seleccionar el umbral.
    top_prev_dia = {}
    prev_probs = None
    for dia, entradas in sorted(grupos.items()):
        if prev_probs:
            ordenadas = sorted(prev_probs)
            corte = ordenadas[int(0.9 * (len(ordenadas) - 1))]
            elegidas = [f for p, f in entradas if p >= corte]
            top_prev_dia[dia] = {
                "corte_previo_p90": round(corte, 3),
                "base": _resumen([f for _, f in entradas]),
                "seleccion": _resumen(elegidas),
            }
        prev_probs = [p for p, _ in entradas]
    futuro = [f for dia, datos in sorted(top_prev_dia.items())
              for p, f in grupos[dia]
              if p >= datos["corte_previo_p90"]]
    return {"umbral_predefinido": UMBRAL,
            "dias": dias, "base": _resumen(todos),
            "gate_57": _resumen(seleccionados),
            "seleccion_p90_dia_anterior": _resumen(futuro),
            "detalle_p90_temporal": top_prev_dia,
            "filas_invalidas": invalidas,
            "dias_ordenados": sorted(dias),
            "autoriza_operacion": False,
            "advertencia": "HISTORICO_EXPLORATORIO_NO_OOS_POSTCONGELACION"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    ruta = p.parse_args().csv
    with open(ruta, encoding="utf-8-sig", newline="") as stream:
        resultado = evaluar_gate_probabilidad(csv.DictReader(stream))
    print(json.dumps(resultado, indent=2, sort_keys=True, ensure_ascii=False))
