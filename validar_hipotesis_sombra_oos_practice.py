"""Seleccion temporal de una hipotesis en señales RECHAZADAS, solo sombra.

Nunca equivale a una ejecucion IQ, fill o PnL. No autoriza operaciones.
El candidato se selecciona exclusivamente en TRAIN, una unica caracteristica,
y se evalua en TEST cronologico con la misma regla congelada.
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

CALIDAD = "HIPOTETICO_VELA_COMPLETA_SIN_FILL"
# Campos categóricos realmente emitidos por COLUMNAS en
# auditoria_candidatas_sombra_practice.py. Otros campos solo se
# usarán si existen en un CSV ampliado, nunca se inventan.
CAMPOS = (
    "patron", "tipo_mercado", "calidad_mercado", "accion_precio",
    "estado_tendencia", "patron_vela", "pa_tipo", "pa_direccion",
    "direccion", "direccion_tendencia", "estrategia",
    "regimen_mercado", "calidad_setup", "tipo_setup",
    "protocolo_sugerido",
)


def _metrica(items):
    n = len(items)
    w = sum(x["win"] for x in items)
    p = w / n if n else 0
    z = 1.96
    den = 1 + z*z/n if n else 1
    inferior = (
        (p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
        if n else None
    )
    return {
        "n": n, "wins": w, "losses": n-w,
        "wr_pct": round(p*100, 2) if n else None,
        "wilson_inferior_95_pct": round(inferior*100, 2) if inferior is not None else None,
        "dias": len({r["dia"] for r in items}),
    }


def _normalizar(fila, campo):
    value = str(fila.get(campo) or "").strip().upper()
    return value if value and value not in {"N/A", "SIN_DATOS", "SIN_DATO"} else None


def _extraer(rows):
    filas = list(rows)
    ids = Counter(str(x.get("id") or "").strip() for x in filas
                  if str(x.get("decision") or "").strip().upper() == "NO_OPERAR")
    elegibles, descartes = [], Counter()
    for f in filas:
        if str(f.get("decision") or "").strip().upper() != "NO_OPERAR":
            descartes["NO_RECHAZADA"] += 1
            continue
        oid = str(f.get("id") or "").strip()
        if not oid or ids[oid] != 1:
            descartes["ID_REPETIDO_O_VACIO"] += 1
            continue
        resultado = _normalizar(f, "resultado_hipotetico")
        if resultado not in {"WIN", "LOSS"} or f.get("calidad_tiempo") != CALIDAD:
            descartes["SIN_RESOLUCION_CONFIABLE"] += 1
            continue
        try:
            instante = int(str(f.get("vela_entrada_from") or ""))
            if instante <= 0:
                raise ValueError("INSTANTE_INVALIDO")
            dia = datetime.fromtimestamp(instante, timezone.utc).date().isoformat()
        except (ValueError, TypeError, OverflowError, OSError):
            descartes["INSTANTE_INVALIDO"] += 1
            continue
        direccion = _normalizar(f, "direccion")
        if direccion not in {"CALL", "PUT"}:
            descartes["DIRECCION_INVALIDA"] += 1
            continue
        feats = {k: _normalizar(f, k) for k in CAMPOS}
        elegibles.append({
            "id": oid, "ts": instante, "dia": dia,
            "win": int(resultado == "WIN"), "feats": feats,
        })
    elegibles.sort(key=lambda x: (x["ts"], x["id"]))
    return elegibles, dict(sorted(descartes.items()))


def validar(rows, minimo_train=40, minimo_test=30, minimo_dias_test=3):
    if min(minimo_train, minimo_test, minimo_dias_test) < 1:
        raise ValueError("MINIMOS_INVALIDOS")
    items, descartes = _extraer(rows)
    dias = sorted({x["dia"] for x in items})
    base = {
        "tipo": "HIPOTESIS_SOMBRA_NO_EJECUTABLE",
        "resueltos": len(items),
        "descartes": descartes,
        "dias_total": len(dias),
        "autoriza_operaciones": False,
        "pnl_broker": None,
        "rentabilidad_demostrada": False,
    }
    if len(dias) < 6:
        return {**base, "estado": "DIAS_INSUFICIENTES", "candidato": None}
    corte = dias[max(0, math.ceil(len(dias)*0.7)-1)]
    train = [x for x in items if x["dia"] <= corte]
    test = [x for x in items if x["dia"] > corte]
    grupos = defaultdict(list)
    for x in train:
        for k, v in x["feats"].items():
            if v is not None:
                grupos[k, v].append(x)
    candidatas = []
    for (k, v), grupo in sorted(grupos.items()):
        m = _metrica(grupo)
        if m["n"] < minimo_train or m["dias"] < 3 or len(grupo) == len(train):
            continue
        # Seleccion TRAIN: priorizar el intervalo inferior, no el máximo WR.
        candidatas.append((m["wilson_inferior_95_pct"], m["n"], k, v, m))
    candidatas.sort(key=lambda x: (-x[0], -x[1], x[2], x[3]))
    salida = {
        **base, "estado": "SIN_CANDIDATOS_TRAIN" if not candidatas else "HIPOTESIS_EVALUADA",
        "corte_train": corte, "baseline_train": _metrica(train),
        "baseline_test": _metrica(test), "candidatos_train": len(candidatas),
        "candidato": None,
    }
    if not candidatas:
        return salida
    _, _, campo, valor, metr_train = candidatas[0]
    elegido_test = [x for x in test if x["feats"][campo] == valor]
    metr_test = _metrica(elegido_test)
    by_day = defaultdict(list)
    for x in elegido_test:
        by_day[x["dia"]].append(x)
    dias_test = {d: _metrica(g) for d, g in sorted(by_day.items())}
    bloques = [_metrica(elegido_test[i:i+20]) for i in range(0, len(elegido_test), 20)
               if len(elegido_test[i:i+20]) == 20]
    # El OOS es una comprobacion; no permite promoción. Exigir estabilidad
    # por días, bloques de 20 y limite conservador, pero SIN PnL broker.
    consistente = (
        metr_test["n"] >= minimo_test
        and metr_test["dias"] >= minimo_dias_test
        and metr_test["wr_pct"] >= 60
        and metr_test["wilson_inferior_95_pct"] > 50
        and len(bloques) >= 2
        and all(b["wr_pct"] >= 60 for b in bloques)
        and all(m["wr_pct"] >= 60 for m in dias_test.values())
    )
    salida["candidato"] = {
        "campo": campo, "valor": valor, "train": metr_train, "test": metr_test,
        "test_por_dia": dias_test, "test_bloques_completos_20": bloques,
        "constancia_hipotetica": consistente,
        "apto_para_promocion": False,
        "requiere_validacion_prospectiva_y_fill_broker": True,
    }
    return salida


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archivo", nargs="?", default="auditoria_candidatas_sombra_practice.csv")
    args = ap.parse_args()
    with Path(args.archivo).open(encoding="utf-8-sig", newline="") as f:
        print(json.dumps(validar(csv.DictReader(f)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
