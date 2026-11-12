"""Experimento de seleccion de familias PRACTICE sin fuga temporal.

Diagnostico: aprende solo del primer tramo temporal y mide las mismas
familias en dias posteriores. Nunca autoriza ni filtra operaciones LIVE.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def _fecha(valor):
    try:
        return datetime.fromisoformat(str(valor or "").strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("FECHA_INVALIDA") from exc


def evaluar_separacion_temporal(
    filas, minimo_train=20, minimo_test=20, objetivo=0.60,
):
    if minimo_train < 1 or minimo_test < 1 or not 0 < objetivo <= 1:
        raise ValueError("PARAMETROS_INVALIDOS")
    registros = []
    ids = set()
    descartes = defaultdict(int)
    for fila in filas:
        if str(fila.get("estado", "")).strip().upper() != "CERRADA":
            descartes["NO_CERRADA"] += 1
            continue
        oid = str(fila.get("order_id", "")).strip()
        if not oid or oid in ids:
            descartes["ID_AUSENTE_O_REPETIDO"] += 1
            continue
        try:
            instante = _fecha(fila.get("fecha"))
            pnl = float(str(fila.get("resultado", "")).strip())
        except (ValueError, TypeError):
            descartes["FECHA_O_RESULTADO_INVALIDO"] += 1
            continue
        if not (-float("inf") < pnl < float("inf")):
            descartes["RESULTADO_NO_FINITO"] += 1
            continue
        ids.add(oid)
        if pnl == 0:
            descartes["EMPATE"] += 1
            continue
        registros.append({
            "dia": instante.date().isoformat(),
            "fecha": instante,
            "id": oid,
            "estrategia": str(fila.get("patron") or "SIN_PATRON").strip(),
            "resultado": pnl,
        })
    zonas = {r["fecha"].tzinfo is None for r in registros}
    if len(zonas) > 1:
        raise ValueError("MEZCLA_FECHAS_CON_Y_SIN_ZONA")
    dias = sorted({r["dia"] for r in registros})
    # Ninguna eleccion de familias puede usar el ultimo dia de evaluacion.
    if len(dias) < 2:
        return {
            "estado": "SIN_SEPARACION_TEMPORAL",
            "dias_disponibles": dias,
            "descartes": dict(descartes),
            "experimentos": [],
            "cambios_live_autorizados": False,
        }
    dia_test = dias[-1]
    grupos_train = defaultdict(list)
    grupos_test = defaultdict(list)
    for r in registros:
        grupo = grupos_test if r["dia"] == dia_test else grupos_train
        grupo[r["estrategia"]].append(r["resultado"])

    def estadistica(valores):
        n = len(valores)
        wins = sum(x > 0 for x in valores)
        return {
            "n": n,
            "wins": wins,
            "losses": n - wins,
            "winrate_pct": round(100 * wins / n, 2) if n else None,
            "neto": round(sum(valores), 2),
        }

    experimentos = []
    for estrategia in sorted(set(grupos_train) | set(grupos_test)):
        train = estadistica(grupos_train[estrategia])
        test = estadistica(grupos_test[estrategia])
        # Preseleccion congelada ANTES de observar el ultimo dia.
        elegida_train = (
            train["n"] >= minimo_train
            and train["winrate_pct"] >= 100 * objetivo
            and train["neto"] > 0
        )
        evaluable_test = test["n"] >= minimo_test
        experimentos.append({
            "estrategia": estrategia,
            "train": train,
            "test": test,
            "seleccion_train": elegida_train,
            "test_muestra_suficiente": evaluable_test,
            "test_cumple_objetivo": (
                test["winrate_pct"] >= 100 * objetivo and test["neto"] > 0
                if elegida_train and evaluable_test else None
            ),
        })
    return {
        "estado": "DIAGNOSTICO_RETROSPECTIVO_NO_AUTORIZANTE",
        "dias_train": dias[:-1],
        "dia_test": dia_test,
        "descartes": dict(sorted(descartes.items())),
        "criterio_preseleccion": {
            "minimo_train": minimo_train,
            "minimo_test": minimo_test,
            "objetivo_winrate_pct": 100 * objetivo,
            "neto_positivo": True,
        },
        "experimentos": experimentos,
        "cambios_live_autorizados": False,
        "evidencia_prospectiva_suficiente": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as archivo:
        reporte = evaluar_separacion_temporal(csv.DictReader(archivo))
    print(json.dumps(reporte, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
