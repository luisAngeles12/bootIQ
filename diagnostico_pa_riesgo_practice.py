"""Diagnostico PRACTICE de alineacion Price Action y riesgo compuesto.

No crea señales, no ajusta umbrales, no produce memoria productiva.
Las comparaciones son observacionales, no causales.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def analizar_pa_riesgo(filas):
    grupos = defaultdict(list)
    dias = defaultdict(lambda: defaultdict(list))
    rechazados = defaultdict(int)
    ids = set()
    for r in filas:
        if str(r.get("estado") or "").strip().upper() != "CERRADA":
            rechazados["NO_CERRADA"] += 1
            continue
        oid = str(r.get("order_id") or "").strip()
        if not oid or oid in ids:
            rechazados["ID_AUSENTE_O_DUPLICADO"] += 1
            continue
        try:
            pnl = float(str(r.get("resultado") or "").strip())
        except ValueError:
            rechazados["RESULTADO_INVALIDO"] += 1
            continue
        if not (-float("inf") < pnl < float("inf")):
            rechazados["RESULTADO_NO_FINITO"] += 1
            continue
        ids.add(oid)
        if pnl == 0:
            rechazados["EMPATE"] += 1
            continue
        direccion = str(r.get("direccion") or "").strip().upper()
        pa = str(r.get("pa_direccion") or "").strip().upper()
        if direccion not in {"CALL", "PUT"}:
            alineacion = "SIN_DIRECCION_OPERACION"
        elif pa in {"CALL", "PUT"}:
            alineacion = "ALINEADA" if pa == direccion else "CONTRARIA"
        elif pa in {"NEUTRA", "NEUTRAL"}:
            alineacion = "NEUTRA"
        else:
            alineacion = "SIN_DATO_PA"
        dato_riesgo = str(r.get("auditoria_riesgo_compuesto_json") or "").strip()
        if dato_riesgo:
            try:
                parsed = json.loads(dato_riesgo)
                riesgo = str(parsed.get("riesgo_nivel") or "SIN_NIVEL").upper() if isinstance(parsed, dict) else "JSON_NO_OBJETO"
            except (ValueError, TypeError):
                riesgo = "JSON_INVALIDO"
        else:
            riesgo = "SIN_SNAPSHOT"
        clave = (alineacion, riesgo)
        grupos[clave].append(pnl)
        fecha = str(r.get("fecha") or "")[:10]
        dias[fecha][clave].append(pnl)

    def resumen(xs):
        n = len(xs)
        w = sum(x > 0 for x in xs)
        return {
            "n": n,
            "wins": w,
            "losses": n - w,
            "winrate_pct": round(100 * w / n, 2) if n else None,
            "neto": round(sum(xs), 2),
            # Un efecto estimado sin muestra ni aleatorizacion NO es causal.
            "evidencia_causal": False,
        }

    return {
        "modo": "DIAGNOSTICO_SOLO_LECTURA",
        "grupos": [
            {"alineacion_pa": pa, "riesgo": riesgo, **resumen(xs)}
            for (pa, riesgo), xs in sorted(grupos.items())
        ],
        "dias": {
            dia: [
                {"alineacion_pa": pa, "riesgo": riesgo, **resumen(xs)}
                for (pa, riesgo), xs in sorted(subgrupos.items())
            ]
            for dia, subgrupos in sorted(dias.items())
        },
        "descartes": dict(sorted(rechazados.items())),
        "cambios_operativos_autorizados": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        print(json.dumps(analizar_pa_riesgo(csv.DictReader(f)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
