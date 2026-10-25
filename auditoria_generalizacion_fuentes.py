"""Diagnóstico OOS por clave de fuente principal del aprendizaje histórico.

No ajusta pesos, memoria ni autoridad. Las etiquetas de señales canceladas
se consideran contrafactuales, nunca operaciones ejecutadas.
"""

import argparse
import ast
import csv
from collections import defaultdict
from datetime import datetime, timezone

from motor_aprendizaje_historico import PRIOR_WINRATE


def _fuente(valor):
    if isinstance(valor, dict):
        return valor
    if not isinstance(valor, str) or not valor.strip():
        return {}
    try:
        dato = ast.literal_eval(valor)
    except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
        return {}
    return dato if isinstance(dato, dict) else {}


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def resumir_generalizacion_fuentes(filas):
    grupos = defaultdict(lambda: {
        "n": 0, "wins_hipoteticos": 0, "suma_prob": 0.0,
        "activos": set(), "minutos": set(), "dias": set(),
        "total_memoria": None, "winrate_memoria": None,
        "brier_modelo": 0.0, "brier_prior": 0.0,
        "brier_principal": 0.0, "n_principal": 0,
        "brier_respaldo": 0.0, "n_respaldo": 0,
    })
    descartadas = 0

    for fila in filas:
        if not isinstance(fila, dict):
            descartadas += 1
            continue
        clave = str(fila.get("clave_probabilidad_principal") or "").strip()
        resultado = str(fila.get("resultado_hipotetico") or "").strip().upper()
        prob = _numero(fila.get("probabilidad_estimada"))
        if not clave or resultado not in ("WIN", "LOSS") or prob is None or not 0 <= prob <= 100:
            descartadas += 1
            continue

        grupo = grupos[clave]
        grupo["n"] += 1
        grupo["wins_hipoteticos"] += int(resultado == "WIN")
        grupo["suma_prob"] += prob
        objetivo = int(resultado == "WIN")
        grupo["brier_modelo"] += (prob / 100.0 - objetivo) ** 2
        grupo["brier_prior"] += (PRIOR_WINRATE / 100.0 - objetivo) ** 2

        activo = str(fila.get("activo") or "").strip().upper()
        if activo:
            grupo["activos"].add(activo)

        fecha_senal = fila.get("fecha_senal")
        try:
            timestamp = float(fecha_senal)
            minuto = int(timestamp) // 60
            dia = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            pass
        else:
            grupo["minutos"].add(minuto)
            grupo["dias"].add(dia)

        fuente = _fuente(fila.get("fuente_probabilidad_principal"))
        prob_principal = _numero(fuente.get("probabilidad_ajustada"))
        if prob_principal is not None and 0 <= prob_principal <= 100:
            grupo["brier_principal"] += (prob_principal / 100.0 - objetivo) ** 2
            grupo["n_principal"] += 1
        respaldo = _fuente(fila.get("fuente_probabilidad_respaldo"))
        prob_respaldo = _numero(respaldo.get("probabilidad_ajustada"))
        if prob_respaldo is not None and 0 <= prob_respaldo <= 100:
            grupo["brier_respaldo"] += (prob_respaldo / 100.0 - objetivo) ** 2
            grupo["n_respaldo"] += 1
        if fuente and grupo["total_memoria"] is None:
            total = _numero(fuente.get("total"))
            wr = _numero(fuente.get("winrate"))
            grupo["total_memoria"] = int(total) if total is not None and total >= 0 else None
            grupo["winrate_memoria"] = wr

    resumen = []
    for clave, datos in grupos.items():
        n = datos["n"]
        pred = datos["suma_prob"] / n
        observado = 100 * datos["wins_hipoteticos"] / n
        resumen.append({
            "clave": clave,
            "n": n,
            "wins_hipoteticos": datos["wins_hipoteticos"],
            "losses_hipoteticos": n - datos["wins_hipoteticos"],
            "pred_promedio": round(pred, 2),
            "winrate_hipotetico": round(observado, 2),
            "brecha_pp": round(observado - pred, 2),
            "brier_modelo": round(datos["brier_modelo"] / n, 5),
            "brier_prior": round(datos["brier_prior"] / n, 5),
            "brier_principal": (
                round(datos["brier_principal"] / datos["n_principal"], 5)
                if datos["n_principal"] else None
            ),
            "brier_respaldo": (
                round(datos["brier_respaldo"] / datos["n_respaldo"], 5)
                if datos["n_respaldo"] else None
            ),
            "n_principal": datos["n_principal"],
            "n_respaldo": datos["n_respaldo"],
            "muestra_memoria": datos["total_memoria"],
            "winrate_memoria": datos["winrate_memoria"],
            "activos_distintos": len(datos["activos"]),
            "minutos_distintos": len(datos["minutos"]),
            "dias_distintos": len(datos["dias"]),
        })
    return sorted(resumen, key=lambda d: (-d["n"], d["clave"])), descartadas


def imprimir_generalizacion_fuentes(filas, limite=25):
    resumen, descartadas = resumir_generalizacion_fuentes(filas)
    print("===== GENERALIZACION OOS POR FUENTE PRINCIPAL — AUDITORIA =====")
    print("WIN/LOSS de señales canceladas son HIPOTETICOS.")
    print("DESCARTADAS:", descartadas)
    for dato in resumen[:limite]:
        print(
            "N:", dato["n"],
            "| MEMORIA_N:", dato["muestra_memoria"],
            "| MEMORIA_WR:", dato["winrate_memoria"],
            "| PRED:", dato["pred_promedio"],
            "| WR_HIP:", dato["winrate_hipotetico"],
            "| BRECHA_PP:", dato["brecha_pp"],
            "| BRIER_MODELO:", dato["brier_modelo"],
            "| BRIER_PRINCIPAL:", dato["brier_principal"],
            "| BRIER_RESPALDO:", dato["brier_respaldo"],
            "| BRIER_PRIOR:", dato["brier_prior"],
            "| ACTIVOS:", dato["activos_distintos"],
            "| MINUTOS:", dato["minutos_distintos"],
            "| DIAS:", dato["dias_distintos"],
            "| FUENTE:", dato["clave"],
        )


def main():
    parser = argparse.ArgumentParser(description="Auditoria por fuente principal")
    parser.add_argument("csv", help="CSV OOS; solo lectura")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        imprimir_generalizacion_fuentes(csv.DictReader(archivo))


if __name__ == "__main__":
    main()
