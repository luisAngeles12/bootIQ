"""Contraste pasivo F3: autorización por estimación vs intervalo inferior.

La comparación es contrafactual, NO cambia umbrales ni órdenes. Nunca
convierte resultados hipotéticos en PNL ejecutado o permiso de trading.
"""
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite, sqrt


UMBRALES = {"OPERAR_SOMBRA": 55.0, "OPERAR_CON_PROTOCOLO_SOMBRA": 50.0}


def _numero(valor):
    try:
        n = float(valor)
        return n if isfinite(n) else None
    except (ValueError, TypeError):
        return None


def _dia_utc(fila):
    valor = fila.get("fecha_senal") or fila.get("fecha")
    try:
        marca = float(valor)
        return datetime.fromtimestamp(marca, timezone.utc).date().isoformat() if isfinite(marca) else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _wilson_inferior(w, n):
    if n == 0:
        return None
    z = 1.96
    p = w / n
    return 100 * (p + z*z/(2*n) - z*sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1 + z*z/n)


def contrastar_intervalo_cerebro(filas):
    """Solo señales autorizadas estadísticamente y resultados hipotéticos."""
    grupos = defaultdict(lambda: {"n": 0, "wins": 0, "losses": 0,
                                  "dias": set(), "activos": set()})
    descartes = defaultdict(int)
    identidades = set()
    for fila in filas:
        if not isinstance(fila, dict):
            descartes["FILA_INVALIDA"] += 1
            continue
        decision = str(fila.get("decision_estadistica_sombra") or "").upper().strip()
        if decision not in UMBRALES:
            descartes["NO_AUTORIZADA_ESTADISTICAMENTE"] += 1
            continue
        resultado = str(fila.get("resultado_hipotetico") or "").upper().strip()
        if resultado not in {"WIN", "LOSS"}:
            descartes["SIN_RESULTADO_HIPOTETICO"] += 1
            continue
        punto = _numero(fila.get("probabilidad_estimada"))
        inferior = _numero(fila.get("intervalo_probabilidad_inferior"))
        muestra = _numero(fila.get("muestra_probabilidad"))
        if (punto is None or inferior is None or muestra is None or muestra <= 0
                or not 0 <= inferior <= punto <= 100):
            descartes["INTERVALO_O_MUESTRA_INVALIDA"] += 1
            continue
        identidad = (fila.get("fecha_senal") or fila.get("fecha"),
                     fila.get("activo"), fila.get("patron"), fila.get("direccion"))
        if all(x not in (None, "") for x in identidad):
            if identidad in identidades:
                raise ValueError("Señal repetida en contraste estadístico")
            identidades.add(identidad)
        umbral = UMBRALES[decision]
        if punto < umbral:
            descartes["DECISION_INCOHERENTE_CON_UMBRAL"] += 1
            continue
        grupo = "INTERVALO_SOSTIENE_UMBRAL" if inferior >= umbral else "SOLO_ESTIMACION_PUNTUAL"
        registro = grupos[(decision, grupo)]
        registro["n"] += 1
        registro["wins"] += resultado == "WIN"
        registro["losses"] += resultado == "LOSS"
        dia = _dia_utc(fila)
        if dia:
            registro["dias"].add(dia)
        if fila.get("activo"):
            registro["activos"].add(str(fila["activo"]))
    salida = {}
    for (decision, grupo), g in sorted(grupos.items()):
        n = g["n"]
        salida[decision + "|" + grupo] = {
            "n": n, "wins_hipoteticos": g["wins"], "losses_hipoteticas": g["losses"],
            "wr_hipotetico": round(100*g["wins"]/n, 2),
            "wilson_inferior_95": round(_wilson_inferior(g["wins"], n), 2),
            "dias_utc": len(g["dias"]), "activos_distintos": len(g["activos"]),
            "autoriza_cambio": False,
        }
    return {"cohortes": salida, "descartes": dict(descartes),
            "advertencia": "RESULTADOS_HIPOTETICOS_NO_ORDENES_NI_PNL",
            "autoriza_operaciones": False}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="CSV oficial existente, solo lectura")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        print(json.dumps(contrastar_intervalo_cerebro(csv.DictReader(archivo)),
                         ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
