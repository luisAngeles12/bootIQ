"""Audita si el cerebro V3 aprovecha el historial cerrado PRACTICE.

Separa fuente estadistica, bootstrap y cierres sin decision registrable.
No reconstruye resultados de ordenes, no cambia memoria ni autoriza trades.
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def _float(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        result = float(v)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _str(v):
    return str(v or "").strip().upper() or "SIN_DATO"


def _resumen(registros):
    n = len(registros)
    wins = sum(x["resultado"] > 0 for x in registros)
    return {
        "n": n, "wins": wins, "losses": n-wins,
        "winrate_pct": round(wins*100/n, 2) if n else None,
        "neto": round(sum(x["resultado"] for x in registros), 2),
        "por_operacion": round(sum(x["resultado"] for x in registros)/n, 4) if n else None,
    }


def auditar(filas):
    validos, ids, descartes = [], set(), Counter()
    for f in filas:
        if _str(f.get("estado")) != "CERRADA":
            descartes["NO_CERRADA"] += 1
            continue
        if _str(f.get("modo_cuenta_configurado")) != "PRACTICE":
            descartes["NO_PRACTICE"] += 1
            continue
        order_id = str(f.get("order_id") or "").strip()
        pnl = _float(f.get("resultado"))
        if not order_id or pnl is None:
            descartes["ID_O_RESULTADO_INVALIDO"] += 1
            continue
        if order_id in ids:
            descartes["ORDER_ID_DUPLICADO"] += 1
            continue
        ids.add(order_id)
        if pnl == 0:
            descartes["EMPATE"] += 1
            continue
        try:
            fecha = datetime.fromisoformat(str(f.get("fecha") or "").replace("Z", "+00:00"))
        except (ValueError, TypeError):
            descartes["FECHA_INVALIDA"] += 1
            continue
        muestra = _float(f.get("muestra_probabilidad"))
        autoridad = _str(f.get("origen_autoridad"))
        fuente = str(f.get("clave_probabilidad_principal") or "").strip()
        if autoridad.startswith("BOOTSTRAP_"):
            ruta = "BOOTSTRAP_SIN_MEMORIA"
        elif fuente and muestra is not None and muestra > 0:
            ruta = "V3_CON_FUENTE_Y_MUESTRA"
        elif muestra is not None and muestra > 0:
            ruta = "MUESTRA_SIN_CLAVE_PRINCIPAL"
        elif muestra == 0:
            ruta = "V3_MUESTRA_CERO"
        else:
            ruta = "SIN_TELEMETRIA_V3"
        validos.append({
            "resultado": pnl, "fecha": fecha,
            "ruta": ruta, "autoridad": autoridad,
            "patron": _str(f.get("patron")),
            "activo": _str(f.get("activo")),
            "muestra": muestra,
            "fuente": fuente,
        })
    by_route, by_day = defaultdict(list), defaultdict(list)
    by_pattern, by_asset = defaultdict(list), defaultdict(list)
    for r in validos:
        by_route[r["ruta"]].append(r)
        by_day[r["fecha"].date().isoformat()].append(r)
        by_pattern[(r["patron"], r["ruta"])].append(r)
        by_asset[(r["activo"], r["ruta"])].append(r)
    total = len(validos)
    bootstrap = len(by_route["BOOTSTRAP_SIN_MEMORIA"])
    v3 = len(by_route["V3_CON_FUENTE_Y_MUESTRA"])
    return {
        "tipo": "COBERTURA_ESTADISTICA_V3_PRACTICE",
        "total_cierres_evaluables": total,
        "baseline": _resumen(validos),
        "cobertura_v3_con_fuente_pct": round(100*v3/total, 2) if total else None,
        "participacion_bootstrap_pct": round(100*bootstrap/total, 2) if total else None,
        "rutas": {k: _resumen(v) for k,v in sorted(by_route.items()) if v},
        "dias": {k: {"rutas": dict(sorted(Counter(r["ruta"] for r in v).items())),
                     **_resumen(v)} for k,v in sorted(by_day.items())},
        "estrategia_por_ruta": [
            {"patron": p, "ruta": ruta, **_resumen(g)}
            for (p,ruta),g in sorted(by_pattern.items())
        ],
        "activo_por_ruta": [
            {"activo": a, "ruta": ruta, **_resumen(g)}
            for (a,ruta),g in sorted(by_asset.items())
        ],
        "descartes": dict(sorted(descartes.items())),
        "advertencias": [
            "La presencia de fuente no demuestra que la estimacion V3 sea correcta.",
            "Bootstrap y V3 pueden operar en periodos y mercados distintos: comparacion no causal.",
            "Una entrada cerrada no prueba el resultado de las senales rechazadas.",
            "Los empates se excluyen del winrate; comparar netos y payout real.",
        ],
        "cambia_reglas": False, "autoriza_operaciones": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = ap.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        print(json.dumps(auditar(csv.DictReader(f)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
