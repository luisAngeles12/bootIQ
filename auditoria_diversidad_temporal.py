"""Auditoría descriptiva de diversidad temporal del histórico de señales.

Los resultados hipotéticos de señales canceladas NO representan operaciones.
La cantidad de filas NO se interpreta como tamaño de muestra independiente.
No altera aprendizaje, filtros, probabilidad ni autoridad operativa.
"""

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone


def _fecha_utc(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None
    try:
        return datetime.fromtimestamp(float(texto), timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    try:
        fecha = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def analizar_diversidad(filas):
    grupos = defaultdict(lambda: {
        "total": 0,
        "wins_hipoteticos": 0,
        "losses_hipoteticos": 0,
        "dias": Counter(),
        "minutos": set(),
        "activos": set(),
        "sin_fecha": 0,
    })
    descartadas = 0

    for fila in filas:
        if not isinstance(fila, dict):
            descartadas += 1
            continue
        clave = tuple(str(fila.get(k) or "").strip().upper()
                      for k in ("patron", "tipo_mercado", "direccion"))
        if not all(clave):
            descartadas += 1
            continue
        datos = grupos[clave]
        datos["total"] += 1
        resultado = str(fila.get("resultado_hipotetico") or "").strip().upper()
        if resultado == "WIN":
            datos["wins_hipoteticos"] += 1
        elif resultado == "LOSS":
            datos["losses_hipoteticos"] += 1

        activo = str(fila.get("activo") or "").strip().upper()
        if activo:
            datos["activos"].add(activo)

        fecha = _fecha_utc(fila.get("fecha_senal") or fila.get("fecha"))
        if fecha is None:
            datos["sin_fecha"] += 1
            continue
        datos["dias"][fecha.date().isoformat()] += 1
        datos["minutos"].add(int(fecha.timestamp()) // 60)

    resumen = []
    for (patron, mercado, direccion), datos in grupos.items():
        con_fecha = sum(datos["dias"].values())
        dia_dominante = datos["dias"].most_common(1)
        resumen.append({
            "patron": patron,
            "tipo_mercado": mercado,
            "direccion": direccion,
            "total": datos["total"],
            "wins_hipoteticos": datos["wins_hipoteticos"],
            "losses_hipoteticos": datos["losses_hipoteticos"],
            "dias_distintos": len(datos["dias"]),
            "minutos_distintos": len(datos["minutos"]),
            "activos_distintos": len(datos["activos"]),
            "sin_fecha": datos["sin_fecha"],
            "dia_dominante": dia_dominante[0][0] if dia_dominante else "",
            "porcentaje_dia_dominante": (
                round(100 * dia_dominante[0][1] / con_fecha, 2)
                if dia_dominante and con_fecha else None
            ),
        })
    return sorted(resumen, key=lambda x: (-x["total"], x["patron"])), descartadas


def imprimir_diversidad(filas, limite=30):
    grupos, descartadas = analizar_diversidad(filas)
    print("===== DIVERSIDAD TEMPORAL DE ESTRATEGIAS — SOLO AUDITORIA =====")
    print("Los WIN/LOSS son HIPOTETICOS; filas correlacionadas no son independientes.")
    print("DESCARTADAS_SIN_CONTEXTO:", descartadas)
    for grupo in grupos[:limite]:
        print(
            "N:", grupo["total"],
            "| DIAS:", grupo["dias_distintos"],
            "| MINUTOS:", grupo["minutos_distintos"],
            "| ACTIVOS:", grupo["activos_distintos"],
            "| DIA_DOMINANTE:", grupo["dia_dominante"],
            "| PORCENTAJE:", grupo["porcentaje_dia_dominante"],
            "| WIN_HIP:", grupo["wins_hipoteticos"],
            "| LOSS_HIP:", grupo["losses_hipoteticos"],
            "|", grupo["patron"], grupo["tipo_mercado"], grupo["direccion"],
        )


def main():
    parser = argparse.ArgumentParser(description="Diagnostico pasivo de diversidad temporal")
    parser.add_argument("csv", help="CSV historico; solo lectura")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        imprimir_diversidad(csv.DictReader(archivo))


if __name__ == "__main__":
    main()
