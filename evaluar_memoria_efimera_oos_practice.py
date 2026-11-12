"""Diagnostico OOS V3: memoria efimera TRAIN, validacion reservada.

No escribe archivos de aprendizaje, no conecta a IQ Option, no autoriza
ordenes. No permite aprender con ningun resultado de VALIDACION.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from auditar_cobertura_memoria_v3_practice import (
    CORTE_TRAIN_INCLUSIVO,
    _items_admisibles,
    _registros_validos,
)
from motor_aprendizaje_historico import (
    _buscar_fuentes_aprendizaje,
    _combinar_fuentes,
    _crear_data_memoria,
    PRIOR_WINRATE,
)


def evaluar_oos_memoria(filas):
    validos, descartes = _registros_validos(filas)
    train = [
        row for fecha, row in validos
        if fecha.date().isoformat() <= CORTE_TRAIN_INCLUSIVO
    ]
    validacion = [
        row for fecha, row in validos
        if fecha.date().isoformat() > CORTE_TRAIN_INCLUSIVO
    ]
    grupos = defaultdict(lambda: {"nivel": "", "wins": 0, "losses": 0})
    for row in train:
        es_win = float(row["resultado"]) > 0
        for item in _items_admisibles(row):
            grupo = grupos[item["clave"]]
            grupo["nivel"] = item["nivel"]
            grupo["wins" if es_win else "losses"] += 1

    # Modelo calculado exclusivamente con el TRAIN; no se persiste.
    memoria = {}
    for clave, grupo in grupos.items():
        wins, losses = grupo["wins"], grupo["losses"]
        memoria[clave] = _crear_data_memoria({
            "clave": clave,
            "nivel": grupo["nivel"],
            "total": wins + losses,
            "wins": wins,
            "losses": losses,
            "winrate": (100.0 * wins / (wins + losses)),
            "estabilidad_disponible": "False",
        })

    errores_modelo = []
    errores_prior = []
    por_patron = defaultdict(lambda: {
        "n": 0, "con_principal": 0, "wins": 0, "losses": 0,
        "brier_modelo_suma": 0.0, "brier_prior_suma": 0.0,
    })
    sin_principal = 0
    prob_min = None
    prob_max = None
    for row in validacion:
        fuentes, _ = _buscar_fuentes_aprendizaje(row, memoria)
        calculo = _combinar_fuentes(fuentes)
        principal = calculo["fuente_principal"]
        if principal is None:
            sin_principal += 1
        p = calculo["probabilidad_estimada"] / 100.0
        prior = PRIOR_WINRATE / 100.0
        y = 1 if float(row["resultado"]) > 0 else 0
        error = (p - y) ** 2
        error_prior = (prior - y) ** 2
        errores_modelo.append(error)
        errores_prior.append(error_prior)
        prob_min = p if prob_min is None else min(prob_min, p)
        prob_max = p if prob_max is None else max(prob_max, p)
        patron = str(row.get("patron") or "").strip() or "SIN_PATRON"
        r = por_patron[patron]
        r["n"] += 1
        r["wins" if y else "losses"] += 1
        r["con_principal"] += int(principal is not None)
        r["brier_modelo_suma"] += error
        r["brier_prior_suma"] += error_prior

    def redondear(numerador, denominador):
        return round(numerador / denominador, 5) if denominador else None

    return {
        "modo": "OOS_MEMORIA_EFIMERA_SOLO_LECTURA",
        "corte_train_inclusivo": CORTE_TRAIN_INCLUSIVO,
        "train_n": len(train),
        "validacion_n": len(validacion),
        "claves_efimeras": len(memoria),
        "senales_sin_principal": sin_principal,
        "probabilidad_modelo_min_pct": (
            round(100 * prob_min, 2) if prob_min is not None else None
        ),
        "probabilidad_modelo_max_pct": (
            round(100 * prob_max, 2) if prob_max is not None else None
        ),
        "brier_modelo": redondear(sum(errores_modelo), len(errores_modelo)),
        "brier_prior_oficial": redondear(sum(errores_prior), len(errores_prior)),
        "brier_por_patron": {
            patron: {
                "n": r["n"],
                "wins": r["wins"],
                "losses": r["losses"],
                "con_principal": r["con_principal"],
                "brier_modelo": redondear(r["brier_modelo_suma"], r["n"]),
                "brier_prior_oficial": redondear(r["brier_prior_suma"], r["n"]),
            } for patron, r in sorted(por_patron.items())
        },
        "descartes": descartes,
        "limitaciones": [
            "El Brier menor es mejor, pero una sola jornada no valida generalizacion.",
            "TRAIN tiene sesgo de seleccion por operaciones ejecutadas.",
            "La memoria efimera no tiene estabilidad temporal validada.",
            "Este diagnostico no reproduce toda la decision ni autoriza entradas.",
        ],
        "resultado_validacion_usado_en_memoria": False,
        "archivos_escritos": False,
        "memoria_productiva_modificada": False,
        "ordenes_autorizadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as archivo:
        reporte = evaluar_oos_memoria(csv.DictReader(archivo))
    print(json.dumps(reporte, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
