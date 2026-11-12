"""Audita cobertura de claves V3 con TRAIN fijo y validacion reservada.

Solo lectura. No construye CSV de aprendizaje, no conecta broker,
no cambia autorizaciones y no utiliza resultados de VALIDACION para entrenar.
"""
import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from motor_aprendizaje_historico import (
    _claves_jerarquicas,
    FUENTES_SIN_AUTORIDAD_PRODUCTIVA_PUT,
    MIN_MUESTRA_APORTE,
    MIN_MUESTRA_CONFIABLE,
    _grupo_nivel,
    _seleccionar_fuente_principal,
)

CORTE_TRAIN_INCLUSIVO = "2026-11-11"


def _registros_validos(filas):
    validos, ids, zonas = [], set(), set()
    descartes = Counter()
    for fila in filas:
        if not isinstance(fila, dict):
            descartes["FILA_INVALIDA"] += 1
            continue
        if str(fila.get("estado") or "").strip().upper() != "CERRADA":
            descartes["NO_CERRADA"] += 1
            continue
        if str(fila.get("estado_operacion") or "").strip().upper() != "OPERADA_DIRECTA":
            descartes["NO_DIRECTA"] += 1
            continue
        oid = str(fila.get("order_id") or "").strip()
        if not oid or oid in ids:
            descartes["ID_INVALIDO_O_REPETIDO"] += 1
            continue
        try:
            fecha = datetime.fromisoformat(
                str(fila.get("fecha") or "").strip().replace("Z", "+00:00")
            )
            pnl = float(str(fila.get("resultado") or "").strip())
        except (ValueError, TypeError):
            descartes["FECHA_O_RESULTADO_INVALIDO"] += 1
            continue
        if not math.isfinite(pnl):
            descartes["RESULTADO_NO_FINITO"] += 1
            continue
        ids.add(oid)
        zonas.add(fecha.tzinfo is None)
        if pnl == 0:
            descartes["EMPATE"] += 1
            continue
        validos.append((fecha, fila))
    if len(zonas) > 1:
        raise ValueError("FECHAS_MIXTAS_CON_Y_SIN_ZONA")
    return validos, dict(sorted(descartes.items()))


def _items_admisibles(fila):
    es_put = str(fila.get("direccion") or "").strip().upper() == "PUT"
    return [
        item for item in _claves_jerarquicas(fila)
        if item.get("clave")
        and not str(item.get("nivel") or "").upper().startswith("PROTOCOLO")
        and not str(item["clave"]).upper().startswith("PROTOCOLO")
        and not (es_put and item["clave"] in FUENTES_SIN_AUTORIDAD_PRODUCTIVA_PUT)
    ]


def auditar_cobertura(filas):
    validos, descartes = _registros_validos(filas)
    train = [(fecha, fila) for fecha, fila in validos
             if fecha.date().isoformat() <= CORTE_TRAIN_INCLUSIVO]
    validacion = [(fecha, fila) for fecha, fila in validos
                  if fecha.date().isoformat() > CORTE_TRAIN_INCLUSIVO]

    conteos = Counter()
    for _, fila in train:
        conteos.update(item["clave"] for item in _items_admisibles(fila))

    # Las etiquetas y los resultados de VALIDACION se ignoran por completo.
    resumen = Counter()
    patrones = {}
    grupos_principal = Counter()
    grupos_coincidentes = Counter()
    sin_principal = 0
    for _, fila in validacion:
        items = _items_admisibles(fila)
        claves = {item["clave"] for item in items}
        suficientes = [conteos[k] for k in claves if conteos[k] >= MIN_MUESTRA_APORTE]
        confiables = [conteos[k] for k in claves if conteos[k] >= MIN_MUESTRA_CONFIABLE]
        grupos_esta_senal = {
            _grupo_nivel(item["nivel"]) for item in items
            if conteos[item["clave"]] >= MIN_MUESTRA_APORTE
        }
        for grupo in grupos_esta_senal:
            grupos_coincidentes[grupo] += 1
        candidatas = [
            {"nivel": item["nivel"], "clave": item["clave"], "total": conteos[item["clave"]]}
            for item in items if conteos[item["clave"]] >= MIN_MUESTRA_APORTE
        ]
        principal = _seleccionar_fuente_principal(candidatas)
        if principal:
            grupo_principal = _grupo_nivel(principal["nivel"])
            grupos_principal[grupo_principal] += 1
        else:
            grupo_principal = "SIN_PRINCIPAL"
            sin_principal += 1
        patron = str(fila.get("patron") or "").strip() or "SIN_PATRON"
        item = patrones.setdefault(patron, {
            "n": 0, "con_fuente_minima": 0, "con_fuente_confiable": 0,
            "grupo_principal": {},
        })
        item["grupo_principal"][grupo_principal] = item["grupo_principal"].get(grupo_principal, 0) + 1
        item["n"] += 1
        resumen["evaluadas"] += 1
        if suficientes:
            item["con_fuente_minima"] += 1
            resumen["con_fuente_minima"] += 1
        if confiables:
            item["con_fuente_confiable"] += 1
            resumen["con_fuente_confiable"] += 1

    return {
        "modo": "COBERTURA_V3_PROSPECTIVA_SOLO_LECTURA",
        "corte_train_inclusivo": CORTE_TRAIN_INCLUSIVO,
        "train_n": len(train),
        "validacion_n": len(validacion),
        "claves_distintas_train": len(conteos),
        "claves_train_con_muestra_minima": sum(
            n >= MIN_MUESTRA_APORTE for n in conteos.values()
        ),
        "claves_train_con_muestra_confiable": sum(
            n >= MIN_MUESTRA_CONFIABLE for n in conteos.values()
        ),
        "minimo_muestra_aporte": MIN_MUESTRA_APORTE,
        "minimo_muestra_confiable": MIN_MUESTRA_CONFIABLE,
        "validacion_con_fuente_minima": resumen["con_fuente_minima"],
        "validacion_con_fuente_confiable": resumen["con_fuente_confiable"],
        "cobertura_por_patron": dict(sorted(patrones.items())),
        "grupos_con_alguna_coincidencia_por_senal": dict(sorted(grupos_coincidentes.items())),
        "grupo_principal_por_senal": dict(sorted(grupos_principal.items())),
        "senales_sin_fuente_principal_segun_minimos_de_grupo": sin_principal,
        "principal_calculada_solo_por_claves_y_muestra": True,
        "descartes": descartes,
        "nota": (
            "La fuente principal se calcula por grupo y n usando la funcion oficial; "
            "NO se han estimado pesos, rentabilidad, estabilidad ni autoridad "
            "productiva. El histórico ejecutado tiene sesgo de selección."
        ),
        "resultado_validacion_usado_para_entrenar": False,
        "memoria_generada": False,
        "memoria_productiva_modificada": False,
        "ordenes_autorizadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as archivo:
        reporte = auditar_cobertura(csv.DictReader(archivo))
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
