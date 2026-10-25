"""Experimentos walk-forward de calibracion por fuente, SOLO SOMBRA.

La correccion candidata usa exclusivamente cierres hipoteticos de dias
anteriores. No escribe memoria, no autoriza operaciones ni altera LIVE.
Los hipoteticos no son operaciones reales.
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def comparar_calibracion_walkforward(filas, horizontes=(3, 14, 60),
                                    fuerzas=(30, 100, 300),
                                    solo_operar=False):
    por_dia = defaultdict(lambda: defaultdict(list))
    descartadas = 0
    for fila in filas:
        if not isinstance(fila, dict):
            descartadas += 1
            continue
        y = str(fila.get("resultado_hipotetico") or "").upper()
        clave = str(fila.get("clave_probabilidad_principal") or "").strip()
        try:
            p = float(fila.get("probabilidad_estimada")) / 100.0
            dia = datetime.fromtimestamp(
                float(fila.get("fecha_senal")), timezone.utc
            ).date()
        except (ValueError, TypeError, OverflowError, OSError):
            descartadas += 1
            continue
        if y not in ("WIN", "LOSS") or not clave or not 0.0 <= p <= 1.0:
            descartadas += 1
            continue
        por_dia[dia][clave].append((
            int(y == "WIN"), p, str(fila.get("decision_estadistica_sombra") or "")
        ))

    dias = sorted(por_dia)
    resultados = []
    for horizonte in horizontes:
        for fuerza in fuerzas:
            if horizonte < 1 or fuerza <= 0:
                raise ValueError("Horizonte y fuerza deben ser positivos")
            for dia in dias:
                n = 0
                brier_actual = 0.0
                brier_candidato = 0.0
                con_historia = 0
                for clave, senales in por_dia[dia].items():
                    pasadas = [
                        y for anterior in dias
                        if 0 < (dia - anterior).days <= horizonte
                        for y, _, _ in por_dia[anterior].get(clave, [])
                    ]
                    muestra = len(pasadas)
                    wins_previos = sum(pasadas)
                    for y, p, decision in senales:
                        if solo_operar and decision != "OPERAR_SOMBRA":
                            continue
                        nueva = (
                            (fuerza * p + wins_previos) / (fuerza + muestra)
                            if muestra else p
                        )
                        brier_actual += (p - y) ** 2
                        brier_candidato += (nueva - y) ** 2
                        con_historia += int(bool(muestra))
                        n += 1
                if not n:
                    continue
                resultados.append({
                    "dia": dia.isoformat(), "horizonte_dias": horizonte,
                    "fuerza": fuerza, "n": n, "con_historia": con_historia,
                    "brier_actual": round(brier_actual / n, 6),
                    "brier_candidato": round(brier_candidato / n, 6),
                    "mejora_brier": round(
                        (brier_actual - brier_candidato) / n, 6
                    ),
                })
    return resultados, descartadas


def main():
    parser = argparse.ArgumentParser(
        description="Comparacion prospectiva de calibracion OOS; no opera"
    )
    parser.add_argument("csv", nargs="+", help="CSV ordenados por fecha")
    parser.add_argument("--solo-operar", action="store_true")
    args = parser.parse_args()
    filas = []
    for ruta in args.csv:
        with open(ruta, encoding="utf-8-sig", newline="") as archivo:
            filas.extend(csv.DictReader(archivo))
    resultados, descartadas = comparar_calibracion_walkforward(
        filas, solo_operar=args.solo_operar
    )
    print("===== CALIBRACION WALK-FORWARD — SOLO AUDITORIA =====")
    print("DATOS_DESCARTADOS:", descartadas)
    for row in resultados:
        print(row)


if __name__ == "__main__":
    main()
