"""Preparar particion cronologica experimental a partir de un backtest.

No usa la asignacion TRAIN/VALIDACION por hash de activo del backtest
como sustituto de una particion temporal. Solo produce archivos
experimentales, nunca memoria del bot ni instrucciones de trading.
"""
import argparse
import csv
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from verificar_particion_train_valid_practice import _timestamp, verificar_particion


NOMBRES = ("train_cronologico.csv", "validacion_cronologica.csv")


def preparar_particion(filas, raiz=".", proporcion_train=0.70):
    if not 0.5 <= proporcion_train <= 0.85:
        raise ValueError("PROPORCION_FUERA_RANGO")
    filas = list(filas)
    if not filas:
        raise ValueError("BACKTEST_VACIO")
    columnas = list(filas[0].keys())
    if not {"fecha", "activo", "direccion", "resultado_hipotetico"}.issubset(columnas):
        raise ValueError("COLUMNAS_BACKTEST_INSUFICIENTES")

    dias = {}
    for fila in filas:
        instante = _timestamp(fila.get("fecha"))
        dia = datetime.fromtimestamp(instante, tz=timezone.utc).date().isoformat()
        dias.setdefault(dia, []).append(fila)
    fechas = sorted(dias)
    if len(fechas) < 3:
        raise ValueError("DIAS_INSUFICIENTES_MINIMO_3")
    # Fijar el corte por dias completos: evita observar una parte
    # del mismo dia en TRAIN y usar el resto como 'futuro'.
    cantidad = max(1, min(len(fechas) - 1, int(len(fechas) * proporcion_train)))
    dias_train = fechas[:cantidad]
    dias_valid = fechas[cantidad:]
    train = [fila for d in dias_train for fila in dias[d]]
    valid = [fila for d in dias_valid for fila in dias[d]]
    if len(train) < 20 or len(valid) < 20:
        raise ValueError("MUESTRA_INSUFICIENTE_MINIMO_20_POR_GRUPO")

    precheck = verificar_particion(train, valid)
    if not precheck["apta_para_experimento_cronologico"]:
        raise ValueError("PARTICION_RECHAZADA_POR_INTEGRIDAD_O_SOLAPAMIENTO")
    if any(str(f.get("resultado_hipotetico") or "").strip().upper()
           not in {"WIN", "LOSS"} for f in train):
        raise ValueError("TRAIN_SIN_ETIQUETAS_HIPOTETICAS_VALIDAS")

    base = Path(raiz).resolve() / "experimentos_fase5"
    destinos = [base / n for n in NOMBRES]
    if any(d.exists() for d in destinos):
        raise FileExistsError("SPLIT_YA_EXISTE_NO_SOBRESCRIBIR")
    base.mkdir(parents=True, exist_ok=True)
    temporales = []
    creados = []
    try:
        for bloque in (train, valid):
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="",
                suffix=".csv", prefix=".particion_", dir=str(base), delete=False
            ) as archivo:
                temporal = Path(archivo.name)
                temporales.append(temporal)
                writer = csv.DictWriter(archivo, fieldnames=columnas, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(bloque)
        for temporal, destino in zip(temporales, destinos):
            os.link(str(temporal), str(destino))
            creados.append(destino)
    except Exception:
        for destino in creados:
            destino.unlink(missing_ok=True)
        raise
    finally:
        for temporal in temporales:
            temporal.unlink(missing_ok=True)
    return {
        "estado": "PARTICION_CRONOLOGICA_EXPERIMENTAL_CREADA",
        "train": str(destinos[0]),
        "validacion": str(destinos[1]),
        "dias_train": dias_train,
        "dias_validacion": dias_valid,
        "registros_train": len(train),
        "registros_validacion": len(valid),
        "integridad": precheck,
        "datos_de_validacion_usados_para_entrenar": False,
        "memoria_productiva_modificada": False,
        "operaciones_autorizadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest", help="CSV con registros historicos etiquetados")
    parser.add_argument("--raiz", default=".")
    args = parser.parse_args()
    with Path(args.backtest).open(encoding="utf-8-sig", newline="") as f:
        resultado = preparar_particion(csv.DictReader(f), raiz=args.raiz)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
