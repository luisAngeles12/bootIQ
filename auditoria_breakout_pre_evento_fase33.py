"""Fase 3.3: replay broker-free de breakout/retest con zonas previas.

Solo cuenta detecciones técnicas en velas pasadas. No calcula winrate,
no emite señales operativas ni modifica CORE4, cerebro o protocolos.
"""
import argparse
import csv
from collections import Counter
from pathlib import Path

from zonas import (soporte_resistencia_zonas, breakout_retest,
                   diagnosticar_breakout_retest_pre_evento)


def auditar_velas_breakout(filas, activo="SIN_ACTIVO", minimo_velas=130):
    velas = list(filas)
    eventos = []
    ventanas = 0
    for fin in range(minimo_velas, len(velas) + 1):
        bloque = velas[fin-minimo_velas:fin]
        try:
            tiempo = int(float(bloque[-1]["from"]))
            opens = [float(r["open"]) for r in bloque]
            closes = [float(r["close"]) for r in bloque]
            highs = [float(r["max"]) for r in bloque]
            lows = [float(r["min"]) for r in bloque]
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
        if any(h < max(o, c) or l > min(o, c) or h < l
               for o, c, h, l in zip(opens, closes, highs, lows)):
            continue
        vol = sum(highs[i] - lows[i] for i in range(-14, 0)) / 14
        if vol <= 0:
            continue
        zonas_actuales = soporte_resistencia_zonas(
            closes[-1], highs, lows, vol)
        antigua_call = breakout_retest(
            opens, closes, highs, lows, zonas_actuales[1], "resistencia")[0]
        antigua_put = breakout_retest(
            opens, closes, highs, lows, zonas_actuales[0], "soporte")[0]
        sombra = diagnosticar_breakout_retest_pre_evento(
            opens, closes, highs, lows, vol)
        ventanas += 1
        for lado, viejo, nuevo in (
            ("CALL", antigua_call, sombra["br_call_sombra"]),
            ("PUT", antigua_put, sombra["br_put_sombra"]),
        ):
            if viejo or nuevo:
                eventos.append({"activo": activo, "fecha": tiempo,
                                "direccion": lado,
                                "detector_actual": bool(viejo),
                                "detector_sombra": bool(nuevo),
                                "zona_previa": sombra[
                                    "resistencia_previa_sombra" if lado == "CALL"
                                    else "soporte_previo_sombra"]})
    claves = [(e["activo"], e["fecha"], e["direccion"]) for e in eventos]
    if len(claves) != len(set(claves)):
        raise ValueError("eventos de breakout duplicados")
    return {"activo": activo, "ventanas": ventanas, "eventos": eventos,
            "actuales": sum(e["detector_actual"] for e in eventos),
            "sombra": sum(e["detector_sombra"] for e in eventos),
            "autoriza_operar": False}


def auditar_carpeta(carpeta):
    resultados = []
    for ruta in sorted(Path(carpeta).glob("*.csv")):
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            resultados.append(auditar_velas_breakout(
                csv.DictReader(archivo), activo=ruta.stem))
    eventos = [e for r in resultados for e in r["eventos"]
               if e["detector_sombra"]]
    minutos = Counter(e["fecha"] // 60 for e in eventos)
    return {"archivos": len(resultados),
            "ventanas": sum(r["ventanas"] for r in resultados),
            "eventos_actuales": sum(r["actuales"] for r in resultados),
            "eventos_sombra": len(eventos),
            "minutos_distintos_sombra": len(minutos),
            "max_eventos_sombra_por_minuto": max(minutos.values(), default=0),
            "activos_con_eventos_sombra": len({e["activo"] for e in eventos}),
            "autoriza_operar": False}


def main():
    parser = argparse.ArgumentParser(description="BR zona previa SOLO SOMBRA")
    parser.add_argument("carpeta")
    args = parser.parse_args()
    print(auditar_carpeta(args.carpeta))


if __name__ == "__main__":
    main()
