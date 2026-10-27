"""Experimento F3 de pullback secuencial, 100% pasivo y sin bróker.

Referencia: motor_protocolos.py _info_vela/_rechazo/_impulso/_pullback_recuperado.
El rechazo y el impulso simultáneos no pueden coexistir por definición;
la hipótesis nueva usa rechazo en la vela ANTERIOR y recuperación/impulso
en la actual. Evalúa el cierre de la vela siguiente; no crea órdenes.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path


def _metrica(vela, direccion):
    op, cl, hi, lo = (float(vela[x]) for x in ("open", "close", "max", "min"))
    if hi < max(op, cl) or lo > min(op, cl):
        raise ValueError("OHLC inválido")
    cuerpo = abs(cl-op)
    rango = max(hi-lo, 1e-8)
    mecha = lo - 0.0
    if direccion == "call":
        mecha = min(op, cl)-lo
        return cl > op and mecha >= 1.3*cuerpo, cl > op and cuerpo/rango >= 0.58
    if direccion == "put":
        mecha = hi-max(op, cl)
        return cl < op and mecha >= 1.3*cuerpo, cl < op and cuerpo/rango >= 0.58
    raise ValueError("Dirección inválida")


def _recuperado(previa, actual, direccion):
    op, cl = float(actual["open"]), float(actual["close"])
    previo = float(previa["close"])
    if direccion == "call":
        return float(actual["min"]) <= previo and cl > op
    return float(actual["max"]) >= previo and cl < op


def _wilson(w, n):
    if not n:
        return None
    p = w/n
    z = 1.96
    return round(100*(p+z*z/(2*n)-z*sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n), 2)


def _resumen(lista):
    conteos = Counter(x["resultado"] for x in lista)
    w, l = conteos["WIN"], conteos["LOSS"]
    return {"n": len(lista), "win": w, "loss": l, "empate": conteos["EMPATE"],
            "wr_hipotetico": round(100*w/(w+l), 2) if w+l else None,
            "wilson_inferior_95": _wilson(w, w+l)}


def evaluar_velas(filas, *, segundos=60):
    velas = sorted(filas, key=lambda x:int(x["from"]))
    tiempos = [int(x["from"]) for x in velas]
    if len(set(tiempos)) != len(tiempos):
        raise ValueError("Velas duplicadas")
    if any(b-a != segundos for a,b in zip(tiempos, tiempos[1:])):
        raise ValueError("Hueco temporal")
    eventos = []
    triple_original = 0
    ambiguos = 0
    for i in range(3, len(velas)-1):
        candidatas = []
        for direccion in ("call", "put"):
            anterior_rechazo, _ = _metrica(velas[i-1], direccion)
            mismo_rechazo, actual_impulso = _metrica(velas[i], direccion)
            if _recuperado(velas[i-1], velas[i], direccion) and mismo_rechazo and actual_impulso:
                triple_original += 1
            if anterior_rechazo and actual_impulso and _recuperado(velas[i-1], velas[i], direccion):
                candidatas.append(direccion)
        if len(candidatas) > 1:
            ambiguos += 1
            continue
        if not candidatas:
            continue
        d = candidatas[0]
        actual = float(velas[i]["close"])
        futuro = float(velas[i+1]["close"])
        resultado = ("EMPATE" if futuro == actual else
                     "WIN" if ((futuro>actual) == (d=="call")) else "LOSS")
        eventos.append({"direccion":d, "resultado":resultado,
                        "dia":datetime.fromtimestamp(tiempos[i], timezone.utc).date().isoformat()})
    return {"eventos":eventos, "triple_misma_vela":triple_original,
            "ambiguos":ambiguos, "velas":len(velas)}


def evaluar_directorio(directorio):
    eventos, totales, por_dia = [], Counter(), defaultdict(list)
    archivos = sorted(Path(directorio).glob("turbo_*.csv"))
    if not archivos:
        raise ValueError("No existen datasets turbo")
    for path in archivos:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            res = evaluar_velas(list(csv.DictReader(stream)))
        totales["activos"] += 1
        totales["velas"] += res["velas"]
        totales["triple_misma_vela"] += res["triple_misma_vela"]
        totales["ambiguos"] += res["ambiguos"]
        eventos.extend(res["eventos"])
        for e in res["eventos"]:
            por_dia[e["dia"]].append(e)
    return {"datasets":len(archivos), "conteos":dict(totales),
            "secuencia":_resumen(eventos),
            "por_dia":{d:_resumen(rows) for d,rows in sorted(por_dia.items())},
            "nota":"SEÑALES_DE_VELAS_NO_EQUIVALEN_A_EJECUCION_V3",
            "autoriza_operaciones":False}


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directorio")
    print(json.dumps(evaluar_directorio(p.parse_args().directorio),
                     indent=2, sort_keys=True, ensure_ascii=False))
