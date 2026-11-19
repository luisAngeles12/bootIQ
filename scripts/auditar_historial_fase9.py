"""R9-07: auditoría de procedencia del historial, estrictamente de solo lectura.

No llama IQ, no genera memoria y no cambia etiquetas. Cuenta estados, modos,
IDs y cronología antes de considerar entrenamiento TRAIN/OOS.
"""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


ESTADOS_NO_EJECUTADOS = {
    "HIPOTETICA", "HIPOTETICO", "ABIERTA", "PENDIENTE",
    "CANCELADA", "CANCELADO", "CANCELADA_CEREBRO",
    "CANCELADA_PROTOCOLO",
}


def _txt(valor):
    return str(valor or "").strip().upper()


def _fecha_finita(valor):
    try:
        numero = float(valor)
    except (ValueError, TypeError, OverflowError):
        return None
    return numero if math.isfinite(numero) and numero > 0 else None


def analizar_historial(ruta):
    ruta = Path(ruta)
    modos = Counter()
    estados = Counter()
    etiquetas = Counter()
    origenes = Counter()
    id_filas = defaultdict(list)
    falta_id = 0
    fechadas = 0
    posibles_candidatas = 0
    fechas_candidatas = []
    filas = 0
    marcas_candidatas = set()

    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames or []
        requeridas = {"order_id", "resultado", "estado_operacion", "fecha"}
        for registro in lector:
            filas += 1
            modo = _txt(registro.get("modo_cuenta_configurado")) or "SIN_MODO"
            estado = _txt(registro.get("estado_operacion")) or "SIN_ESTADO"
            etiqueta = _txt(registro.get("resultado")) or "SIN_RESULTADO"
            origen = _txt(registro.get("origen_autoridad")) or "SIN_AUTORIDAD"
            orden = str(registro.get("order_id") or "").strip()
            fecha = _fecha_finita(registro.get("fecha"))
            modos[modo] += 1
            estados[estado] += 1
            etiquetas[etiqueta] += 1
            origenes[origen] += 1
            fechadas += fecha is not None
            if orden:
                id_filas[orden].append((modo, estado, etiqueta))
            else:
                falta_id += 1
            if (
                orden and modo == "PRACTICE"
                and estado not in ESTADOS_NO_EJECUTADOS
                and estado not in {"", "SIN_ESTADO"}
                and etiqueta in {"WIN", "LOSS"}
            ):
                posibles_candidatas += 1
                marcas_candidatas.add(orden)
                if fecha is not None:
                    fechas_candidatas.append(fecha)

    repetidos = sum(len(grupo) > 1 for grupo in id_filas.values())
    conflictivos = sum(
        len(set(grupo)) > 1 for grupo in id_filas.values() if len(grupo) > 1
    )
    return {
        "archivo": str(ruta),
        "filas": filas,
        "columnas_requeridas_presentes": sorted(requeridas.intersection(columnas)),
        "columnas_requeridas_ausentes": sorted(requeridas.difference(columnas)),
        "modos": dict(sorted(modos.items())),
        "estados_operacion": dict(sorted(estados.items())),
        "resultados": dict(sorted(etiquetas.items())),
        "autoridades": dict(sorted(origenes.items())),
        "filas_sin_order_id": falta_id,
        "order_ids_distintos": len(id_filas),
        "order_ids_repetidos": repetidos,
        "order_ids_con_metadatos_distintos": conflictivos,
        "filas_con_fecha_numerica": fechadas,
        "filas_candidatas_preliminares_practice": posibles_candidatas,
        "ids_candidatos_distintos": len(marcas_candidatas),
        "candidatas_fechadas": len(fechas_candidatas),
        "min_fecha_candidata": min(fechas_candidatas) if fechas_candidatas else None,
        "max_fecha_candidata": max(fechas_candidatas) if fechas_candidatas else None,
        "advertencia": (
            "CANDIDATAS PRELIMINARES, NO MEMORIA: falta verificar contra IQ "
            "las órdenes y resultados, duplicados y partición temporal TRAIN/OOS."
        ),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    argumentos = parser.parse_args()
    print(json.dumps(analizar_historial(argumentos.historial),
                     indent=2, ensure_ascii=False))
