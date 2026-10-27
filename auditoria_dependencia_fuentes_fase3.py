"""Chequeo pasivo de procedencia de fuentes principal/respaldo F3.

Demuestra inclusión estructural en pares compatibles CONTEXTO_* -> FAMILIA_DIRECCION.
No identifica cada observación histórica ni cuantifica otros cruces.
Compara solo las estadísticas archivadas y nunca cambia el Cerebro.
"""
import ast
import csv
import json
from collections import Counter


def _fuente(valor):
    if isinstance(valor, dict):
        return valor
    if not isinstance(valor, str) or not valor.strip():
        return {}
    try:
        obj = ast.literal_eval(valor)
    except (SyntaxError, ValueError, MemoryError, RecursionError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _conteos(fuente):
    try:
        total = int(fuente["total"])
        wins = int(fuente["wins"])
        losses = int(fuente["losses"])
        if min(total, wins, losses) < 0 or wins + losses != total:
            return None
        return total, wins, losses
    except (KeyError, ValueError, TypeError, OverflowError):
        return None


def _subconjunto_demostrable(principal, respaldo):
    """Prueba estructural, sin IDs, para CONTEXTO_* -> FAMILIA_DIRECCION.

    La generación jerárquica agrega la misma operación a ambas claves.
    Solo se reconoce cuando familia y dirección coinciden literalmente.
    """
    kp = str(principal.get("clave") or "").split("|")
    kr = str(respaldo.get("clave") or "").split("|")
    if (
        len(kp) < 3
        or len(kr) != 3
        or kp[0] not in ("CONTEXTO_SETUP", "CONTEXTO_TECNICO")
        or kr[0] != "FAMILIA_DIRECCION"
    ):
        return False
    return kp[1] == kr[2] and kp[2] == kr[1]


def auditar_dependencia_fuentes(filas):
    conteos = Counter()
    grupos = Counter()
    for fila in filas:
        if not isinstance(fila, dict):
            conteos["FILA_INVALIDA"] += 1
            continue
        p = _fuente(fila.get("fuente_probabilidad_principal"))
        r = _fuente(fila.get("fuente_probabilidad_respaldo"))
        if not p:
            conteos["SIN_PRINCIPAL"] += 1
            continue
        if not r:
            conteos["SIN_RESPALDO"] += 1
            continue
        conteos["CON_AMBAS_FUENTES"] += 1
        nivel_p = str(p.get("nivel") or "").strip().upper()
        nivel_r = str(r.get("nivel") or "").strip().upper()
        grupos[(nivel_p, nivel_r)] += 1
        cp, cr = _conteos(p), _conteos(r)
        if cp is None or cr is None:
            conteos["CONTEOS_NO_COMPARABLES"] += 1
            continue
        conteos["CONTEOS_COMPARABLES"] += 1
        if str(p.get("clave") or "") == str(r.get("clave") or ""):
            conteos["CLAVES_IGUALES"] += 1
        if cp == cr:
            conteos["CONTADORES_WIN_LOSS_IDENTICOS"] += 1
        if _subconjunto_demostrable(p, r):
            conteos["SUBCONJUNTO_ESTRUCTURAL_DEMOSTRADO"] += 1
            if cp[0] > cr[0]:
                conteos["ANOMALIA_CONTEOS_SUBCONJUNTO"] += 1
        if cp[0] > cr[0]:
            conteos["PRINCIPAL_MUESTRA_MAYOR"] += 1
        elif cp[0] < cr[0]:
            conteos["RESPALDO_MUESTRA_MAYOR"] += 1
        else:
            conteos["MISMA_MUESTRA_NUMERICA"] += 1
    return {
        "conteos": dict(conteos),
        "pares_de_niveles": {
            p + " -> " + r: n for (p, r), n in sorted(grupos.items())
        },
        "identidades_de_observaciones_disponibles": False,
        "solapamiento_individual_verificable": False,
        "subconjunto_estructural_verificable": True,
        "autoriza_cambio": False,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    ruta = p.parse_args().csv
    with open(ruta, encoding="utf-8-sig", newline="") as stream:
        print(json.dumps(auditar_dependencia_fuentes(csv.DictReader(stream)),
                         ensure_ascii=False, indent=2, sort_keys=True))
