"""Auditoria de cobertura y decisiones sombra sobre CSV PRACTICE ya capturado.

No conecta al broker, no importa credenciales y nunca autoriza ordenes.
Replay historico y flujo causal NO son intercambiables si hubo recepciones tardias.
"""
import argparse
import csv
from pathlib import Path

from paridad_sombra_practice import (
    reproducir_cierres,
    evaluar_flujo,
    comprobar_paridad_recepcion_1s,
)

COLUMNAS = (
    "activo", "timestamp_utc", "open", "high", "low", "close",
    "latencia_primera_recepcion_s",
)


def cargar_captura(ruta):
    """Lee OHLC y latencia observada: no fabrica tiempos faltantes."""
    velas, latencias = {}, {}
    activo = None
    with Path(ruta).open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if not lector.fieldnames or any(c not in lector.fieldnames for c in COLUMNAS):
            raise ValueError("COLUMNAS_DE_CAPTURA_INCOMPLETAS")
        for fila in lector:
            nombre = fila["activo"]
            if not nombre or (activo is not None and nombre != activo):
                raise ValueError("ACTIVOS_MEZCLADOS")
            activo = nombre
            t = int(fila["timestamp_utc"])
            if t in velas:
                raise ValueError("TIMESTAMP_DUPLICADO")
            demora = int(fila["latencia_primera_recepcion_s"])
            if demora < 0:
                raise ValueError("LATENCIA_INVALIDA")
            velas[t] = {
                "from": t,
                "open": float(fila["open"]),
                "max": float(fila["high"]),
                "min": float(fila["low"]),
                "close": float(fila["close"]),
            }
            latencias[t] = demora
    if not velas:
        raise ValueError("CAPTURA_VACIA")
    marcas = sorted(velas)
    if any(b - a != 1 for a, b in zip(marcas, marcas[1:])):
        raise ValueError("HUECOS_EN_CAPTURA")
    return velas, latencias


def auditar_decisiones(velas, latencias):
    """Compara cada cierre causal con su replay sin forzar igualdad artificial."""
    cobertura = comprobar_paridad_recepcion_1s(velas, latencias)
    if cobertura["paridad"] is None:
        return {"estado": "EVIDENCIA_TEMPORAL_INVALIDA",
                "cobertura": cobertura, "operaciones_autorizadas": False}
    historico = dict(reproducir_cierres(velas))
    llegadas = sorted(
        ((t + 1 + latencias[t], dict(vela)) for t, vela in velas.items()),
        key=lambda par: (par[0], int(par[1]["from"])),
    )
    flujo = dict(evaluar_flujo(llegadas))
    distintos = [fin for fin in sorted(flujo) if historico[fin] != flujo[fin]]
    contextos = [fin for fin in distintos
                 if historico[fin]["contexto"] != flujo[fin]["contexto"]]
    candidatos = [fin for fin in distintos
                  if historico[fin]["candidatos"] != flujo[fin]["candidatos"]]
    arbitros = [fin for fin in distintos
                if historico[fin]["arbitraje"] != flujo[fin]["arbitraje"]]
    return {
        "estado": ("PARIDAD_DECISIONES_COMPLETA"
                   if cobertura["paridad"] is True else "PARIDAD_DECISIONES_NO_DEMOSTRADA"),
        "velas": len(velas),
        "cierres_replay": len(historico),
        "cierres_flujo": len(flujo),
        "cierres_replay_excluidos": sorted(set(historico) - set(flujo)),
        "coincidencia_cierres_elegibles": cobertura["coincidencia_cierres_elegibles"],
        "decisiones_iguales_sobre_flujo": len(flujo) - len(distintos),
        "decisiones_diferentes_sobre_flujo": len(distintos),
        "contextos_diferentes": len(contextos),
        "candidatos_diferentes": len(candidatos),
        "arbitros_diferentes": len(arbitros),
        "cierres_decisiones_diferentes": distintos,
        "cierres_contextos_diferentes": contextos,
        "cierres_arbitros_diferentes": arbitros,
        "operaciones_autorizadas": False,
        "advertencia": "DIFERENCIA_CAUSAL_NO_ES_DEFECTO_AUTOMATICO_NI_WINRATE",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_practice", help="Captura PRACTICE existente de 1 segundo")
    args = parser.parse_args()
    velas, latencias = cargar_captura(args.csv_practice)
    print(auditar_decisiones(velas, latencias))


if __name__ == "__main__":
    main()
