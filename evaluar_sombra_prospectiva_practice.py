"""Audita resultados de velas de candidatas bloqueadas sin autorizar trading.

Los WIN/LOSS son hipoteticos: no contienen fill, payout ni PnL del broker.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ESTADO_VALIDO = "HIPOTETICO_VELA_COMPLETA_SIN_FILL"


def _resumen(eventos):
    n = len(eventos)
    wins = sum(x["resultado"] == "WIN" for x in eventos)
    return {
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "winrate_pct": round(wins * 100 / n, 2) if n else None,
        "cumple_60_pct": n > 0 and wins * 5 >= n * 3,
    }


def evaluar(filas):
    """Devuelve cobertura y metricas, sin promover reglas ni atribuir PnL."""
    filas = list(filas)
    ids = set()
    validos = []
    descartes = defaultdict(int)
    pendientes = 0
    for fila in filas:
        if str(fila.get("decision") or "").strip().upper() != "NO_OPERAR":
            descartes["NO_RECHAZADA"] += 1
            continue
        clave = str(fila.get("id") or "").strip()
        if not clave or clave in ids:
            descartes["ID_DUPLICADO_O_VACIO"] += 1
            continue
        ids.add(clave)
        resultado = str(fila.get("resultado_hipotetico") or "").strip().upper()
        if not resultado:
            pendientes += 1
            continue
        if resultado == "EMPATE":
            descartes["EMPATE"] += 1
            continue
        if resultado not in ("WIN", "LOSS") or fila.get("calidad_tiempo") != ESTADO_VALIDO:
            descartes["CALIDAD_O_RESULTADO_INVALIDO"] += 1
            continue
        try:
            ts = int(str(fila.get("vela_entrada_from") or ""))
            if ts <= 0:
                raise ValueError("TIMESTAMP")
            fecha = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            descartes["FECHA_INVALIDA"] += 1
            continue
        validos.append({"id": clave, "ts": ts, "dia_utc": fecha,
                        "direccion": str(fila.get("direccion") or "").lower(),
                        "resultado": resultado})
    validos.sort(key=lambda x: (x["ts"], x["id"]))
    dias = defaultdict(list)
    direcciones = defaultdict(list)
    for x in validos:
        dias[x["dia_utc"]].append(x)
        direcciones[x["direccion"]].append(x)
    bloques = []
    for inicio in range(0, len(validos), 20):
        items = validos[inicio:inicio + 20]
        if len(items) != 20:
            break
        bloques.append({"bloque": len(bloques) + 1, **_resumen(items)})
    return {
        "tipo": "AUDITORIA_HIPOTETICA_SOMBRA_PRACTICE",
        "filas": len(filas), "resueltas_validas": len(validos),
        "pendientes_sin_resultado": pendientes,
        "descartes": dict(sorted(descartes.items())),
        "global": _resumen(validos),
        "por_dia_utc": [{"dia_utc": d, **_resumen(x)} for d, x in sorted(dias.items())],
        "por_direccion": {d: _resumen(x) for d, x in sorted(direcciones.items())},
        "bloques_completos_20": bloques,
        "bloques_20_cumplen_60": sum(x["cumple_60_pct"] for x in bloques),
        "todos_bloques_20_cumplen_60": bool(bloques) and all(x["cumple_60_pct"] for x in bloques),
        "pnl_broker": None,
        "rentabilidad_demostrada": False,
        "autoriza_operaciones": False,
        "nota": "Aciertos hipoteticos de vela completa, sin fill, payout ni validacion OOS independiente.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", nargs="?", default="auditoria_candidatas_sombra_practice.csv")
    args = p.parse_args()
    with Path(args.csv).open(encoding="utf-8-sig", newline="") as f:
        resultado = evaluar(csv.DictReader(f))
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
