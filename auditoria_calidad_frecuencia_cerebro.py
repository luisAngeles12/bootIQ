"""Embudo pasivo de calidad y frecuencia del cerebro V3.

Las operaciones son estados del backtest, no órdenes colocadas en broker.
El umbral diagnóstico 59% NO bloquea señales ni gobierna la ejecución.
"""
import csv
from collections import defaultdict
from datetime import datetime, timezone


OBJETIVO_WR_FUERA_MUESTRA = 59.0


def _dia_y_minuto(fila):
    valor = fila.get("fecha_senal") or fila.get("fecha")
    try:
        ts = int(float(valor))
        if ts <= 0:
            return "SIN_FECHA", None
        return datetime.fromtimestamp(ts, timezone.utc).date().isoformat(), ts // 60
    except (ValueError, TypeError, OverflowError, OSError):
        return "SIN_FECHA", None


def _probabilidad(fila):
    try:
        valor = float(fila.get("probabilidad_estimada"))
        return valor if 0 <= valor <= 100 else None
    except (TypeError, ValueError):
        return None


def resumir_frecuencia_cerebro(filas):
    grupos = defaultdict(lambda: {"senales": 0, "operadas_backtest": 0,
                                  "canceladas_cerebro": 0, "canceladas_protocolo": 0,
                                  "otros_estados": 0, "predicciones_con_dato": 0,
                                  "predicciones_ge59": 0,
                                  "minutos_con_senal": set(), "activos_con_senal": set()})
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        dia, minuto = _dia_y_minuto(fila)
        g = grupos[dia]
        g["senales"] += 1
        if minuto is not None:
            g["minutos_con_senal"].add(minuto)
        if fila.get("activo"):
            g["activos_con_senal"].add(str(fila["activo"]))
        estado = str(fila.get("estado_operacion") or "").upper()
        if estado.startswith("OPERADA_"):
            g["operadas_backtest"] += 1
        elif estado == "CANCELADA_CEREBRO":
            g["canceladas_cerebro"] += 1
        elif estado == "CANCELADA_PROTOCOLO":
            g["canceladas_protocolo"] += 1
        else:
            g["otros_estados"] += 1
        prob = _probabilidad(fila)
        if prob is not None:
            g["predicciones_con_dato"] += 1
            if prob >= OBJETIVO_WR_FUERA_MUESTRA:
                g["predicciones_ge59"] += 1
    salida = {}
    for dia, g in sorted(grupos.items()):
        n = g["senales"]
        minutos = len(g["minutos_con_senal"])
        salida[dia] = {
            "senales": n, "operadas_backtest": g["operadas_backtest"],
            "canceladas_cerebro": g["canceladas_cerebro"],
            "canceladas_protocolo": g["canceladas_protocolo"],
            "otros_estados": g["otros_estados"],
            "activos_con_senal": len(g["activos_con_senal"]),
            "minutos_con_senal": minutos,
            "operadas_por_100_senales": round(100 * g["operadas_backtest"] / n, 2) if n else 0,
            "operadas_por_100_minutos_con_senal": (
                round(100 * g["operadas_backtest"] / minutos, 2) if minutos else None
            ),
            "predicciones_con_dato": g["predicciones_con_dato"],
            "predicciones_ge59": g["predicciones_ge59"],
            "payout_y_pnl_no_evaluables": True,
        }
    return salida


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Embudo backtest, solo lectura")
    parser.add_argument("csv")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        resumen = resumir_frecuencia_cerebro(csv.DictReader(archivo))
    for dia, datos in resumen.items():
        print(dia, datos)


if __name__ == "__main__":
    main()
