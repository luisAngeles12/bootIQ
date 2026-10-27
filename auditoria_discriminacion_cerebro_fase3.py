"""F3: contraste pasivo de discriminación Cerebro vs universo no autorizado.

No estima efecto causal: las cohortes no son asignadas al azar.
Señales hipotéticas no constituyen PNL ni autoridad de operación.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt

AUTORIZADAS = frozenset({"OPERAR_SOMBRA", "OPERAR_CON_PROTOCOLO_SOMBRA"})


def _dia(fila):
    try:
        return datetime.fromtimestamp(float(fila.get("fecha_senal") or fila.get("fecha")),
                                      timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _resumen(filas):
    n = len(filas)
    wins = sum(x["resultado_hipotetico"] == "WIN" for x in filas)
    return {"n": n, "wins": wins, "losses": n-wins,
            "wr": round(100*wins/n, 2) if n else None}


def _intervalo_diferencia(aut, rechaz):
    """IC normal descriptivo de diferencia de proporciones, sin causalidad."""
    n1, n0 = len(aut), len(rechaz)
    if not n1 or not n0:
        return None
    p1 = sum(f["resultado_hipotetico"] == "WIN" for f in aut)/n1
    p0 = sum(f["resultado_hipotetico"] == "WIN" for f in rechaz)/n0
    error = sqrt(p1*(1-p1)/n1 + p0*(1-p0)/n0)
    return {"diferencia_pp": round(100*(p1-p0), 2),
            "ic_95_inferior_pp": round(100*(p1-p0-1.96*error), 2),
            "ic_95_superior_pp": round(100*(p1-p0+1.96*error), 2)}


def auditar_discriminacion(filas):
    validas, omitidas, identidades = [], 0, set()
    for f in filas:
        if not isinstance(f, dict):
            omitidas += 1
            continue
        if f.get("resultado_hipotetico") not in ("WIN", "LOSS"):
            omitidas += 1
            continue
        dia = _dia(f)
        if dia is None:
            omitidas += 1
            continue
        identidad = (f.get("fecha_senal") or f.get("fecha"), f.get("activo"),
                     f.get("patron"), f.get("direccion"))
        if all(x not in (None, "") for x in identidad):
            if identidad in identidades:
                raise ValueError("Identidad de señal duplicada")
            identidades.add(identidad)
        entrada = dict(f)
        entrada["_dia_audit"] = dia
        entrada["_autorizada_audit"] = (
            str(f.get("decision_estadistica_sombra") or "").strip().upper()
            in AUTORIZADAS
        )
        validas.append(entrada)

    autorizadas = [r for r in validas if r["_autorizada_audit"]]
    rechazadas = [r for r in validas if not r["_autorizada_audit"]]
    dias = {}
    estratos = defaultdict(lambda: ([], []))
    for f in validas:
        clave = (f["_dia_audit"], str(f.get("activo") or ""))
        estratos[clave][int(f["_autorizada_audit"])].append(f)
    comparables = []
    for clave, (rech, aut) in sorted(estratos.items()):
        if rech and aut:
            p1 = _resumen(aut)["wr"]
            p0 = _resumen(rech)["wr"]
            comparables.append({"dia": clave[0], "activo": clave[1],
                                "n_autorizadas": len(aut), "n_rechazadas": len(rech),
                                "diferencia_pp": round(p1-p0, 2)})
    for dia in sorted({f["_dia_audit"] for f in validas}):
        aut = [f for f in autorizadas if f["_dia_audit"] == dia]
        rech = [f for f in rechazadas if f["_dia_audit"] == dia]
        dias[dia] = {"autorizadas": _resumen(aut),
                     "rechazadas": _resumen(rech),
                     "contraste": _intervalo_diferencia(aut, rech)}
    return {
        "universo": _resumen(validas), "autorizadas": _resumen(autorizadas),
        "rechazadas": _resumen(rechazadas),
        "diferencia_global": _intervalo_diferencia(autorizadas, rechazadas),
        "por_dia": dias, "estratos_dia_activo_comparables": len(comparables),
        "estratos_positivos": sum(x["diferencia_pp"] > 0 for x in comparables),
        "estratos_negativos": sum(x["diferencia_pp"] < 0 for x in comparables),
        "senales_omitidas": omitidas,
        "advertencia": "DESCRIPTIVO_NO_CAUSAL_RESULTADO_HIPOTETICO",
        "autoriza_cambio": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    ruta = parser.parse_args().csv
    with open(ruta, newline="", encoding="utf-8-sig") as file:
        print(json.dumps(auditar_discriminacion(csv.DictReader(file)),
                         ensure_ascii=False, indent=2, sort_keys=True))
