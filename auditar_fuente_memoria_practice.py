"""Auditoria de aptitud del historial para una futura memoria V3 experimental.

No genera memoria, no escribe CSV y no conecta al broker.
El corte se congela antes de evaluar el dia reservado.
"""
import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

CORTE_TRAIN_INCLUSIVO = "2026-11-11"


def auditar_fuente_memoria(filas):
    ids = set()
    descartes = Counter()
    partes = {"TRAIN_HASTA_2026_11_11": [], "VALIDACION_DESDE_2026_11_12": []}
    zonas = set()
    for fila in filas:
        if not isinstance(fila, dict):
            descartes["FILA_INVALIDA"] += 1
            continue
        if str(fila.get("estado") or "").strip().upper() != "CERRADA":
            descartes["NO_CERRADA"] += 1
            continue
        if str(fila.get("estado_operacion") or "").strip().upper() != "OPERADA_DIRECTA":
            descartes["NO_DIRECTA_EJECUTADA"] += 1
            continue
        oid = str(fila.get("order_id") or "").strip()
        if not oid or oid in ids:
            descartes["ID_AUSENTE_O_DUPLICADO"] += 1
            continue
        try:
            instante = datetime.fromisoformat(str(fila.get("fecha") or "").strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            descartes["FECHA_INVALIDA"] += 1
            continue
        try:
            pnl = float(str(fila.get("resultado") or "").strip())
        except (ValueError, TypeError):
            descartes["RESULTADO_INVALIDO"] += 1
            continue
        if not math.isfinite(pnl):
            descartes["RESULTADO_INVALIDO"] += 1
            continue
        ids.add(oid)
        zonas.add("SIN_ZONA" if instante.tzinfo is None else "CON_ZONA")
        if pnl == 0:
            descartes["EMPATE"] += 1
            continue
        parte = (
            "TRAIN_HASTA_2026_11_11"
            if instante.date().isoformat() <= CORTE_TRAIN_INCLUSIVO
            else "VALIDACION_DESDE_2026_11_12"
        )
        partes[parte].append({
            "fecha": instante.isoformat(),
            "order_id": oid,
            "etiqueta_propuesta": "WIN" if pnl > 0 else "LOSS",
            "patron": str(fila.get("patron") or "").strip(),
        })

    def resumen(registros):
        wins = sum(x["etiqueta_propuesta"] == "WIN" for x in registros)
        return {
            "n": len(registros),
            "wins": wins,
            "losses": len(registros) - wins,
            "dias": sorted({x["fecha"][:10] for x in registros}),
            "patrones_distintos": len({x["patron"] for x in registros}),
        }

    mezcla_zonas = len(zonas) > 1
    train = resumen(partes["TRAIN_HASTA_2026_11_11"])
    validacion = resumen(partes["VALIDACION_DESDE_2026_11_12"])
    return {
        "modo": "AUDITORIA_FUENTE_MEMORIA_SOLO_LECTURA",
        "corte_train_inclusivo": CORTE_TRAIN_INCLUSIVO,
        "train": train,
        "validacion_reservada": validacion,
        "descartes": dict(sorted(descartes.items())),
        "formato_temporal": sorted(zonas),
        "mezcla_zonas_temporales": mezcla_zonas,
        "conversion_win_loss_propuesta_no_aplicada": True,
        "timestamp_epoch_generado": False,
        "memoria_experimental_generada": False,
        "memoria_productiva_modificada": False,
        "aprendizaje_activado": False,
        "operaciones_autorizadas": False,
        "limitaciones": [
            "La zona de las fechas sin offset no se presume.",
            "Solo tres dias: no es una validacion robusta de generalizacion.",
            "Operaciones originales ejecutadas pueden sufrir sesgo de seleccion.",
            "Los datos de VALIDACION no deben incorporarse al TRAIN.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as archivo:
        reporte = auditar_fuente_memoria(csv.DictReader(archivo))
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
