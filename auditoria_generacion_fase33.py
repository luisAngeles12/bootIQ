"""Auditoría pasiva F3.3 de familias sin coincidencia CORE4.

No activa estrategias ni habilita operaciones: los resultados de señales
canceladas son contrafactuales e insuficientes para rentabilidad.
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt


def _dia_utc(fila):
    valor = fila.get("fecha_senal") or fila.get("fecha")
    try:
        if str(valor).strip().replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(valor), timezone.utc).date().isoformat()
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.astimezone(timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def _wilson_inferior(wins, total):
    if not total:
        return 0.0
    z = 1.96
    p = wins / total
    return 100 * (p + z*z/(2*total)
                  - z*sqrt(p*(1-p)/total + z*z/(4*total*total))) / (1+z*z/total)


def auditar_generacion_sin_core4(filas, objetivo=59.0, minimo_dias=3,
                                 minimo_senales_dia=20, minimo_total=100):
    grupos = defaultdict(lambda: defaultdict(lambda: {"win": 0, "loss": 0}))
    sin_match = sin_match_sin_resultado = 0
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        if str(fila.get("core4_match_previo", "")).lower() != "false":
            continue
        sin_match += 1
        resultado = str(fila.get("resultado_hipotetico") or "").upper()
        dia = _dia_utc(fila)
        if resultado not in ("WIN", "LOSS") or not dia:
            sin_match_sin_resultado += 1
            continue
        clave = (str(fila.get("familia_setup") or "SIN_FAMILIA"),
                 str(fila.get("calidad_setup") or "SIN_CALIDAD"))
        grupos[clave][dia][resultado.lower()] += 1

    salida = {}
    for clave, dias in sorted(grupos.items()):
        n = sum(v["win"] + v["loss"] for v in dias.values())
        w = sum(v["win"] for v in dias.values())
        detalle = {d: {"n": v["win"]+v["loss"], "win": v["win"],
                       "loss": v["loss"],
                       "wr_hipotetico": round(100*v["win"]/(v["win"]+v["loss"]), 2)}
                   for d, v in sorted(dias.items())}
        dias_validos = sum(v["n"] >= minimo_senales_dia and
                           v["wr_hipotetico"] >= objetivo for v in detalle.values())
        inferior = _wilson_inferior(w, n)
        salida[clave] = {
            "n": n, "win_hipoteticas": w, "loss_hipoteticas": n-w,
            "winrate_hipotetico": round(100*w/n, 2),
            "wilson_inferior_95": round(inferior, 2),
            "por_dia": detalle,
            "cumple_cobertura_exploratoria": bool(
                n >= minimo_total and len(dias) >= minimo_dias
                and dias_validos == len(dias) and inferior >= objetivo),
            "autoriza_operar": False,
        }
    return {"sin_match": sin_match,
            "sin_match_sin_resultado_o_fecha": sin_match_sin_resultado,
            "grupos": salida, "autoriza_operar": False}


def main():
    p = argparse.ArgumentParser(description="Fase 3.3 sin autoridad de trading")
    p.add_argument("csv")
    args = p.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        analisis = auditar_generacion_sin_core4(csv.DictReader(archivo))
    print("SIN_MATCH", analisis["sin_match"])
    print("SIN_RESULTADO_O_FECHA", analisis["sin_match_sin_resultado_o_fecha"])
    for grupo, datos in analisis["grupos"].items():
        print(grupo, datos)


if __name__ == "__main__":
    main()
