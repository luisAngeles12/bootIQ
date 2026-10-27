"""Auditor independiente F3.3; no importa ni ejecuta el bot.

Lee datasets de velas y puede exportar TODAS las ventanas, incluso si
ningún motor de estrategia generó señal. Úsese solo para investigación.
"""

import argparse
import csv
from pathlib import Path

from diagnostico_breakout_retest_sombra import diagnosticar_breakout_retest_sombra


def auditar_filas(filas, ventana=181, segundos_vela=60):
    """Devuelve diagnósticos causales indexados por activo y vela de señal."""
    if ventana < 16:
        raise ValueError("ventana insuficiente")
    filas = sorted(filas, key=lambda f: int(f["from"]))
    tiempos = [int(f["from"]) for f in filas]
    if len(tiempos) != len(set(tiempos)):
        raise ValueError("timestamps duplicados")
    if any(b - a != segundos_vela for a, b in zip(tiempos, tiempos[1:])):
        raise ValueError("velas no continuas")

    resultados = []
    for idx in range(ventana - 1, len(filas)):
        tramo = filas[idx - ventana + 1: idx + 1]
        opens = [float(f["open"]) for f in tramo]
        closes = [float(f["close"]) for f in tramo]
        highs = [float(f["max"]) for f in tramo]
        lows = [float(f["min"]) for f in tramo]
        if any(h < max(o, c) or l > min(o, c) or h < l
               for o, c, h, l in zip(opens, closes, highs, lows)):
            raise ValueError("OHLC inválido")
        diagnostico = diagnosticar_breakout_retest_sombra(
            opens, closes, highs, lows
        )
        resultados.append({
            "activo": tramo[-1]["activo"],
            "tipo": tramo[-1].get("tipo", ""),
            "idx_senal": idx,
            "from_senal": tiempos[idx],
            **diagnostico,
        })
    return resultados


def auditar_directorio(directorio, salida=None):
    registros = []
    for ruta in sorted(Path(directorio).glob("turbo_*.csv")):
        with ruta.open(newline="", encoding="utf-8-sig") as stream:
            filas = list(csv.DictReader(stream))
        registros.extend(auditar_filas(filas))

    if salida is not None:
        campos = [
            "activo", "tipo", "idx_senal", "from_senal",
            "br_call_sombra", "br_put_sombra",
            "br_call_nivel_sombra", "br_put_nivel_sombra",
        ]
        with Path(salida).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=campos)
            writer.writeheader()
            writer.writerows(registros)

    return {
        "ventanas": len(registros),
        "call": sum(r["br_call_sombra"] == 1 for r in registros),
        "put": sum(r["br_put_sombra"] == -1 for r in registros),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directorio", help="carpeta de velas históricas")
    parser.add_argument("--salida", help="CSV de auditoría independiente")
    args = parser.parse_args()
    print(auditar_directorio(args.directorio, args.salida))
