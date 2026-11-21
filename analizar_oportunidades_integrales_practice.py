"""Analiza oportunidades historicas PRACTICE sin alterar ordenes ni reglas.

Usa TRAIN cronologico para elegir UNA hipotesis, y dias posteriores para
validarla. Asociacion != causalidad; solo operaciones ejecutadas.
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from construir_memoria_ejecutadas_train_practice import _limpiar

FEATURES = ("patron", "tipo_mercado", "calidad_mercado", "regimen_mercado",
            "accion_precio", "pa_tipo", "estado_tendencia", "origen_autoridad",
            "protocolo_sugerido", "rsi_zona", "ema_direccion", "bb_ubicacion",
            "vela_senal_cuerpo", "direccion_contra_tendencia", "riesgo_nivel")


def _number(value):
    try:
        if value is None or isinstance(value, bool) or str(value).strip() == "":
            return None
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _norm(value):
    return str(value or "").strip().upper() or "SIN_DATO"


def _features(row):
    data = {k: _norm(row.get(k)) for k in FEATURES if k in row}
    rsi = _number(row.get("rsi"))
    data["rsi_zona"] = ("SIN_DATO" if rsi is None or not 0 <= rsi <= 100 else
                        "BAJO_30" if rsi < 30 else "ALTO_70" if rsi > 70 else "30_A_70")
    e9, e21 = _number(row.get("ema9")), _number(row.get("ema21"))
    data["ema_direccion"] = ("SIN_DATO" if e9 is None or e21 is None else
                              "ALCISTA" if e9 > e21 else "BAJISTA" if e9 < e21 else "IGUAL")
    lo, mid, hi, price = (_number(row.get(k)) for k in
                          ("bb_inferior", "bb_media", "bb_superior", "precio_cierre_indicadores"))
    if None in (lo, mid, hi, price) or not lo < hi or not lo <= mid <= hi:
        data["bb_ubicacion"] = "SIN_DATO"
    else:
        data["bb_ubicacion"] = ("FUERA_INFERIOR" if price < lo else
                                "FUERA_SUPERIOR" if price > hi else
                                "MITAD_INFERIOR" if price < mid else "MITAD_SUPERIOR")
    o, c, h, l = (_number(row.get(k)) for k in
                  ("precio_senal_open", "precio_senal_close", "precio_senal_high", "precio_senal_low"))
    if None in (o, c, h, l) or h <= l or not l <= min(o, c) <= max(o, c) <= h:
        data["vela_senal_cuerpo"] = "SIN_DATO"
    else:
        ratio = abs(c - o) / (h - l)
        data["vela_senal_cuerpo"] = ("DOJI" if ratio < 0.15 else
                                     "CUERPO_MEDIO" if ratio < 0.6 else "CUERPO_ALTO")
    direction, trend = _norm(row.get("direccion")), _norm(row.get("direccion_tendencia"))
    data["direccion_contra_tendencia"] = (
        "SIN_DATO" if direction not in ("CALL", "PUT") or trend not in ("ALCISTA", "BAJISTA")
        else "CONTRA" if (direction == "CALL") != (trend == "ALCISTA") else "A_FAVOR"
    )
    try:
        risk = json.loads(row.get("auditoria_riesgo_compuesto_json") or "{}")
        data["riesgo_nivel"] = _norm(risk.get("riesgo_nivel")) if isinstance(risk, dict) else "SIN_DATO"
    except (ValueError, TypeError):
        data["riesgo_nivel"] = "SIN_DATO"
    return data


def _metrics(rows):
    n = len(rows)
    wins = sum(r["pnl"] > 0 for r in rows)
    pnl = sum(r["pnl"] for r in rows)
    # Una muestra efectiva por minuto, elegida por orden temporal/ID
    # ANTES de ver el resultado; no escoger al ganador del minuto.
    minutos = {}
    for item in sorted(rows, key=lambda r: (r["fecha"], r["order_id"])):
        clave_minuto = item["fecha"].replace(second=0, microsecond=0)
        minutos.setdefault(clave_minuto, item)
    muestra_independiente = list(minutos.values())
    minutos_distintos = len(muestra_independiente)
    wins_independientes = sum(r["pnl"] > 0 for r in muestra_independiente)
    if minutos_distintos:
        p_ind = wins_independientes / minutos_distintos
        z_ind = 1.96
        den_ind = 1 + z_ind*z_ind/minutos_distintos
        limite_ind = (
            p_ind + z_ind*z_ind/(2*minutos_distintos) -
            z_ind*math.sqrt(p_ind*(1-p_ind)/minutos_distintos +
                            z_ind*z_ind/(4*minutos_distintos**2))
        ) / den_ind
    else:
        p_ind, limite_ind = None, None
    if n:
        z = 1.96
        p = wins / n
        d = 1 + z*z/n
        lower = (p + z*z/(2*n) - z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / d
    else:
        lower = None
    return {"n": n, "wins": wins, "losses": n-wins,
            "minutos_distintos": minutos_distintos,
            "simultaneas_mismo_minuto": n - minutos_distintos,
            "winrate_por_minuto_pct": round(100*p_ind, 2) if p_ind is not None else None,
            "wilson_minutos_95_pct": round(100*limite_ind, 2) if limite_ind is not None else None,
            "winrate_pct": round(100*wins/n, 2) if n else None,
            "wilson_inferior_95_pct": round(100*lower, 2) if lower is not None else None,
            "neto": round(pnl, 2),
            "expectativa_por_operacion": round(pnl/n, 4) if n else None}


def analizar(rows, minimo_train=20, minimo_oos=20):
    if minimo_train < 2 or minimo_oos < 2:
        raise ValueError("MINIMOS_INVALIDOS")
    # Compartir el mismo contrato de procedencia y deduplicacion que
    # los analizadores de memoria e interacciones. El legado declarado
    # se mantiene diferenciado de la marca PRACTICE del CSV.
    registros, rejects = _limpiar(rows)
    valid = [
        {"order_id": oid, "fecha": fecha, "pnl": pnl,
         "features": _features(fila),
         "procedencia": fila["_procedencia_practice_auditoria"]}
        for fecha, oid, pnl, fila in registros
    ]
    procedencia = dict(Counter(r["procedencia"] for r in valid))
    dates = sorted({r["fecha"].date().isoformat() for r in valid})
    if len(dates) < 2:
        return {"estado": "SIN_DIAS_INDEPENDIENTES", "baseline": _metrics(valid),
                "procedencia": procedencia,
                "descartes": dict(rejects), "dias": len(dates), "operaciones_validas": len(valid),
                "candidato": None, "aviso": "No afirmar mejora sin validacion temporal independiente"}
    cut = dates[max(0, int(len(dates) * 0.7) - 1)]
    train = [r for r in valid if r["fecha"].date().isoformat() <= cut]
    oos = [r for r in valid if r["fecha"].date().isoformat() > cut]
    cohorts = defaultdict(list)
    for r in train:
        for key in FEATURES:
            value = r["features"].get(key, "SIN_DATO")
            if value != "SIN_DATO":
                cohorts[(key, value)].append(r)
    candidates = []
    for (key, value), group in sorted(cohorts.items()):
        if len(group) < minimo_train or len(group) == len(train):
            continue
        m = _metrics(group)
        # Operaciones simultaneas comparten el mismo shock de mercado:
        # no fingir independencia al seleccionar una regla en TRAIN.
        if m["minutos_distintos"] < minimo_train:
            continue
        candidates.append((m["expectativa_por_operacion"], len(group), key, value, m))
    candidates.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))
    baseline_oos = _metrics(oos)
    top = candidates[0] if candidates else None
    if top is None:
        candidate = None
    else:
        _, _, key, value, train_metrics = top
        picked = [r for r in oos if r["features"].get(key) == value]
        test_metrics = _metrics(picked)
        candidate = {
            "variable": key, "valor": value, "train": train_metrics, "test_oos": test_metrics,
            "retencion_oos_pct": round(100*len(picked)/len(oos), 2) if oos else None,
            "evidencia_minima_oos": (
                len(picked) >= minimo_oos
                and test_metrics["minutos_distintos"] >= minimo_oos
            ),
            "diferencia_expectativa_oos_vs_baseline": (
                round(test_metrics["expectativa_por_operacion"] - baseline_oos["expectativa_por_operacion"], 4)
                if picked and oos else None),
            "supera_objetivo_oos": (
                len(picked) >= minimo_oos
                and test_metrics["minutos_distintos"] >= minimo_oos
                and
                test_metrics["winrate_pct"] is not None and
                test_metrics["winrate_pct"] >= 60
                and test_metrics["winrate_por_minuto_pct"] is not None
                and test_metrics["winrate_por_minuto_pct"] >= 60
                and test_metrics["neto"] > 0),
            "autoriza_operaciones": False,
        }
    return {"estado": "ANALISIS_NO_OPERABLE", "operaciones_validas": len(valid),
            "procedencia": procedencia,
            "descartes": dict(sorted(rejects.items())), "dias": len(dates),
            "corte_train": cut, "train": _metrics(train), "test_oos": baseline_oos,
            "candidatos_train_comparados": len(candidates), "candidato": candidate,
            "nota": "Asociacion no causal; sesgo de seleccion de operaciones ejecutadas. "
                    "No estima operaciones descartadas. OOS no selecciona reglas. "
                    "Requiere confirmacion prospectiva."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("historial", nargs="?", default="historial_bot.csv")
    ap.add_argument("--minimo-train", type=int, default=20)
    ap.add_argument("--minimo-oos", type=int, default=20)
    args = ap.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as handle:
        result = analizar(csv.DictReader(handle), args.minimo_train, args.minimo_oos)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
