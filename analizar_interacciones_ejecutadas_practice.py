"""Busca interacciones de señales ejecutadas PRACTICE con holdout cronologico.

Las candidatas se seleccionan solo en entrenamiento; los hallazgos del holdout
se etiquetan post hoc. El informe no cambia el cerebro ni autoriza operaciones.
"""
import argparse
import csv
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from analizar_oportunidades_integrales_practice import FEATURES, _features
from construir_memoria_ejecutadas_train_practice import _limpiar

MIN_DIAS_TRAIN = 3
MIN_DIAS_TEST = 2
OBJETIVO_ACIERTO_PCT = 60.0


def leer_filas(ruta):
    """Lee CSV o ZIP que contenga exactamente un historial_bot.csv."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".zip":
        with zipfile.ZipFile(ruta) as archivo:
            candidatos = [
                nombre for nombre in archivo.namelist()
                if Path(nombre).name.lower() == "historial_bot.csv"
            ]
            if len(candidatos) != 1:
                raise ValueError("CSV_HISTORIAL_AUSENTE_O_DUPLICADO")
            with archivo.open(candidatos[0]) as raw:
                texto = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                return list(csv.DictReader(texto))
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _resumen(eventos):
    n = len(eventos)
    wins = sum(e["pnl"] > 0 for e in eventos)
    losses = sum(e["pnl"] < 0 for e in eventos)
    neto = sum(e["pnl"] for e in eventos)
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "winrate_pct": round(100 * wins / n, 2) if n else None,
        "neto": round(neto, 2),
        "expectativa_por_operacion": round(neto / n, 4) if n else None,
        "dias": len({e["dia"] for e in eventos}),
    }


def _resumen_diario(eventos):
    por_dia = defaultdict(list)
    for evento in eventos:
        por_dia[evento["dia"]].append(evento)
    return [
        {"dia": dia, **_resumen(registros)}
        for dia, registros in sorted(por_dia.items())
    ]


def analizar(filas, min_train=20, min_test=20, proporcion_dias_train=0.7):
    if type(min_train) is not int or min_train < 2:
        raise ValueError("MIN_TRAIN_INVALIDO")
    if type(min_test) is not int or min_test < 2:
        raise ValueError("MIN_TEST_INVALIDO")
    if (isinstance(proporcion_dias_train, bool)
            or not isinstance(proporcion_dias_train, (int, float))
            or not math.isfinite(proporcion_dias_train)
            or not 0 < proporcion_dias_train < 1):
        raise ValueError("PROPORCION_DIAS_INVALIDA")

    filas = list(filas)
    registros, descartes = _limpiar(filas)
    eventos = [
        {
            "dia": fecha.date().isoformat(),
            "pnl": pnl,
            "features": _features(fila),
            "procedencia": fila["_procedencia_practice_auditoria"],
        }
        for fecha, _order_id, pnl, fila in registros
    ]
    dias = sorted({evento["dia"] for evento in eventos})
    procedencia = Counter(e["procedencia"] for e in eventos)

    respuesta_base = {
        "tipo": "INVESTIGACION_RETROSPECTIVA_INTERACCIONES_EJECUTADAS",
        "filas_originales": len(filas),
        "operaciones_validas_no_empate": len(eventos),
        "operaciones_practice_verificadas": procedencia.get("CSV_MODO_PRACTICE", 0),
        "operaciones_practice_declaradas_legacy": procedencia.get(
            "USUARIO_DECLARADO_LEGADO_SIN_MODO", 0
        ),
        "descartes": descartes,
        "dias_disponibles": len(dias),
        "promueve_estrategia": False,
        "autoriza_operaciones": False,
        "autoriza_real": False,
    }

    if len(dias) < MIN_DIAS_TRAIN + MIN_DIAS_TEST:
        return {
            **respuesta_base,
            "estado": "JORNADAS_INSUFICIENTES",
            "baseline": _resumen(eventos),
            "interacciones": [],
        }

    n_train_dias = max(
        MIN_DIAS_TRAIN,
        min(len(dias) - MIN_DIAS_TEST,
            int(len(dias) * proporcion_dias_train)),
    )
    corte = dias[n_train_dias - 1]
    train = [e for e in eventos if e["dia"] <= corte]
    test = [e for e in eventos if e["dia"] > corte]
    conteos = Counter()
    interacciones = []
    descubrimientos_posthoc = []

    for campo_a, campo_b in combinations(FEATURES, 2):
        grupos = defaultdict(list)
        for evento in train:
            a = evento["features"].get(campo_a, "SIN_DATO")
            b = evento["features"].get(campo_b, "SIN_DATO")
            if a != "SIN_DATO" and b != "SIN_DATO":
                grupos[(a, b)].append(evento)

        for (valor_a, valor_b), muestra_train in grupos.items():
            if len(muestra_train) < min_train or len(muestra_train) == len(train):
                continue
            conteos["grupos_train_evaluables"] += 1
            metricas_train = _resumen(muestra_train)
            muestra_test = [
                evento for evento in test
                if (evento["features"].get(campo_a) == valor_a
                    and evento["features"].get(campo_b) == valor_b)
            ]
            metricas_test = _resumen(muestra_test)
            tiene_minimo_test = metricas_test["n"] >= min_test
            cumple_test = (
                tiene_minimo_test
                and metricas_test["winrate_pct"] >= OBJETIVO_ACIERTO_PCT
                and metricas_test["neto"] > 0
            )
            if tiene_minimo_test:
                conteos["grupos_con_muestra_test_suficiente"] += 1
            if cumple_test:
                conteos["grupos_60_y_neto_positivo_test_posthoc"] += 1
                descubrimientos_posthoc.append({
                    "regla": {campo_a: valor_a, campo_b: valor_b},
                    "train": metricas_train,
                    "test_oos": metricas_test,
                    "test_oos_por_dia": _resumen_diario(muestra_test),
                    "seleccion_posthoc_por_test": True,
                    "requiere_validacion_prospectiva": True,
                    "autoriza_operaciones": False,
                })

            if (metricas_train["winrate_pct"] < OBJETIVO_ACIERTO_PCT
                    or metricas_train["neto"] <= 0):
                continue
            conteos["candidatas_seleccionadas_solo_train"] += 1
            if tiene_minimo_test:
                conteos["candidatas_train_con_muestra_test_suficiente"] += 1
            if cumple_test:
                conteos["candidatas_train_60_y_neto_positivo_test"] += 1

            interacciones.append({
                "regla": {campo_a: valor_a, campo_b: valor_b},
                "train": metricas_train,
                "test_oos": metricas_test,
                "test_oos_por_dia": _resumen_diario(muestra_test),
                "muestra_test_suficiente": tiene_minimo_test,
                "cumple_60_y_neto_positivo_test": cumple_test,
                "autoriza_operaciones": False,
            })

    # El orden depende exclusivamente del entrenamiento; no del holdout.
    interacciones.sort(key=lambda x: (
        -x["train"]["expectativa_por_operacion"],
        -x["train"]["n"],
        tuple(x["regla"].items()),
    ))
    descubrimientos_posthoc.sort(key=lambda x: tuple(x["regla"].items()))
    claves_conteo = (
        "grupos_train_evaluables",
        "grupos_con_muestra_test_suficiente",
        "grupos_60_y_neto_positivo_test_posthoc",
        "candidatas_seleccionadas_solo_train",
        "candidatas_train_con_muestra_test_suficiente",
        "candidatas_train_60_y_neto_positivo_test",
    )
    return {
        **respuesta_base,
        "estado": "ANALISIS_RETROSPECTIVO_PARTIDO",
        "dia_corte_train": corte,
        "dias_train": dias[:n_train_dias],
        "dias_test_oos": dias[n_train_dias:],
        "baseline_train": _resumen(train),
        "baseline_test_oos": _resumen(test),
        "pares_de_features_explorados": len(list(combinations(FEATURES, 2))),
        "conteos": {clave: conteos.get(clave, 0) for clave in claves_conteo},
        "interacciones": interacciones,
        "descubrimientos_posthoc_test": descubrimientos_posthoc,
        "advertencia": (
            "Las interacciones se seleccionan entre multiples hipotesis y los "
            "resultados siguen siendo retrospectivos. El holdout historico no "
            "es validacion prospectiva ni prueba rentabilidad."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archivo", nargs="?", default="historial_bot.csv",
        help="CSV o ZIP con historial_bot.csv",
    )
    parser.add_argument("--min-train", type=int, default=20)
    parser.add_argument("--min-test", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(
        analizar(leer_filas(args.archivo), args.min_train, args.min_test),
        ensure_ascii=True,
        indent=2,
    ))


if __name__ == "__main__":
    main()
