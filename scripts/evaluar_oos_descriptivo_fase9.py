"""R9-14: rendimiento DESCRIPTIVO del tramo temporal posterior, solo lectura.

No reconstruye una politica contrafactual, no valida el Cerebro V3, no
modifica memoria ni conecta al broker. Solo informa resultados observados.
Exige separacion local sin fuga antes de calcular ventanas posteriores.
"""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from scripts.auditar_historial_fase9 import _fecha_iso, _txt, _cierre_explicito
from scripts.auditar_particion_temporal_fase9 import auditar_particion


def _metricas(bloque):
    pnl = [v[2] for v in bloque]
    n = len(pnl)
    wins = sum(x > 0 for x in pnl)
    losses = sum(x < 0 for x in pnl)
    positivos = sum(x for x in pnl if x > 0)
    negativos = -sum(x for x in pnl if x < 0)
    neto = sum(pnl)
    return {
        "operaciones": n,
        "ganadas": wins,
        "perdidas": losses,
        "winrate_pct": round(100 * wins / n, 2) if n else None,
        "neto": round(neto, 2),
        "expectativa_por_operacion": round(neto / n, 4) if n else None,
        "profit_factor": round(positivos / negativos, 4) if negativos else None,
        "cumple_60_y_neto_positivo": n == 20 and wins >= 12 and neto > 0,
    }


def evaluar_oos(ruta, minimo_train=20, minimo_oos=20):
    corte = auditar_particion(
        ruta, minimo_train=minimo_train, minimo_oos=minimo_oos
    )
    base = {
        "estado": "NO_APTO",
        "tipo": "DESCRIPTIVO_HISTORICO_NO_VALIDA_POLITICA_V3",
        "corte": corte,
        "memoria_generada": False,
        "habilita_trading": False,
    }
    if corte["estado"] != "PRELIMINAR_NO_VERIFICADO_IQ":
        return {**base, "causa": "PARTICION_INVALIDA"}
    if not corte["separacion_local_sin_fuga"]:
        return {**base, "causa": "RESULTADOS_TRAIN_NO_CONOCIDOS_ANTES_DE_OOS"}
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        rows = list(csv.DictReader(archivo))
    inicio = datetime.fromisoformat(corte["inicio_oos_utc"])
    oos = []
    for f in rows:
        apertura_iso = _fecha_iso(f.get("fecha"))
        if apertura_iso is None:
            continue
        apertura = datetime.fromisoformat(apertura_iso)
        if apertura.tzinfo is None or apertura.utcoffset() is None:
            continue
        apertura = apertura.astimezone(timezone.utc)
        if apertura < inicio:
            continue
        if _txt(f.get("modo_cuenta_configurado")) != "PRACTICE":
            continue
        if not _cierre_explicito(_txt(f.get("estado"))):
            continue
        try:
            pnl = float(f.get("resultado"))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(pnl) or pnl == 0:
            continue
        cierre_iso = _fecha_iso(f.get("fecha_conciliacion_local_utc"))
        if cierre_iso is None:
            return {**base, "causa": "OOS_SIN_MARCA_CONCILIACION"}
        cierre = datetime.fromisoformat(cierre_iso)
        if cierre.tzinfo is None or cierre.utcoffset() is None:
            return {**base, "causa": "OOS_CIERRE_SIN_ZONA"}
        if cierre.astimezone(timezone.utc) < apertura:
            return {**base, "causa": "OOS_CIERRE_ANTERIOR_APERTURA"}
        oos.append((apertura, str(f["order_id"]).strip(), pnl,
                    _txt(f.get("origen_autoridad")) or "SIN_AUTORIDAD"))
    oos.sort(key=lambda v: (v[0], v[1]))
    if len(oos) != corte["oos"] or len({x[1] for x in oos}) != len(oos):
        return {**base, "causa": "OOS_INCONSISTENTE_CON_PARTICION"}
    if len(oos) < 20:
        return {**base, "causa": "SIN_BLOQUE_COMPLETO_20"}
    bloques = []
    for i in range(0, len(oos) - 19, 20):
        bloques.append({"desde": i + 1, "hasta": i + 20,
                        **_metricas(oos[i:i + 20])})
    ventanas = [_metricas(oos[i:i + 20]) for i in range(len(oos) - 19)]
    cumple = all(b["cumple_60_y_neto_positivo"] for b in bloques)
    cumple_movil = all(b["cumple_60_y_neto_positivo"] for b in ventanas)
    autoridades = sorted({x[3] for x in oos})
    return {
        **base, "estado": "DESCRIPTIVO_NO_VERIFICADO_BROKER",
        "oos_operaciones": len(oos),
        "bloques_20_no_solapados": bloques,
        "ventanas_moviles_20": len(ventanas),
        "ventanas_moviles_20_que_cumplen": sum(
            b["cumple_60_y_neto_positivo"] for b in ventanas
        ),
        "cumple_todos_bloques_20": cumple,
        "cumple_todas_ventanas_moviles_20": cumple_movil,
        "autoridades_observadas": autoridades,
        "conclusion": (
            "Metricas descriptivas sobre autorizaciones historicas, "
            "NO validacion OOS de una politica entrenada o de V3."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    print(json.dumps(evaluar_oos(args.historial), indent=2,
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
