"""Diagnostico exploratorio del CHOCH BAJISTA en operaciones ejecutadas PRACTICE.

No selecciona ni autoriza reglas de entrada. La fecha de corte y las
observaciones de TEST son descriptivas; cualquier nueva hipotesis requiere
validacion prospectiva posterior en datos que aun no se han observado.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from analizar_oportunidades_integrales_practice import _features, _metrics
from construir_memoria_ejecutadas_train_practice import _limpiar

PATRON = "CHOCH BAJISTA"
CAMPOS = ("calidad_mercado", "tipo_mercado", "regimen_mercado",
          "estado_tendencia", "accion_precio", "pa_tipo",
          "rsi_zona", "ema_direccion", "bb_ubicacion",
          "direccion_contra_tendencia", "origen_autoridad",
          "protocolo_sugerido")


def diagnosticar(rows, corte="2026-11-16", minimo_subgrupo=10):
    if minimo_subgrupo < 1:
        raise ValueError("MINIMO_SUBGRUPO_INVALIDO")
    # Igual procedencia, estados y deduplicacion que el analizador oficial.
    registros, descartes = _limpiar(rows)
    evaluados = []
    for fecha, oid, pnl, fila in registros:
        feats = _features(fila)
        if feats.get("patron") != PATRON:
            continue
        evaluados.append({
            "fecha": fecha, "order_id": oid, "pnl": pnl,
            "features": feats,
            "procedencia": fila["_procedencia_practice_auditoria"],
        })
    evaluados.sort(key=lambda r: (r["fecha"], r["order_id"]))
    train = [r for r in evaluados if r["fecha"].date().isoformat() <= corte]
    test = [r for r in evaluados if r["fecha"].date().isoformat() > corte]

    def agrupaciones(items):
        dias = defaultdict(list)
        campos = defaultdict(list)
        for r in items:
            dias[r["fecha"].date().isoformat()].append(r)
            for nombre in CAMPOS:
                valor = r["features"].get(nombre)
                if valor and valor != "SIN_DATO":
                    campos[(nombre, valor)].append(r)
        por_dia = {dia: _metrics(grupo) for dia, grupo in sorted(dias.items())}
        por_condicion = [
            {"campo": campo, "valor": valor, **_metrics(grupo)}
            for (campo, valor), grupo in sorted(campos.items())
            if len(grupo) >= minimo_subgrupo
        ]
        # Orden alfabetico y tamaños fijados, no ordenar por ganadores.
        return {"total": _metrics(items), "por_dia": por_dia,
                "por_condicion": por_condicion}

    resumen_train = agrupaciones(train)
    resumen_test = agrupaciones(test)
    mapa_train = {
        (x["campo"], x["valor"]): x for x in resumen_train["por_condicion"]
    }
    mapa_test = {
        (x["campo"], x["valor"]): x for x in resumen_test["por_condicion"]
    }
    # Este informe contiene exclusivamente condiciones definidas por TRAIN;
    # la falta de muestra TEST es visible y nunca se interpreta como WIN.
    comparacion = []
    for (campo, valor), origen in sorted(mapa_train.items()):
        destino = mapa_test.get((campo, valor))
        # Incluir también grupos TEST por debajo del umbral mínimo para
        # evitar sesgo de supervivencia al mostrar sólo los grandes.
        if destino is None:
            filas_test_grupo = [
                x for x in test if x["features"].get(campo) == valor
            ]
            destino = _metrics(filas_test_grupo)
        wr_train = origen["winrate_por_minuto_pct"]
        wr_test = destino["winrate_por_minuto_pct"]
        comparacion.append({
            "campo": campo, "valor": valor,
            "n_train": origen["n"],
            "n_test": destino["n"],
            "minutos_train": origen["minutos_distintos"],
            "minutos_test": destino["minutos_distintos"],
            "winrate_train_pct": wr_train,
            "winrate_test_pct": wr_test,
            "delta_winrate_pp": (
                round(wr_test - wr_train, 2)
                if wr_train is not None and wr_test is not None else None
            ),
            "pnl_train": origen["neto"], "pnl_test": destino["neto"],
            "muestra_test_limitada": destino["minutos_distintos"] < minimo_subgrupo,
            "no_autoriza_operaciones": True,
        })
    return {
        "tipo": "DIAGNOSTICO_CHOCH_BAJISTA_SOLO_INVESTIGACION",
        "comparacion_condiciones_train_test": comparacion,
        "seleccion_por_test_prohibida": True,
        "corte": corte,
        "procedencia": sorted({r["procedencia"] for r in evaluados}),
        "train": resumen_train,
        "test": resumen_test,
        "descartes_procedencia": dict(descartes),
        "autoriza_operaciones": False,
        "puede_promover_patron": False,
        "advertencia": (
            "Desglose retrospectivo; no usar subgrupos descubiertos en "
            "TEST para operar. Requiere validacion en fechas futuras "
            "con broker PRACTICE, fill y payout observados."
        ),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archivo", nargs="?", default="historial_bot.csv")
    ap.add_argument("--corte", default="2026-11-16")
    ap.add_argument("--minimo-subgrupo", type=int, default=10)
    args = ap.parse_args()
    try:
        datetime.strptime(args.corte, "%Y-%m-%d")
    except ValueError:
        ap.error("--corte debe ser YYYY-MM-DD")
    with Path(args.archivo).open(encoding="utf-8-sig", newline="") as file:
        salida = diagnosticar(
            csv.DictReader(file), corte=args.corte,
            minimo_subgrupo=args.minimo_subgrupo
        )
    print(json.dumps(salida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
