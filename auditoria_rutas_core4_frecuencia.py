"""Auditoría pasiva de capacidad CORE4: rutas, vetos y tamaño de muestra.

No elimina vetos, no cambia autoridad, no cuenta resultados cancelados
como operaciones ejecutadas.
"""
import csv
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt


def _verdadero(v):
    return v is True or str(v).strip().lower() == "true"


def _dia(fila):
    try:
        ts = int(float(fila.get("fecha_senal") or fila.get("fecha")))
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def _wilson_min(w, n):
    if not n:
        return 0.0
    z = 1.96
    p = w/n
    return 100*(p + z*z/(2*n) - z*sqrt((p*(1-p)+z*z/(4*n))/n))/(1+z*z/n)


def auditar_rutas_core4(filas, objetivo=59.0, minimo_operadas=30, minimo_dias=3):
    grupos = defaultdict(lambda: {"senales": 0, "operadas": 0, "canceladas_cerebro": 0,
                                  "canceladas_protocolo": 0, "win_ejecutadas_backtest": 0,
                                  "loss_ejecutadas_backtest": 0, "win_hipoteticas_veto": 0,
                                  "loss_hipoteticas_veto": 0, "dias_operadas": set(),
                                  "activos_operados": set()})
    sin_match = 0
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        if not _verdadero(fila.get("core4_match_previo")):
            sin_match += 1
            continue
        reglas = str(fila.get("core4_reglas_previas") or fila.get("core4_reglas") or "SIN_REGLA")
        invalida = _verdadero(fila.get("core4_invalidacion_dura_previa")) or _verdadero(
            fila.get("core4_invalidacion_selectiva_previa")
        )
        clase = "VETO" if invalida else "SIN_VETO"
        g = grupos[(reglas, clase)]
        g["senales"] += 1
        estado = str(fila.get("estado_operacion") or "").upper()
        res = str(fila.get("resultado_hipotetico") or "").upper()
        if estado.startswith("OPERADA_"):
            g["operadas"] += 1
            # La etiqueta hipotética del replay es observación de backtest,
            # no ejecución de broker real.
            if res == "WIN":
                g["win_ejecutadas_backtest"] += 1
            elif res == "LOSS":
                g["loss_ejecutadas_backtest"] += 1
            dia = _dia(fila)
            if dia:
                g["dias_operadas"].add(dia)
            if fila.get("activo"):
                g["activos_operados"].add(str(fila["activo"]))
        elif estado == "CANCELADA_CEREBRO":
            g["canceladas_cerebro"] += 1
            if res == "WIN":
                g["win_hipoteticas_veto"] += 1
            elif res == "LOSS":
                g["loss_hipoteticas_veto"] += 1
        elif estado == "CANCELADA_PROTOCOLO":
            g["canceladas_protocolo"] += 1
    resultado = {}
    for (reglas, clase), g in sorted(grupos.items()):
        n = g["win_ejecutadas_backtest"] + g["loss_ejecutadas_backtest"]
        dias = len(g["dias_operadas"])
        suficiente = (n >= minimo_operadas and dias >= minimo_dias)
        wr = 100 * g["win_ejecutadas_backtest"] / n if n else None
        resultado[(reglas, clase)] = {
            **{k:v for k,v in g.items() if not isinstance(v,set)},
            "dias_operadas": dias, "activos_operados": len(g["activos_operados"]),
            "winrate_operadas_backtest": round(wr,2) if wr is not None else None,
            "limite_inferior_wilson_95": round(_wilson_min(g["win_ejecutadas_backtest"],n),2),
            "cumple_objetivo_y_cobertura": bool(suficiente and wr is not None and wr >= objetivo),
            "autoriza_modificar_veto": False,
        }
    return resultado, sin_match


def main():
    import argparse
    p=argparse.ArgumentParser(description="Análisis CORE4 solo lectura")
    p.add_argument("csv")
    args=p.parse_args()
    with open(args.csv,encoding="utf-8-sig",newline="") as f:
        rutas,sin_match=auditar_rutas_core4(csv.DictReader(f))
    print("SIN_MATCH",sin_match)
    for ruta,detalle in rutas.items():
        print(ruta,detalle)


if __name__=="__main__":
    main()
