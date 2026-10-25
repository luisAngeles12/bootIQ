"""Auditoría pasiva de cobertura de estabilidad temporal en memoria histórica.

La ausencia de estabilidad no implica que una fuente sea mala. Este informe
solo describe cobertura por tamaño de muestra y no cambia los pesos, los
umbrales, las decisiones ni el factor legacy de estabilidad.
"""

import argparse
import csv


def _entero(valor):
    try:
        return max(0, int(float(valor)))
    except (TypeError, ValueError):
        return 0


def _verdadero(valor):
    return valor is True or str(valor or "").strip().lower() in ("true", "1", "si", "sí")


def _rango(total):
    if total < 5:
        return "0_4"
    if total < 12:
        return "5_11"
    if total < 20:
        return "12_19"
    if total < 50:
        return "20_49"
    return "50_MAS"


def resumir_cobertura_estabilidad(filas):
    resumen = {
        r: {"fuentes": 0, "estabilidad_disponible": 0,
            "sin_estabilidad": 0, "con_persistencia": 0}
        for r in ("0_4", "5_11", "12_19", "20_49", "50_MAS")
    }
    invalidas = 0
    for fila in filas:
        if not isinstance(fila, dict):
            invalidas += 1
            continue
        total = _entero(fila.get("total"))
        grupo = resumen[_rango(total)]
        grupo["fuentes"] += 1
        disponible = _verdadero(fila.get("estabilidad_disponible"))
        if disponible:
            grupo["estabilidad_disponible"] += 1
        else:
            grupo["sin_estabilidad"] += 1
        persistencia = str(fila.get("persistencia_direccion") or "").strip()
        if persistencia:
            try:
                float(persistencia)
            except ValueError:
                pass
            else:
                grupo["con_persistencia"] += 1
    return resumen, invalidas


def imprimir_cobertura_estabilidad(filas):
    resumen, invalidas = resumir_cobertura_estabilidad(filas)
    print("===== COBERTURA DE ESTABILIDAD MEMORIA — SOLO AUDITORIA =====")
    print("Sin estabilidad no significa LOSS; no se recalculan pesos.")
    print("FILAS_INVALIDAS:", invalidas)
    for rango, d in resumen.items():
        porcentaje = round(100 * d["estabilidad_disponible"] / d["fuentes"], 2) if d["fuentes"] else None
        print(
            "MUESTRA:", rango,
            "| FUENTES:", d["fuentes"],
            "| ESTABILIDAD:", d["estabilidad_disponible"],
            "| SIN_ESTABILIDAD:", d["sin_estabilidad"],
            "| PERSISTENCIA:", d["con_persistencia"],
            "| COBERTURA_PCT:", porcentaje,
        )


def main():
    parser = argparse.ArgumentParser(description="Auditoria de cobertura de memoria; solo lectura")
    parser.add_argument("csv", help="CSV de memoria historica")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        imprimir_cobertura_estabilidad(csv.DictReader(archivo))


if __name__ == "__main__":
    main()
