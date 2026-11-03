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



def resumir_contexto_temporal(velas, latencias, profundidad=24):
    """Cuenta cierres con historial consecutivo verdaderamente recibido a tiempo.

    No declara paridad de decisiones ni convierte cierres en operaciones.
    """
    if type(profundidad) is not int or profundidad < 1:
        raise ValueError("PROFUNDIDAD_INVALIDA")
    from contexto_mercado_fresco import consolidar_minutos

    minutos = consolidar_minutos(velas)
    elegibles = set()
    for minuto in minutos:
        fin = minuto["end"]
        if all(
            t in latencias and type(latencias[t]) is int
            and latencias[t] >= 0 and t + 1 + latencias[t] <= fin
            for t in range(fin - 60, fin)
        ):
            elegibles.add(fin)
    racha = 0
    mayor = 0
    con_contexto = 0
    anterior = None
    for minuto in minutos:
        fin = minuto["end"]
        if fin in elegibles:
            racha = (racha + 1 if anterior == fin - 60 else 1)
            mayor = max(mayor, racha)
            if racha >= profundidad:
                con_contexto += 1
        else:
            racha = 0
        anterior = fin
    return {
        "profundidad_minutos": profundidad,
        "cierres_temporalmente_elegibles": len(elegibles),
        "racha_maxima_cierres_elegibles": mayor,
        "cierres_con_contexto_temporal_verificado": con_contexto,
        "operaciones_autorizadas": False,
    }



def resumir_arbitro_flujo(velas, latencias, profundidad=24):
    """Diagnostica el arbitro REALMENTE observable en flujo, no replay.

    Solo cuenta candidatos generados por el arbitro original. Que un cierre
    tenga contexto temporal suficiente no constituye una senal ni un WIN.
    """
    from collections import Counter
    llegadas = sorted(
        ((t + 1 + latencias[t], dict(vela)) for t, vela in velas.items()),
        key=lambda par: (par[0], int(par[1]["from"])),
    )
    cierres = evaluar_flujo(llegadas)
    motivos = Counter()
    estados = Counter()
    candidatos = []
    validos_por_fin = {fin for fin, _ in cierres}
    # El historial disponible en el flujo debe ser continuo y observable.
    racha = 0
    anterior = None
    ventanas_verificadas = 0
    for fin, diagnostico in cierres:
        racha = racha + 1 if anterior == fin - 60 else 1
        anterior = fin
        contexto_verificado = racha >= profundidad
        ventanas_verificadas += contexto_verificado
        arbitraje = diagnostico["arbitraje"]
        if arbitraje["operable"] is not False:
            raise RuntimeError("ARBITRO_FLUJO_AUTORIZO_OPERACION")
        motivos[arbitraje["motivo"]] += 1
        estados[arbitraje["estado"]] += 1
        if arbitraje["estado"] == "CANDIDATO_SOMBRA_NO_OPERABLE":
            candidatos.append({
                "timestamp_cierre": fin,
                "direccion": arbitraje["direccion"],
                "estrategias": list(arbitraje["estrategias"]),
                "contexto_24_min_verificado": contexto_verificado,
                "operable": False,
            })
    return {
        "cierres_flujo": len(cierres),
        "cierres_temporales_distintos": len(validos_por_fin),
        "ventanas_contexto_verificadas": ventanas_verificadas,
        "estados_arbitro": dict(sorted(estados.items())),
        "motivos_arbitro": dict(sorted(motivos.items())),
        "candidatos_sombra_totales": len(candidatos),
        "candidatos_con_contexto_temporal_verificado": sum(
            c["contexto_24_min_verificado"] for c in candidatos
        ),
        "candidatos": candidatos,
        "resultados_win_loss_verificados": None,
        "payouts_preentrada_verificados": None,
        "operaciones_autorizadas": False,
        "advertencia": "VENTANA_VALIDADA_NO_ES_SENAL; CANDIDATO_NO_ES_WIN",
    }


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
        "contexto_temporal": resumir_contexto_temporal(velas, latencias),
        "arbitro_flujo": resumir_arbitro_flujo(velas, latencias),
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
