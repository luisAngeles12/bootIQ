"""Evalua interacciones estrategia/contexto con reserva temporal PRACTICE.

La seleccion usa exclusivamente TRAIN; TEST se informa aunque contradiga la
hipotesis. No conecta broker, no modifica memoria ni autoriza operaciones.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from analizar_oportunidades_integrales_practice import _features, _metrics, _norm, _number

CONTEXTO = (
    "tipo_mercado", "regimen_mercado", "calidad_mercado", "estado_tendencia",
    "accion_precio", "pa_tipo", "rsi_zona", "ema_direccion", "bb_ubicacion",
    "vela_senal_cuerpo", "direccion_contra_tendencia", "riesgo_nivel",
    "protocolo_sugerido",
)


def _limpiar(filas):
    ordenes = {}
    excluidos = Counter()
    for fila in filas:
        if _norm(fila.get("modo_cuenta_configurado")) != "PRACTICE":
            excluidos["NO_PRACTICE"] += 1
            continue
        if _norm(fila.get("estado")) != "CERRADA":
            excluidos["NO_CERRADA"] += 1
            continue
        if _norm(fila.get("estado_operacion")) not in ("OPERADA_DIRECTA", "OPERADA_PROTOCOLO"):
            excluidos["NO_OPERADA"] += 1
            continue
        oid = str(fila.get("order_id") or "").strip()
        pnl = _number(fila.get("resultado"))
        try:
            fecha = datetime.fromisoformat(str(fila.get("fecha") or "").replace("Z", "+00:00"))
        except (TypeError, ValueError):
            fecha = None
        if not oid or pnl is None or fecha is None:
            excluidos["IDENTIDAD_RESULTADO_O_FECHA_INVALIDOS"] += 1
            continue
        if oid in ordenes:
            excluidos["ORDER_ID_REPETIDO"] += 1
            # No decidir arbitrariamente entre dos cierres conflictivos.
            ordenes[oid] = None
            continue
        if pnl == 0:
            excluidos["EMPATE"] += 1
            continue
        ordenes[oid] = {
            "order_id": oid, "fecha": fecha, "pnl": pnl,
            "patron": _norm(fila.get("patron")),
            "autoridad": _norm(fila.get("origen_autoridad")),
            "activo": _norm(fila.get("activo")),
            "f": _features(fila),
        }
    datos = [r for r in ordenes.values() if r is not None]
    if len({r["fecha"].tzinfo is None for r in datos}) > 1:
        raise ValueError("FECHAS_CON_ZONAS_MIXTAS")
    datos.sort(key=lambda r: (r["fecha"], r["order_id"]))
    return datos, dict(sorted(excluidos.items()))


def _resumen_por(grupo, atributo, min_n=1):
    buckets = defaultdict(list)
    for row in grupo:
        buckets[row[atributo]].append(row)
    return [
        {"valor": valor, **_metrics(filas)}
        for valor, filas in sorted(buckets.items())
        if len(filas) >= min_n
    ]


def _contextos_train(rows, min_n):
    """Primero se exige comparar dentro de la MISMA estrategia."""
    por_patron = defaultdict(list)
    for row in rows:
        por_patron[row["patron"]].append(row)
    candidatos = []
    for patron, grupo in por_patron.items():
        if len(grupo) < 2 * min_n:
            continue
        referencia = _metrics(grupo)
        for key in CONTEXTO:
            buckets = defaultdict(list)
            for r in grupo:
                value = r["f"].get(key, "SIN_DATO")
                if value != "SIN_DATO":
                    buckets[value].append(r)
            for value, subgrupo in buckets.items():
                # Exige muestra en ambos lados: no se puede confundir
                # un patron entero con el efecto de un indicador.
                if len(subgrupo) < min_n or len(grupo) - len(subgrupo) < min_n:
                    continue
                m = _metrics(subgrupo)
                delta = m["expectativa_por_operacion"] - referencia["expectativa_por_operacion"]
                candidatos.append({
                    "patron": patron, "variable": key, "valor": value,
                    "train": m, "referencia_estrategia_train": referencia,
                    "diferencia_expectativa_train": round(delta, 4),
                })
    candidatos.sort(key=lambda x: (-x["diferencia_expectativa_train"],
                                    -x["train"]["n"], x["patron"], x["variable"], x["valor"]))
    return candidatos


def analizar_contextos(filas, min_train=20, min_test=20):
    if min_train < 2 or min_test < 2:
        raise ValueError("MINIMOS_DEBEN_SER_MAYORES_O_IGUALES_A_DOS")
    datos, excluidos = _limpiar(filas)
    dias = sorted({r["fecha"].date().isoformat() for r in datos})
    base = {
        "modo": "ANALISIS_INTERACCIONES_PRACTICE_NO_OPERABLE",
        "operaciones_cerradas_validas": len(datos),
        "descartes": excluidos,
        "dias_observados": len(dias),
        "baseline_global": _metrics(datos),
        "por_estrategia_global": _resumen_por(datos, "patron"),
        "por_autoridad_global": _resumen_por(datos, "autoridad"),
        "por_activo_global": _resumen_por(datos, "activo"),
        "autoriza_operaciones": False,
        "modifica_cerebro": False,
    }
    if len(dias) < 2:
        return {**base, "estado": "SIN_VALIDACION_TEMPORAL", "hipotesis": None}
    # Dias completos: no dividir operaciones del mismo dia entre TRAIN y TEST.
    corte = dias[max(0, int(len(dias) * 0.7) - 1)]
    train = [r for r in datos if r["fecha"].date().isoformat() <= corte]
    test = [r for r in datos if r["fecha"].date().isoformat() > corte]
    candidatos = _contextos_train(train, min_train)
    elegido = candidatos[0] if candidatos else None
    if elegido is not None:
        patron = elegido["patron"]
        ref = [r for r in test if r["patron"] == patron]
        sub = [r for r in ref if r["f"].get(elegido["variable"]) == elegido["valor"]]
        m, ref_m = _metrics(sub), _metrics(ref)
        suficiente = len(sub) >= min_test and len(ref) - len(sub) >= min_test
        delta = (round(m["expectativa_por_operacion"] - ref_m["expectativa_por_operacion"], 4)
                 if sub and ref else None)
        elegido = {
            **elegido,
            "test": m, "referencia_estrategia_test": ref_m,
            "diferencia_expectativa_test": delta,
            "muestra_oos_suficiente_en_ambos_lados": suficiente,
            "replica_mejora_oos": bool(suficiente and delta is not None and delta > 0
                                     and m["neto"] > 0 and m["winrate_pct"] >= 60),
            "recomendacion": "HIPOTESIS_PARA_VALIDACION_PROSPECTIVA",
        }
    return {
        **base, "estado": "COMPARACION_TEMPORAL_NO_CAUSAL",
        "corte_train_inclusivo": corte, "train": _metrics(train),
        "test_global": _metrics(test),
        "candidatos_evaluados_solo_en_train": len(candidatos),
        "hipotesis": elegido,
        "advertencias": [
            "Solo operaciones ejecutadas; no se observan resultados contrafactuales de señales descartadas.",
            "Seleccion entre muchos candidatos puede sobreajustar TRAIN.",
            "Una reserva temporal no sustituye validaciones prospectivas independientes.",
            "Si un grupo no tiene muestra en ambos lados de TEST, no hay evidencia para cambiar entradas.",
            "Sin evidencia causal no se cambia ningun umbral, bloqueo ni permiso.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    parser.add_argument("--min-train", type=int, default=20)
    parser.add_argument("--min-test", type=int, default=20)
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as handle:
        result = analizar_contextos(csv.DictReader(handle), args.min_train, args.min_test)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
