"""Auditoria de consistencia PRACTICE: solo lectura, sin autorizacion de trading.

Calcula bloques de 20 y ventanas moviles de 20 operaciones ordenadas por
fecha de senal. Nunca genera aprendizaje ni propone cambios automaticos.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

TAMANO_VENTANA = 20
OBJETIVO = 0.60


def _instante(fecha):
    valor = str(fecha or "").strip()
    if not valor:
        raise ValueError("FECHA_VACIA")
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("FECHA_INVALIDA") from exc


def evaluar_filas(filas, tamano=TAMANO_VENTANA, objetivo=OBJETIVO):
    if tamano < 1 or not 0 < objetivo <= 1:
        raise ValueError("PARAMETROS_INVALIDOS")
    aceptadas = []
    rechazadas = defaultdict(int)
    ids = set()
    for fila in filas:
        if str(fila.get("estado", "")).strip().upper() != "CERRADA":
            rechazadas["NO_CERRADA"] += 1
            continue
        identificador = str(fila.get("order_id", "")).strip()
        if not identificador:
            rechazadas["SIN_ORDER_ID"] += 1
            continue
        if identificador in ids:
            rechazadas["ORDER_ID_DUPLICADO"] += 1
            continue
        try:
            instante = _instante(fila.get("fecha"))
        except ValueError as exc:
            rechazadas[str(exc)] += 1
            continue
        try:
            pnl = float(str(fila.get("resultado", "")).strip())
        except ValueError:
            rechazadas["RESULTADO_INVALIDO"] += 1
            continue
        if not (-float("inf") < pnl < float("inf")):
            rechazadas["RESULTADO_INVALIDO"] += 1
            continue
        # El empate no equivale ni a WIN ni a LOSS y no completa ventanas.
        ids.add(identificador)
        if pnl == 0:
            rechazadas["EMPATE"] += 1
            continue
        aceptadas.append({
            "order_id": identificador,
            "fecha": instante,
            "dia": instante.date().isoformat(),
            "patron": str(fila.get("patron") or "SIN_PATRON").strip(),
            "pnl": pnl,
            "win": pnl > 0,
        })
    # Comparacion por fecha, no por el orden arbitrario de las filas CSV.
    # Fechas sin zona deben provenir de la misma zona de registro.
    zonas = {x["fecha"].tzinfo is None for x in aceptadas}
    if len(zonas) > 1:
        raise ValueError("MEZCLA_FECHAS_CON_Y_SIN_ZONA")
    aceptadas.sort(key=lambda r: (r["fecha"], r["order_id"]))

    def resumen(bloque):
        n = len(bloque)
        wins = sum(r["win"] for r in bloque)
        return {
            "n": n,
            "wins": wins,
            "losses": n - wins,
            "winrate_pct": round(100 * wins / n, 2) if n else None,
            "neto": round(sum(r["pnl"] for r in bloque), 2),
            "cumple_60": wins / n >= objetivo if n == tamano else None,
        }

    bloques = [resumen(aceptadas[i:i + tamano])
               for i in range(0, len(aceptadas), tamano)]
    completos = bloques[:len(aceptadas) // tamano]
    moviles = [resumen(aceptadas[i:i + tamano])
               for i in range(len(aceptadas) - tamano + 1)]
    dias = defaultdict(list)
    patrones = defaultdict(list)
    for r in aceptadas:
        dias[r["dia"]].append(r)
        patrones[r["patron"]].append(r)
    return {
        "modo": "AUDITORIA_SOLO_LECTURA",
        "objetivo_pct": round(objetivo * 100, 2),
        "ventana": tamano,
        "total_filas_validas_win_loss": len(aceptadas),
        "descartes": dict(sorted(rechazadas.items())),
        "global": resumen(aceptadas),
        "dias": {k: resumen(v) for k, v in sorted(dias.items())},
        "estrategias": {k: resumen(v) for k, v in sorted(patrones.items())},
        "bloques_no_solapados": bloques,
        "bloques_completos": len(completos),
        "bloques_completos_bajo_objetivo": sum(
            x["cumple_60"] is False for x in completos
        ),
        "ventanas_moviles": len(moviles),
        "ventanas_moviles_bajo_objetivo": sum(
            x["cumple_60"] is False for x in moviles
        ),
        "consistencia_20_observada": bool(moviles) and all(
            x["cumple_60"] for x in moviles
        ),
        "evidencia_prospectiva_suficiente": False,
        "operaciones_autorizadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as archivo:
        reporte = evaluar_filas(csv.DictReader(archivo))
    print(json.dumps(reporte, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
