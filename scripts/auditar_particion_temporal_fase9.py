"""R9-10: partición temporal de auditoría sin crear memoria ni operar.

Acepta únicamente cierres PRACTICE explícitos con PNL no cero, fechas ISO
con zona horaria y order_id único en todo el CSV. No verifica con broker.
Si el conjunto es pequeño, inválido o tiene un corte temporal compartido,
reporta NO_APTO y no ofrece un TRAIN/OOS engañoso.
"""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scripts.auditar_historial_fase9 import _cierre_explicito, _fecha_iso, _resultado_monetario, _txt


def auditar_particion(ruta, proporcion_train=0.70, minimo_train=20, minimo_oos=20):
    if not (0 < proporcion_train < 1):
        raise ValueError("proporcion_train debe estar entre 0 y 1")
    if minimo_train < 1 or minimo_oos < 1:
        raise ValueError("los minimos deben ser positivos")

    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        reader = csv.DictReader(archivo)
        campos = set(reader.fieldnames or ())
        requeridos = {"order_id", "modo_cuenta_configurado", "estado",
                      "resultado", "fecha"}
        if not requeridos.issubset(campos):
            return {
                "estado": "NO_APTO", "causa": "COLUMNAS_FALTANTES",
                "columnas_faltantes": sorted(requeridos - campos),
                "train": 0, "oos": 0,
            }
        filas = list(reader)
    frecuencia_ids = Counter(
        str(f.get("order_id") or "").strip() for f in filas
        if str(f.get("order_id") or "").strip()
    )
    excluidas = Counter()
    admisibles = []
    for f in filas:
        oid = str(f.get("order_id") or "").strip()
        if not oid:
            excluidas["SIN_ORDER_ID"] += 1
            continue
        if frecuencia_ids[oid] != 1:
            excluidas["ORDER_ID_REPETIDO"] += 1
            continue
        if _txt(f.get("modo_cuenta_configurado")) != "PRACTICE":
            excluidas["MODO_NO_VERIFICADO_PRACTICE"] += 1
            continue
        if not _cierre_explicito(_txt(f.get("estado"))):
            excluidas["SIN_CIERRE_EXPLICITO"] += 1
            continue
        pnl_tipo = _resultado_monetario(f.get("resultado"))
        if pnl_tipo not in {"GANANCIA", "PERDIDA"}:
            excluidas["RESULTADO_NO_VALIDO_TRAIN"] += 1
            continue
        iso = _fecha_iso(f.get("fecha"))
        if iso is None:
            excluidas["SIN_FECHA_ISO"] += 1
            continue
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None or dt.utcoffset() is None:
            excluidas["FECHA_SIN_ZONA"] += 1
            continue
        admisibles.append((dt.astimezone(timezone.utc), oid, pnl_tipo))

    admisibles.sort(key=lambda x: (x[0], x[1]))
    marcas = sorted(set(f[0] for f in admisibles))
    base = {
        "filas_totales": len(filas),
        "candidatas_tras_filtros": len(admisibles),
        "fechas_utc_distintas": len(marcas),
        "exclusiones": dict(sorted(excluidas.items())),
        "train": 0, "oos": 0,
        "nota": "Solo auditoría: ningún resultado se usa para entrenar, puntuar o autorizar órdenes.",
    }
    if len(admisibles) < minimo_train + minimo_oos:
        return {**base, "estado": "NO_APTO", "causa": "MUESTRA_INSUFICIENTE"}
    if len(marcas) < 2:
        return {**base, "estado": "NO_APTO", "causa": "SIN_CORTE_TEMPORAL"}

    # Prohibido dividir dos órdenes del mismo instante UTC entre TRAIN y OOS.
    cortes = []
    for corte in marcas[:-1]:
        n_train = sum(t <= corte for t, _, _ in admisibles)
        n_oos = len(admisibles) - n_train
        if n_train >= minimo_train and n_oos >= minimo_oos:
            cortes.append((abs(n_train / len(admisibles) - proporcion_train),
                           corte, n_train, n_oos))
    if not cortes:
        return {**base, "estado": "NO_APTO", "causa": "NO_HAY_CORTE_CON_MINIMOS"}
    _, corte, n_train, n_oos = min(cortes)
    primer_oos = next(t for t, _, _ in admisibles if t > corte)
    assert corte < primer_oos and n_train + n_oos == len(admisibles)
    return {
        **base, "estado": "PRELIMINAR_NO_VERIFICADO_IQ",
        "train": n_train, "oos": n_oos,
        "fin_train_utc": corte.isoformat(),
        "inicio_oos_utc": primer_oos.isoformat(),
        "solapamiento_ids": 0,
        "corte_estricto": True,
        "observacion": "Falta contrastar order_id y cierres con IQ y separar la ventana de diseño de la validación final.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    a = parser.parse_args()
    print(json.dumps(auditar_particion(a.historial), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
