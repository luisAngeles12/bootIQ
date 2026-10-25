"""Auditoría OOS descriptiva de calibración de probabilidades en sombra.

No sustituye el resultado ejecutado por el hipotético ni recalibra el Cerebro.
Los porcentajes observados son contrafactuales para señales canceladas.
No habilita operaciones ni modifica la autoridad V3.
"""

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone


def _probabilidad(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if numero != numero or not 0.0 <= numero <= 100.0:
        return None
    return numero


def _fecha_utc(fila):
    valor = str(fila.get("fecha_senal") or fila.get("fecha") or "").strip()
    if not valor:
        return ""
    try:
        return datetime.fromtimestamp(float(valor), timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return ""


def resumir_calibracion_sombra(filas):
    grupos = defaultdict(lambda: {
        "n": 0, "wins_hipoteticos": 0, "suma_probabilidad": 0.0,
        "suma_error_cuadratico": 0.0, "dias": set(), "minutos": set(),
    })
    descartadas = 0
    for fila in filas:
        if not isinstance(fila, dict):
            descartadas += 1
            continue
        resultado = str(fila.get("resultado_hipotetico") or "").strip().upper()
        probabilidad = _probabilidad(fila.get("probabilidad_estimada"))
        if resultado not in ("WIN", "LOSS") or probabilidad is None:
            descartadas += 1
            continue
        decision = str(fila.get("decision_estadistica_sombra") or "SIN_DATOS").strip().upper()
        grupo = grupos[decision]
        y = int(resultado == "WIN")
        grupo["n"] += 1
        grupo["wins_hipoteticos"] += y
        grupo["suma_probabilidad"] += probabilidad
        grupo["suma_error_cuadratico"] += (probabilidad / 100.0 - y) ** 2
        fecha = _fecha_utc(fila)
        if fecha:
            grupo["dias"].add(fecha)
        fecha_senal = fila.get("fecha_senal")
        if fecha_senal not in ("", None):
            try:
                grupo["minutos"].add(int(float(fecha_senal)) // 60)
            except (TypeError, ValueError):
                pass

    resumen = []
    for decision, datos in grupos.items():
        n = datos["n"]
        pred = datos["suma_probabilidad"] / n
        observado = 100.0 * datos["wins_hipoteticos"] / n
        resumen.append({
            "decision_sombra": decision,
            "n": n,
            "wins_hipoteticos": datos["wins_hipoteticos"],
            "probabilidad_promedio": round(pred, 2),
            "winrate_hipotetico": round(observado, 2),
            "diferencia_pp": round(observado - pred, 2),
            "brier_hipotetico": round(datos["suma_error_cuadratico"] / n, 5),
            "dias_distintos": len(datos["dias"]),
            "minutos_distintos": len(datos["minutos"]),
        })
    return sorted(resumen, key=lambda r: (-r["n"], r["decision_sombra"])), descartadas


def imprimir_calibracion_sombra(filas):
    grupos, descartadas = resumir_calibracion_sombra(filas)
    print("===== CALIBRACION SOMBRA — SOLO AUDITORIA =====")
    print("Comparacion descriptiva, no se consideran operaciones ejecutadas.")
    print("DESCARTADAS:", descartadas)
    for g in grupos:
        print(
            "DECISION:", g["decision_sombra"],
            "| N:", g["n"],
            "| PRED:", g["probabilidad_promedio"],
            "| WR_HIP:", g["winrate_hipotetico"],
            "| DIFERENCIA_PP:", g["diferencia_pp"],
            "| BRIER_HIP:", g["brier_hipotetico"],
            "| DIAS:", g["dias_distintos"],
            "| MINUTOS:", g["minutos_distintos"],
        )


def main():
    parser = argparse.ArgumentParser(description="Auditoria de calibracion V3 sombra")
    parser.add_argument("csv", help="CSV backtest con resultados hipoteticos; solo lectura")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        imprimir_calibracion_sombra(csv.DictReader(archivo))


if __name__ == "__main__":
    main()
