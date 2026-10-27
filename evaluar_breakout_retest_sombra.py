"""Evaluación post-señal F3.3 en sombra. Nunca autoriza operaciones.

Usa exclusivamente el cierre de la vela siguiente (expiración de un minuto
en el BACKTEST oficial actual). Los patrones se detectan solo con velas
hasta idx_senal; la siguiente se consulta después para medir el resultado.
Las ventanas se solapan: estos casos NO son operaciones independientes.
"""

import argparse
import csv
from collections import Counter
from pathlib import Path

from auditar_breakout_retest_sombra import auditar_filas


def evaluar_filas(filas):
    filas = sorted(filas, key=lambda fila: int(fila["from"]))
    eventos = auditar_filas(filas)
    resultados = []
    for evento in eventos:
        direccion = (
            "call" if evento["br_call_sombra"] == 1
            else "put" if evento["br_put_sombra"] == -1
            else None
        )
        ambas = evento["br_call_sombra"] == 1 and evento["br_put_sombra"] == -1
        if not direccion and not ambas:
            continue

        idx = evento["idx_senal"]
        registro = {**evento, "direccion_sombra": "AMBAS" if ambas else direccion}
        if ambas:
            registro["resultado_hipotetico_sombra"] = "AMBIGUA"
        elif idx + 1 >= len(filas):
            registro["resultado_hipotetico_sombra"] = "SIN_FUTURO"
        else:
            entrada = float(filas[idx]["close"])
            cierre = float(filas[idx + 1]["close"])
            if entrada == cierre:
                resultado = "EMPATE"
            elif (cierre > entrada) == (direccion == "call"):
                resultado = "WIN"
            else:
                resultado = "LOSS"
            registro["resultado_hipotetico_sombra"] = resultado
        resultados.append(registro)
    return resultados


def evaluar_directorio(directorio):
    casos = []
    archivos = sorted(Path(directorio).glob("turbo_*.csv"))
    for archivo in archivos:
        with archivo.open(newline="", encoding="utf-8-sig") as stream:
            casos.extend(evaluar_filas(list(csv.DictReader(stream))))
    conteos = Counter(caso["resultado_hipotetico_sombra"] for caso in casos)
    direcciones = Counter(caso["direccion_sombra"] for caso in casos)
    evaluables = conteos["WIN"] + conteos["LOSS"]
    return {
        "datasets": len(archivos),
        "patrones": len(casos),
        "call": direcciones["call"],
        "put": direcciones["put"],
        "ambiguas": conteos["AMBIGUA"],
        "sin_futuro": conteos["SIN_FUTURO"],
        "empates": conteos["EMPATE"],
        "win": conteos["WIN"],
        "loss": conteos["LOSS"],
        "wr_hipotetico": round(100 * conteos["WIN"] / evaluables, 2)
        if evaluables else None,
        "advertencia": "VENTANAS_SOLAPADAS_NO_OPERACIONES_INDEPENDIENTES",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directorio")
    args = parser.parse_args()
    print(evaluar_directorio(args.directorio))
