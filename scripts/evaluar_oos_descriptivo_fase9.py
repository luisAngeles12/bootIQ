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
from scripts.conciliar_exportacion_iq_fase9 import conciliar_exportacion


def _metricas(bloque):
    pnl = [v[2] for v in bloque]
    n = len(pnl)
    wins = sum(x > 0 for x in pnl)
    losses = sum(x < 0 for x in pnl)
    positivos = sum(x for x in pnl if x > 0)
    negativos = -sum(x for x in pnl if x < 0)
    neto = sum(pnl)
    # Drawdown de PNL acumulado, con capital inicial abstracto 0.
    # No confundir con drawdown porcentual de la cuenta PRACTICE.
    acumulado = 0.0
    maximo = 0.0
    drawdown = 0.0
    racha_perdidas = 0
    peor_racha = 0
    for x in pnl:
        acumulado += x
        maximo = max(maximo, acumulado)
        drawdown = max(drawdown, maximo - acumulado)
        racha_perdidas = racha_perdidas + 1 if x < 0 else 0
        peor_racha = max(peor_racha, racha_perdidas)
    return {
        "operaciones": n,
        "ganadas": wins,
        "perdidas": losses,
        "winrate_pct": round(100 * wins / n, 2) if n else None,
        "neto": round(neto, 2),
        "expectativa_por_operacion": round(neto / n, 4) if n else None,
        "profit_factor": round(positivos / negativos, 4) if negativos else None,
        "drawdown_maximo_unidades": round(drawdown, 2),
        "racha_maxima_perdidas": peor_racha,
        "cumple_60_y_neto_positivo": n == 20 and wins >= 12 and neto > 0,
    }


def evaluar_oos(ruta, minimo_train=20, minimo_oos=20, exportacion_iq=None):
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
    # La selección de registros no debe borrar silenciosamente empates
    # o cierres no resueltos del tramo posterior para fabricar bloques de 20.
    excluidos_tramo = {}
    for f in rows:
        marca_utc = str(f.get("fecha_apertura_registro_local_utc") or "").strip()
        apertura_iso = _fecha_iso(marca_utc if marca_utc else f.get("fecha"))
        if apertura_iso is None:
            if marca_utc:
                return {**base, "causa": "OOS_APERTURA_UTC_INVALIDA"}
            continue
        apertura = datetime.fromisoformat(apertura_iso)
        if apertura.tzinfo is None or apertura.utcoffset() is None:
            if marca_utc:
                return {**base, "causa": "OOS_APERTURA_UTC_SIN_ZONA"}
            continue
        apertura = apertura.astimezone(timezone.utc)
        if apertura < inicio:
            continue
        if _txt(f.get("modo_cuenta_configurado")) != "PRACTICE":
            continue
        if not _cierre_explicito(_txt(f.get("estado"))):
            excluidos_tramo["NO_CERRADA"] = excluidos_tramo.get("NO_CERRADA", 0) + 1
            continue
        try:
            pnl = float(f.get("resultado"))
        except (TypeError, ValueError, OverflowError):
            excluidos_tramo["PNL_INVALIDO"] = excluidos_tramo.get("PNL_INVALIDO", 0) + 1
            continue
        if not math.isfinite(pnl):
            excluidos_tramo["PNL_NO_FINITO"] = excluidos_tramo.get("PNL_NO_FINITO", 0) + 1
            continue
        if pnl == 0:
            excluidos_tramo["EMPATE_EXCLUIDO"] = excluidos_tramo.get("EMPATE_EXCLUIDO", 0) + 1
            continue
        cierre_iso = _fecha_iso(f.get("fecha_conciliacion_local_utc"))
        if cierre_iso is None:
            return {**base, "causa": "OOS_SIN_MARCA_CONCILIACION"}
        cierre = datetime.fromisoformat(cierre_iso)
        if cierre.tzinfo is None or cierre.utcoffset() is None:
            return {**base, "causa": "OOS_CIERRE_SIN_ZONA"}
        if cierre.astimezone(timezone.utc) < apertura:
            return {**base, "causa": "OOS_CIERRE_ANTERIOR_APERTURA"}
        familia = _txt(f.get("familia_setup")) or "SIN_FAMILIA"
        oos.append((apertura, str(f["order_id"]).strip(), pnl,
                    _txt(f.get("origen_autoridad")) or "SIN_AUTORIDAD",
                    familia))
    oos.sort(key=lambda v: (v[0], v[1]))
    if excluidos_tramo:
        return {
            **base, "causa": "OOS_CON_RESULTADOS_OMITIDOS",
            "exclusiones_oos": dict(sorted(excluidos_tramo.items())),
            "operaciones_oos_evaluadas": 0,
        }
    if len(oos) != corte["oos"] or len({x[1] for x in oos}) != len(oos):
        return {**base, "causa": "OOS_INCONSISTENTE_CON_PARTICION"}
    if len(oos) < 20:
        return {**base, "causa": "SIN_BLOQUE_COMPLETO_20"}
    cotejo = None
    if exportacion_iq is not None:
        # Un match offline no certifica el origen de un CSV supuesto IQ,
        # pero una discrepancia impide publicar métricas como consistentes.
        cotejo = conciliar_exportacion(
            ruta, exportacion_iq, ids_objetivo={x[1] for x in oos}
        )
        if not cotejo.get("objetivo_oos_conciliado_completo", False):
            return {
                **base, "causa": "OOS_DIFIERE_BROKER_OFFLINE",
                "cotejo_offline": cotejo,
            }
    bloques = []
    for i in range(0, len(oos) - 19, 20):
        bloques.append({"desde": i + 1, "hasta": i + 20,
                        **_metricas(oos[i:i + 20])})
    ventanas = [_metricas(oos[i:i + 20]) for i in range(len(oos) - 19)]
    cumple = all(b["cumple_60_y_neto_positivo"] for b in bloques)
    cumple_movil = all(b["cumple_60_y_neto_positivo"] for b in ventanas)
    autoridades = sorted({x[3] for x in oos})
    resumen = _metricas(oos)
    restantes = len(oos) % 20
    conteos_familias = {}
    for op in oos:
        conteos_familias.setdefault(op[4], []).append(op)
    informe_familias = {}
    for familia, registros in sorted(conteos_familias.items()):
        ventanas_familia = [
            _metricas(registros[i:i + 20])
            for i in range(len(registros) - 19)
        ]
        bloques_familia = [
            _metricas(registros[i:i + 20])
            for i in range(0, len(registros) - 19, 20)
        ]
        informe_familias[familia] = {
            "operaciones": len(registros),
            "resumen": _metricas(registros),
            "bloques_20_completos": len(bloques_familia),
            "ventanas_moviles_20": len(ventanas_familia),
            "estado": (
                "SIN_MUESTRA_MINIMA_20"
                if len(registros) < 20 else "DESCRIPTIVO_NO_VERIFICADO"
            ),
            "bloques_20_que_cumplen": sum(
                b["cumple_60_y_neto_positivo"] for b in bloques_familia
            ),
            "ventanas_20_que_cumplen": sum(
                b["cumple_60_y_neto_positivo"] for b in ventanas_familia
            ),
            "cumple_todas_ventanas_observadas": (
                bool(ventanas_familia) and all(
                    b["cumple_60_y_neto_positivo"] for b in ventanas_familia
                )
            ),
        }
    peores_bloques = [
        {"desde": b["desde"], "hasta": b["hasta"],
         "ganadas": b["ganadas"], "neto": b["neto"]}
        for b in bloques if not b["cumple_60_y_neto_positivo"]
    ]
    return {
        **base, "estado": "DESCRIPTIVO_NO_VERIFICADO_BROKER",
        "oos_operaciones": len(oos),
        "familias": informe_familias,
        "operaciones_sin_familia": len(conteos_familias.get("SIN_FAMILIA", [])),
        "familias_con_muestra_minima_20": sum(
            f["operaciones"] >= 20 for f in informe_familias.values()
            if f is not informe_familias.get("SIN_FAMILIA")
        ),
        "resumen_oos_descriptivo": resumen,
        "bloques_20_completos": len(bloques),
        "operaciones_restantes_sin_bloque_completo": restantes,
        "bloques_20_no_solapados": bloques,
        "bloques_20_que_incumplen": peores_bloques,
        "peor_winrate_ventana_20": min(v["winrate_pct"] for v in ventanas),
        "peor_neto_ventana_20": min(v["neto"] for v in ventanas),
        "ventanas_moviles_20": len(ventanas),
        "ventanas_moviles_20_que_cumplen": sum(
            b["cumple_60_y_neto_positivo"] for b in ventanas
        ),
        "cumple_todos_bloques_20": cumple,
        "cumple_todas_ventanas_moviles_20": cumple_movil,
        "evidencia_sostenida_60_pct": False,
        "calidad_evidencia": "DESCRIPTIVO_HISTORICO_NO_INDEPENDIENTE",
        "autoridades_observadas": autoridades,
        "cotejo_offline": cotejo,
        "origen_broker_independiente_certificado": False,
        "conclusion": (
            "Metricas descriptivas sobre autorizaciones historicas, "
            "NO validacion OOS de una politica entrenada o de V3."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    parser.add_argument("--exportacion-iq", default=None,
                        help="CSV de broker normalizado, opcional, para cotejo offline")
    args = parser.parse_args()
    print(json.dumps(evaluar_oos(args.historial, exportacion_iq=args.exportacion_iq), indent=2,
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
