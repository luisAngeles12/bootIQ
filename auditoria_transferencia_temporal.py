"""Auditoria pasiva de transferencia temporal entre archivos OOS.

Nunca combina WIN/LOSS hipoteticos con operaciones ejecutadas ni cambia
probabilidades, autoridad, memoria, umbrales o permisos LIVE.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

from auditoria_generalizacion_fuentes import resumir_generalizacion_fuentes


def comparar_ventanas_por_fuente(ventanas, minimo_global=20):
    """ventanas: secuencia (nombre, filas) de evaluaciones distintas.

    Las fuentes se comparan por clave exacta. Un resultado de un archivo
    nunca es utilizado para recalibrar predicciones del mismo archivo.
    """
    nombres = set()
    grupos = defaultdict(dict)
    rechazadas = {}
    for nombre, filas in ventanas:
        nombre = str(nombre).strip()
        if not nombre or nombre in nombres:
            raise ValueError("Cada ventana debe tener un nombre distinto y no vacio")
        nombres.add(nombre)
        resumen, descartadas = resumir_generalizacion_fuentes(filas)
        rechazadas[nombre] = descartadas
        for item in resumen:
            grupos[item["clave"]][nombre] = {
                "n": item["n"],
                "wins_hipoteticos": item["wins_hipoteticos"],
                "probabilidad_promedio": item["pred_promedio"],
                "winrate_hipotetico": item["winrate_hipotetico"],
                "brecha_pp": item["brecha_pp"],
                "brier_modelo": item["brier_modelo"],
                "brier_prior": item["brier_prior"],
                "activos_distintos": item["activos_distintos"],
                "dias_distintos": item["dias_distintos"],
            }

    resultados = []
    for clave, periodos in grupos.items():
        if len(periodos) < 2 or sum(p["n"] for p in periodos.values()) < minimo_global:
            continue
        brechas = [p["brecha_pp"] for p in periodos.values()]
        resultados.append({
            "clave": clave,
            "ventanas": dict(sorted(periodos.items())),
            "n_total": sum(p["n"] for p in periodos.values()),
            "rango_brecha_pp": round(max(brechas) - min(brechas), 2),
            "dias_totales": sum(p["dias_distintos"] for p in periodos.values()),
        })
    return sorted(resultados, key=lambda x: (-x["n_total"], x["clave"])), rechazadas


def main():
    parser = argparse.ArgumentParser(
        description="Transferencia por fuente: archivos OOS distintos, solo lectura"
    )
    parser.add_argument("csv", nargs="+", help="CSV por ventana, al menos dos")
    parser.add_argument("--minimo-global", type=int, default=20)
    parser.add_argument("--limite", type=int, default=20)
    args = parser.parse_args()
    if len(args.csv) < 2:
        parser.error("Se requieren dos o mas ventanas")

    ventanas = []
    for ruta in args.csv:
        with open(ruta, encoding="utf-8-sig", newline="") as archivo:
            ventanas.append((Path(ruta).name, list(csv.DictReader(archivo))))
    comparaciones, descartadas = comparar_ventanas_por_fuente(
        ventanas, minimo_global=args.minimo_global
    )
    print("===== TRANSFERENCIA TEMPORAL DE FUENTES — SOLO AUDITORIA =====")
    print("Las canceladas tienen resultados HIPOTETICOS.")
    print("DESCARTADAS:", descartadas)
    for dato in comparaciones[:args.limite]:
        print("FUENTE:", dato["clave"], "| N_TOTAL:", dato["n_total"],
              "| RANGO_BRECHA_PP:", dato["rango_brecha_pp"],
              "| VENTANAS:", dato["ventanas"])


if __name__ == "__main__":
    main()
