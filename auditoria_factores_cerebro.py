"""Auditoría pasiva de factores del cerebro V3 en señales canceladas.

Los resultados de señales no ejecutadas son contrafactuales. Requiere
cobertura de activos, minutos y fechas; no autoriza operaciones.
"""
import csv
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt


FACTORES = ("patron", "direccion", "tipo_mercado", "estado_tendencia", "accion_precio")
OBJETIVO_WINRATE_MINIMO = 59.0  # solo auditoría, nunca cambia autoridad


def _fecha_minuto(fila):
    bruto = fila.get("fecha_senal") or fila.get("fecha")
    try:
        ts = int(float(bruto))
        if ts <= 0:
            return None, None
        return datetime.fromtimestamp(ts, timezone.utc).date().isoformat(), ts // 60
    except (TypeError, ValueError, OverflowError, OSError):
        return None, None


def _wilson_inferior(wins, n, z=1.96):
    if n <= 0:
        return 0.0
    p = wins / n
    return (p + z*z/(2*n) - z*sqrt((p*(1-p)+z*z/(4*n))/n)) / (1+z*z/n)


def analizar_factores_cancelados(filas, minimo=30, minimo_dias=3, minimo_activos=5):
    """Devuelve descripciones, nunca recomendaciones de trading.

    No considera operadas ni resultados inexistentes. Una sola ventana,
    por grande que sea, no se etiqueta como evidencia transferible.
    """
    grupos = defaultdict(lambda: {"n": 0, "wins": 0, "activos": set(),
                                  "dias": set(), "minutos": set(), "por_dia": defaultdict(list)})
    excluidos = {"no_cancelada": 0, "sin_resultado_hipotetico": 0}
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        estado = str(fila.get("estado_operacion") or "").upper()
        if not estado.startswith("CANCELADA_"):
            excluidos["no_cancelada"] += 1
            continue
        resultado = str(fila.get("resultado_hipotetico") or "").upper()
        if resultado not in {"WIN", "LOSS"}:
            excluidos["sin_resultado_hipotetico"] += 1
            continue
        dia, minuto = _fecha_minuto(fila)
        for factor in FACTORES:
            valor = str(fila.get(factor) or "").strip()
            if not valor:
                continue
            g = grupos[(factor, valor)]
            g["n"] += 1
            win = resultado == "WIN"
            g["wins"] += win
            if fila.get("activo"):
                g["activos"].add(str(fila["activo"]))
            if dia:
                g["dias"].add(dia)
                g["por_dia"][dia].append(win)
            if minuto is not None:
                g["minutos"].add(minuto)
    salida = []
    for (factor, valor), g in grupos.items():
        n = g["n"]
        if n < minimo:
            continue
        dias = len(g["dias"])
        activos = len(g["activos"])
        # Un día con una sola señal no constituye validación temporal.
        dias_con_muestra = sum(len(v) >= 10 for v in g["por_dia"].values())
        suficiente = dias >= minimo_dias and activos >= minimo_activos and dias_con_muestra >= minimo_dias
        # El agregado no puede ocultar un día con menos del objetivo.
        supera_59_cada_dia = bool(g["por_dia"]) and all(
            len(v) >= 10 and sum(v) * 100.0 / len(v) >= OBJETIVO_WINRATE_MINIMO
            for v in g["por_dia"].values()
        )
        supera_59 = (suficiente and 100.0 * g["wins"] / n >= OBJETIVO_WINRATE_MINIMO
                     and supera_59_cada_dia)
        salida.append({
            "factor": factor, "valor": valor, "n": n, "wins_hipoteticos": g["wins"],
            "wr_hipotetico": round(g["wins"] * 100 / n, 2),
            "wilson_inferior_95": round(100*_wilson_inferior(g["wins"], n), 2),
            "dias": dias, "dias_con_muestra": dias_con_muestra,
            "activos": activos, "minutos": len(g["minutos"]),
            "cobertura_temporal_suficiente": suficiente,
            "objetivo_59_sostenido_en_dias": supera_59,
            "candidato_productivo": False,
        })
    return sorted(salida, key=lambda r: (-r["n"], r["factor"], r["valor"])), excluidos


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Factores de canceladas, sin autoridad productiva")
    parser.add_argument("csv")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        grupos, excluidos = analizar_factores_cancelados(csv.DictReader(archivo))
    print("EXCLUIDOS:", excluidos)
    for grupo in grupos:
        print(grupo)


if __name__ == "__main__":
    main()
