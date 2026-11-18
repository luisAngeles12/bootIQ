"""Walk-forward V3 en cierres PRACTICE con entrenamiento cronologico.

Cada dia TEST usa exclusivamente cierres anteriores. No elige estrategias
a partir del test, no altera memoria oficial ni envia ordenes.
"""
import argparse
import csv
import json
import math
import tempfile
from collections import Counter
from pathlib import Path

import motor_aprendizaje_historico as mah
from construir_memoria_ejecutadas_train_practice import _limpiar, _resumen
from motor_decision import UMBRAL_PROBABILIDAD_OPERAR, MIN_MUESTRA_PROBABILIDAD


def evaluar_walk_forward(filas, minimo_train=20, minimo_test_total=20):
    if minimo_train < 20 or minimo_test_total < 20:
        raise ValueError("MINIMOS_REQUIEREN_20")
    validos, descartes = _limpiar(filas)
    dias = sorted({x[0].date().isoformat() for x in validos})
    cortes = []
    evaluados = []
    seleccionados = []
    predicciones = []
    rechazos = Counter()
    probabilidades = []
    muestras = []
    fuentes_principales = {}
    for dia in dias:
        train = [x for x in validos if x[0].date().isoformat() < dia]
        test = [x for x in validos if x[0].date().isoformat() == dia]
        if len(train) < minimo_train:
            continue
        # El test no puede influir en la construccion de su propia memoria.
        datos = []
        for fecha, _oid, pnl, fila in train:
            registro = dict(fila)
            registro["resultado"] = "WIN" if pnl > 0 else "LOSS"
            registro["fecha"] = str(fecha.timestamp())
            registro["es_hipotetico"] = False
            datos.append(registro)
        with tempfile.TemporaryDirectory(prefix="bootiq_wf_") as temp:
            ruta = str(Path(temp) / "train.csv")
            mah.generar_aprendizaje_desde_resultados(
                datos, ruta=ruta, incluir_hipoteticos=False
            )
            memoria = mah.cargar_aprendizaje(ruta)
        evaluados.extend(test)
        seleccion_dia = []
        con_fuente = 0
        for item in test:
            diagnostico = mah.evaluar_aprendizaje_historico(item[3], memoria=memoria)
            principal = diagnostico.get("fuente_probabilidad_principal")
            muestra = diagnostico.get("muestra_historica", 0)
            prob = diagnostico.get("probabilidad_estimada")
            if not principal:
                rechazos["SIN_FUENTE_PRINCIPAL"] += 1
                continue
            if isinstance(prob, bool) or not isinstance(prob, (int, float)) or not math.isfinite(prob) or not (0 <= prob <= 100):
                rechazos["PROBABILIDAD_INVALIDA"] += 1
                continue
            con_fuente += 1
            probabilidades.append(prob)
            observado = 1 if item[2] > 0 else 0
            predicciones.append((prob/100, observado))
            # Diagnostico estrictamente OOS: agrupar por nivel principal,
            # sin elegir ni promover fuentes en funcion del TEST.
            if isinstance(principal, dict):
                nivel = str(principal.get("nivel") or "SIN_NIVEL").strip()
            else:
                nivel = "FUENTE_NO_DICT"
            fuente_stats = fuentes_principales.setdefault(
                nivel, {"n": 0, "wins": 0, "neto": 0.0,
                        "probabilidades": [], "muestras": []}
            )
            fuente_stats["n"] += 1
            fuente_stats["wins"] += observado
            fuente_stats["neto"] += item[2]
            fuente_stats["probabilidades"].append(prob)
            if isinstance(muestra, (int, float)) and not isinstance(muestra, bool) and math.isfinite(muestra):
                fuente_stats["muestras"].append(muestra)
            muestra_valida = (
                not isinstance(muestra, bool)
                and isinstance(muestra, (int, float))
                and math.isfinite(muestra)
                and muestra >= 0
            )
            if muestra_valida:
                muestras.append(muestra)
            prob_ok = prob >= UMBRAL_PROBABILIDAD_OPERAR
            muestra_ok = muestra_valida and muestra >= MIN_MUESTRA_PROBABILIDAD
            if prob_ok and muestra_ok:
                seleccion_dia.append(item)
                seleccionados.append(item)
            elif not muestra_valida:
                rechazos["MUESTRA_INVALIDA"] += 1
            elif not prob_ok and not muestra_ok:
                rechazos["PROBABILIDAD_Y_MUESTRA_INSUFICIENTES"] += 1
            elif not prob_ok:
                rechazos["SOLO_PROBABILIDAD_INSUFICIENTE"] += 1
            else:
                rechazos["SOLO_MUESTRA_INSUFICIENTE"] += 1
        cortes.append({
            "dia_test": dia, "train_n": len(train),
            "test": _resumen(test),
            "con_fuente": con_fuente,
            "seleccion_v3_diagnostica": _resumen(seleccion_dia),
        })
    baseline = _resumen(evaluados)
    hipotesis = _resumen(seleccionados)
    brier = (sum((p-y)**2 for p,y in predicciones)/len(predicciones)
             if predicciones else None)
    brier_prior = (sum((mah.PRIOR_WINRATE/100-y)**2 for p,y in predicciones)
                   /len(predicciones) if predicciones else None)
    suficiente = len(seleccionados) >= minimo_test_total
    # La meta pide constancia, no solo 60% global. Las ventanas son de
    # veinte ordenes SELECCIONADAS en orden cronologico OOS.
    ventanas_20 = []
    for i in range(max(0, len(seleccionados) - 19)):
        ventana = seleccionados[i:i + 20]
        resumen = _resumen(ventana)
        ventanas_20.append({
            "desde": ventana[0][0].isoformat(),
            "hasta": ventana[-1][0].isoformat(),
            "winrate_pct": resumen["winrate_pct"],
            "neto": resumen["neto"],
            "cumple_objetivo": resumen["winrate_pct"] >= 60 and resumen["neto"] > 0,
        })
    dias_con_entradas = sum(
        corte["seleccion_v3_diagnostica"]["n"] > 0 for corte in cortes
    )
    ventanas_fallidas = sum(not x["cumple_objetivo"] for x in ventanas_20)
    consistencia_observada = (
        suficiente and bool(ventanas_20) and ventanas_fallidas == 0
        and hipotesis["winrate_pct"] >= 60 and hipotesis["neto"] > 0
    )
    return {
        "modo": "WALK_FORWARD_V3_PRACTICE_SOLO_EJECUTADAS",
        "dias_disponibles": len(dias),
        "dias_test_evaluados": len(cortes),
        "cortes": cortes,
        "baseline_dias_test": baseline,
        "seleccion_probabilidad_v3_diagnostica": hipotesis,
        "fuentes_principales_oos": [
            {
                "nivel": nivel, "n": datos["n"],
                "wins": datos["wins"], "losses": datos["n"] - datos["wins"],
                "winrate_pct": round(100 * datos["wins"] / datos["n"], 2),
                "neto": round(datos["neto"], 2),
                "probabilidad_promedio_pct": round(
                    sum(datos["probabilidades"]) / datos["n"], 2),
                "muestra_promedio": round(
                    sum(datos["muestras"]) / len(datos["muestras"]), 2
                ) if datos["muestras"] else None,
            }
            for nivel, datos in sorted(fuentes_principales.items())
        ],
        "diagnostico_rechazos_v3": {
            "umbrales_no_modificados": {
                "probabilidad_minima_pct": UMBRAL_PROBABILIDAD_OPERAR,
                "muestra_minima": MIN_MUESTRA_PROBABILIDAD,
            },
            "motivos_exclusivos": dict(sorted(rechazos.items())),
            "probabilidad_observada_pct": {
                "min": round(min(probabilidades), 2) if probabilidades else None,
                "max": round(max(probabilidades), 2) if probabilidades else None,
                "promedio": round(sum(probabilidades)/len(probabilidades), 2) if probabilidades else None,
            },
            "muestra_observada": {
                "min": min(muestras) if muestras else None,
                "max": max(muestras) if muestras else None,
                "promedio": round(sum(muestras)/len(muestras), 2) if muestras else None,
            },
        },
        "retencion_pct": round(100*len(seleccionados)/len(evaluados),2)
                         if evaluados else None,
        "brier_v3": round(brier,6) if brier is not None else None,
        "brier_prior": round(brier_prior,6) if brier_prior is not None else None,
        "muestra_seleccion_suficiente": suficiente,
        "dias_con_seleccion": dias_con_entradas,
        "ventanas_moviles_20": len(ventanas_20),
        "ventanas_moviles_20_bajo_objetivo": ventanas_fallidas,
        "consistencia_20_y_neto_observada": consistencia_observada,
        "supera_60_y_neto": consistencia_observada,
        "descartes": descartes,
        "limitaciones": [
            "La muestra contiene solo ordenes ejecutadas: sesgo de seleccion.",
            "No estima el rendimiento contrafactual de senales no ejecutadas.",
            "Seleccion V3 es diagnostica: no replica todos los vetos ni protocolos.",
            "Superar 60 en este analisis no demuestra consistencia futura.",
        ],
        "autoriza_operaciones": False,
        "memoria_productiva_modificada": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = ap.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        print(json.dumps(evaluar_walk_forward(csv.DictReader(f)),
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
