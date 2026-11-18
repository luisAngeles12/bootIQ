"""Diagnostica la ausencia de fuente V3 usando exactamente las claves oficiales.

No crea ni reescribe memorias. Solo inspecciona cierres PRACTICE; la presencia
de un match actual NO demuestra que existiera al abrir la operacion.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import motor_aprendizaje_historico as mah


def diagnosticar_cobertura_real(filas, memoria=None):
    # Nunca se genera memoria a partir de las operaciones evaluadas.
    memoria = mah.cargar_aprendizaje() if memoria is None else memoria
    if not isinstance(memoria, dict):
        raise TypeError("MEMORIA_INVALIDA")
    estados = Counter()
    por_patron = defaultdict(Counter)
    muestras_cero_historicas = Counter()
    ids = set()
    for fila in filas:
        if str(fila.get("estado") or "").upper().strip() != "CERRADA":
            estados["DESCARTE_NO_CERRADA"] += 1
            continue
        if str(fila.get("modo_cuenta_configurado") or "").upper().strip() != "PRACTICE":
            estados["DESCARTE_NO_PRACTICE"] += 1
            continue
        oid = str(fila.get("order_id") or "").strip()
        if not oid or oid in ids:
            estados["DESCARTE_ID_INVALIDO_O_DUPLICADO"] += 1
            continue
        ids.add(oid)
        # Clasificacion sobre la foto ACTUAL de la memoria, no retrospectiva.
        claves = mah._claves_jerarquicas(fila)
        permitidas = []
        for item in claves:
            clave = item.get("clave")
            if not clave:
                continue
            if (str(fila.get("direccion") or "").upper().strip() == "PUT"
                    and clave in mah.FUENTES_SIN_AUTORIDAD_PRODUCTIVA_PUT):
                continue
            permitidas.append(item)
        presentes = [item for item in permitidas if item["clave"] in memoria]
        suficientes = [
            {"nivel": item["nivel"], "clave": item["clave"],
             "total": memoria[item["clave"]].get("total", 0)}
            for item in presentes
            if int(memoria[item["clave"]].get("total") or 0) >= mah.MIN_MUESTRA_APORTE
        ]
        principal = mah._seleccionar_fuente_principal(suficientes)
        if not memoria:
            causa = "MEMORIA_VACIA_O_AUSENTE"
        elif not presentes:
            causa = "SIN_CLAVES_COINCIDENTES"
        elif not suficientes:
            causa = "CLAVES_CON_MUESTRA_INSUFICIENTE"
        elif not principal:
            causa = "FUENTES_PRESENTES_NO_ELEGIBLES"
        else:
            causa = "FUENTE_PRINCIPAL_ELEGIBLE_ACTUALMENTE"
        estados[causa] += 1
        por_patron[str(fila.get("patron") or "SIN_PATRON")][causa] += 1
        # Distinguir la decision guardada de la cobertura que existe ahora.
        if str(fila.get("muestra_probabilidad") or "").strip() == "0":
            muestras_cero_historicas[causa] += 1
    return {
        "modo": "COBERTURA_REAL_V3_SOLO_LECTURA",
        "claves_memoria_actual": len(memoria),
        "causas": dict(sorted(estados.items())),
        "por_patron": {k: dict(sorted(v.items())) for k,v in sorted(por_patron.items())},
        "muestra_v3_cero_al_abrir_por_cobertura_actual": dict(sorted(muestras_cero_historicas.items())),
        "memoria_modificada": False,
        "autorizacion_operativa": False,
        "advertencias": [
            "La memoria actual puede haberse actualizado despues de cada entrada.",
            "Las coincidencias de hoy no prueban disponibilidad en la fecha de senal.",
            "Si la memoria falta o es ilegible, diagnosticar_memoria_v3_practice.py determina su causa.",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = ap.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        print(json.dumps(diagnosticar_cobertura_real(csv.DictReader(f)),
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
