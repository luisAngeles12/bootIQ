"""Comprobar separación temporal TRAIN/VALIDACION antes de entrenar.

Solo lectura: verifica cortes cronológicos y duplicados de eventos; nunca
escribe memoria, importa bot.py ni autoriza operaciones.
"""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def _timestamp(valor):
    s = str(valor if valor is not None else "").strip()
    if not s:
        raise ValueError("FECHA_VACIA")
    try:
        numero = float(s)
    except ValueError:
        try:
            obj = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("FECHA_INVALIDA") from exc
        if obj.tzinfo is None:
            raise ValueError("FECHA_SIN_ZONA_HORARIA")
        numero = obj.timestamp()
    if not math.isfinite(numero) or numero <= 0:
        raise ValueError("FECHA_INVALIDA")
    return numero


def _filtrar(filas, origen, ids_globales):
    validas = []
    descartes = {}
    vistos_locales = set()
    for fila in filas:
        try:
            fecha = _timestamp(fila.get("fecha"))
        except ValueError as exc:
            clave = str(exc)
            descartes[clave] = descartes.get(clave, 0) + 1
            continue
        activo = str(fila.get("activo") or "").strip().upper()
        direccion = str(fila.get("direccion") or "").strip().upper()
        # Event identity by signal timestamp and instrument/direction.
        # Distinct signals at same second need further inspection.
        if not activo or direccion not in {"CALL", "PUT"}:
            descartes["IDENTIDAD_INCOMPLETA"] = descartes.get("IDENTIDAD_INCOMPLETA", 0) + 1
            continue
        evento = (activo, fecha, direccion)
        if evento in vistos_locales:
            descartes["EVENTO_DUPLICADO_LOCAL"] = descartes.get("EVENTO_DUPLICADO_LOCAL", 0) + 1
            continue
        vistos_locales.add(evento)
        if evento in ids_globales:
            descartes["EVENTO_COMPARTIDO_TRAIN_VALID"] = descartes.get(
                "EVENTO_COMPARTIDO_TRAIN_VALID", 0
            ) + 1
        ids_globales.add(evento)
        validas.append({"fecha": fecha, "evento": evento, "origen": origen})
    return validas, descartes


def verificar_particion(train, validacion):
    vistos = set()
    entradas_train, d_train = _filtrar(list(train), "TRAIN", vistos)
    entradas_valid, d_valid = _filtrar(list(validacion), "VALIDACION", vistos)
    t_max = max((x["fecha"] for x in entradas_train), default=None)
    v_min = min((x["fecha"] for x in entradas_valid), default=None)
    eventos_compartidos = d_valid.get("EVENTO_COMPARTIDO_TRAIN_VALID", 0)
    separacion_cronologica = (
        t_max is not None and v_min is not None and t_max < v_min
    )
    descartes = {
        "train": d_train,
        "validacion": d_valid,
    }
    integridad = (
        bool(entradas_train) and bool(entradas_valid)
        and not any(d_train.values()) and not any(d_valid.values())
    )
    apta = separacion_cronologica and integridad and eventos_compartidos == 0
    return {
        "modo": "PRECHECK_SEPARACION_SOLO_LECTURA",
        "train_validos": len(entradas_train),
        "validacion_validos": len(entradas_valid),
        "max_fecha_train_utc": (
            datetime.fromtimestamp(t_max, tz=timezone.utc).isoformat()
            if t_max is not None else None
        ),
        "min_fecha_validacion_utc": (
            datetime.fromtimestamp(v_min, tz=timezone.utc).isoformat()
            if v_min is not None else None
        ),
        "separacion_cronologica_estricta": separacion_cronologica,
        "eventos_compartidos": eventos_compartidos,
        "descartes": descartes,
        "apta_para_experimento_cronologico": apta,
        "permiso_generar_memoria_productiva": False,
        "entrenamiento_ejecutado": False,
        "operaciones_autorizadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train")
    parser.add_argument("validacion")
    args = parser.parse_args()
    with Path(args.train).open(encoding="utf-8-sig", newline="") as tf, (
        Path(args.validacion).open(encoding="utf-8-sig", newline="")
    ) as vf:
        resultado = verificar_particion(csv.DictReader(tf), csv.DictReader(vf))
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
