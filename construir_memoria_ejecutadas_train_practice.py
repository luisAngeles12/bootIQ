"""Construye memoria V3 candidata con cierres reales PRACTICE, no ficticios.

Convierte PnL numerico del historial a WIN/LOSS del generador oficial.
Mantiene el orden temporal: TRAIN cerrado antes de TEST por dias completos.
No activa, copia ni reemplaza la memoria oficial del bot.
"""
import argparse
import csv
import json
import math
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import motor_aprendizaje_historico as mah


def _limpiar(filas):
    vistos, duplicados, descartes, validos = set(), set(), Counter(), []
    for fila in filas:
        if str(fila.get("modo_cuenta_configurado") or "").strip().upper() != "PRACTICE":
            descartes["NO_PRACTICE"] += 1
            continue
        if str(fila.get("estado") or "").strip().upper() != "CERRADA":
            descartes["NO_CERRADA"] += 1
            continue
        if str(fila.get("estado_operacion") or "").strip().upper() not in ("OPERADA_DIRECTA", "OPERADA_PROTOCOLO"):
            descartes["NO_EJECUTADA"] += 1
            continue
        oid = str(fila.get("order_id") or "").strip()
        if not oid:
            descartes["ID_INVALIDO_O_DUPLICADO"] += 1
            continue
        if oid in vistos:
            duplicados.add(oid)
            descartes["ID_INVALIDO_O_DUPLICADO"] += 1
            continue
        vistos.add(oid)
        try:
            pnl = float(str(fila.get("resultado") or "").strip())
            fecha = datetime.fromisoformat(str(fila.get("fecha") or "").replace("Z", "+00:00"))
            if not math.isfinite(pnl):
                raise ValueError("PNL_INVALIDO")
        except (ValueError, TypeError, OverflowError):
            descartes["FECHA_O_PNL_INVALIDO"] += 1
            continue
        if pnl == 0:
            descartes["EMPATE"] += 1
            continue
        # Prevenir convertir cierres sin contexto operable en muestras espurias.
        if str(fila.get("direccion") or "").lower().strip() not in ("call", "put"):
            descartes["SIN_DIRECCION"] += 1
            continue
        validos.append((fecha, oid, pnl, fila))
    # Dos filas cerradas para el mismo order_id son ambiguas incluso si
    # una parece valida: excluir TODAS sus apariciones del entrenamiento.
    if duplicados:
        validos = [fila for fila in validos if fila[1] not in duplicados]
        descartes["ORDENES_AMBIGUAS_EXCLUIDAS"] = len(duplicados)
    if len({fecha.tzinfo is None for fecha, *_ in validos}) > 1:
        raise ValueError("ZONAS_HORARIAS_MIXTAS")
    validos.sort(key=lambda x: (x[0], x[1]))
    return validos, dict(sorted(descartes.items()))


def _resumen(filas):
    n = len(filas)
    wins = sum(x[2] > 0 for x in filas)
    neto = sum(x[2] for x in filas)
    return {"n": n, "wins": wins, "losses": n-wins,
            "winrate_pct": round(100*wins/n, 2) if n else None,
            "neto": round(neto, 2),
            "pnl_por_orden": round(neto/n, 4) if n else None}


def preparar_candidata(filas, carpeta="experimentos_fase5", minimo_train=20,
                       minimo_test=20, generar=True):
    if minimo_train < 20 or minimo_test < 20:
        raise ValueError("MINIMO_TRAIN_Y_TEST_20")
    validos, descartes = _limpiar(filas)
    dias = sorted({x[0].date().isoformat() for x in validos})
    if len(dias) < 2:
        return {"estado": "SIN_DIAS_INDEPENDIENTES", "descartes": descartes,
                "baseline": _resumen(validos), "memoria_modificada": False}
    corte = dias[max(0, int(len(dias)*0.7)-1)]
    train = [x for x in validos if x[0].date().isoformat() <= corte]
    test = [x for x in validos if x[0].date().isoformat() > corte]
    reporte = {"modo": "MEMORIA_CANDIDATA_DE_CIERRES_REALES_PRACTICE",
               "corte_train_inclusivo": corte,
               "train": _resumen(train), "test_oos": _resumen(test),
               "descartes": descartes, "memoria_productiva_modificada": False,
               "autoriza_operaciones": False}
    if len(train) < minimo_train or len(test) < minimo_test:
        return {**reporte, "estado": "MUESTRA_TEMPORAL_INSUFICIENTE"}
    if not generar:
        return {**reporte, "estado": "PARTICION_APTA_SIN_GENERAR"}
    datos = []
    for fecha, oid, pnl, fila in train:
        copia = dict(fila)
        copia["resultado"] = "WIN" if pnl > 0 else "LOSS"
        copia["fecha"] = str(fecha.timestamp())
        copia["es_hipotetico"] = False
        datos.append(copia)
    destino_dir = Path(carpeta).resolve()
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / "memoria_ejecutadas_train_candidata.csv"
    productiva = Path(os.getenv("BOOTIQ_RUTA_APRENDIZAJE",
                                mah.RUTA_APRENDIZAJE)).resolve()
    if destino == productiva:
        raise ValueError("RUTA_CANDIDATA_IGUAL_PRODUCTIVA")
    if destino.exists():
        raise FileExistsError("CANDIDATA_EXISTENTE_NO_SOBRESCRIBIR")
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(dir=destino_dir, prefix=".memoria_train_",
                                         suffix=".csv", delete=False) as t:
            temporal = Path(t.name)
        claves = mah.generar_aprendizaje_desde_resultados(
            datos, ruta=str(temporal), incluir_hipoteticos=False
        )
        if not claves:
            raise ValueError("SIN_CLAVES_GENERADAS")
        memoria = mah.cargar_aprendizaje(str(temporal))
        if not memoria:
            raise ValueError("MEMORIA_GENERADA_ILEGIBLE")
        # OOS solo se evalua, nunca contribuye a entrenar ni seleccionar claves.
        disponibles = []
        predicciones = []
        for item in test:
            # La memoria TRAIN queda congelada durante todo el holdout.
            diagnostico = mah.evaluar_aprendizaje_historico(item[3], memoria=memoria)
            principal = diagnostico.get("fuente_probabilidad_principal")
            if principal:
                disponibles.append(item)
                prob = diagnostico.get("probabilidad_estimada")
                muestra = diagnostico.get("muestra_historica", 0)
                if isinstance(prob, (int, float)) and math.isfinite(prob):
                    predicciones.append((item, float(prob), int(muestra)))
        reporte["cobertura_test_oos"] = {
            "con_fuente_n": len(disponibles),
            "cobertura_pct": round(100*len(disponibles)/len(test), 2),
            "pnl_observado_con_fuente": _resumen(disponibles),
            "sin_fuente_n": len(test)-len(disponibles),
        }
        # Brier menor es mejor; comparacion justa sobre el mismo holdout.
        # Solo evalua operaciones ejecutadas, nunca las descartadas.
        reporte["calibracion_oos_solo_ejecutadas"] = {
            "n": len(predicciones),
            "brier_v3": round(sum(
                ((prob / 100) - (1 if item[2] > 0 else 0))**2
                for item, prob, _ in predicciones
            ) / len(predicciones), 6) if predicciones else None,
            "brier_prior": round(sum(
                ((mah.PRIOR_WINRATE / 100) - (1 if item[2] > 0 else 0))**2
                for item, _, _ in predicciones
            ) / len(predicciones), 6) if predicciones else None,
            "mejora_brier_contra_prior": None,
        }
        cal = reporte["calibracion_oos_solo_ejecutadas"]
        if cal["brier_v3"] is not None:
            cal["mejora_brier_contra_prior"] = cal["brier_v3"] < cal["brier_prior"]
        reporte["hipotesis_probabilidad_oos"] = {
            "umbral_solo_diagnostico_pct": 55.0,
            "muestra_minima_solo_diagnostico": 12,
            "operaciones_que_superan_ambos": _resumen([
                item for item, prob, n in predicciones if prob >= 55 and n >= 12
            ]),
            "no_equivale_a_decision_del_cerebro": True,
            "no_autoriza_operaciones": True,
        }
        # No declarar validacion de trading por disponer de una fuente.
        os.link(str(temporal), str(destino))
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return {**reporte, "estado": "CANDIDATA_AISLADA_CREADA",
            "destino": str(destino), "claves_generadas": len(memoria),
            "requiere_pruebas_prospectivas": True,
            "aviso": "Muestra ejecutada con sesgo de seleccion; no equivale a universo completo de señales."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("historial", nargs="?", default="historial_bot.csv")
    ap.add_argument("--carpeta", default="experimentos_fase5")
    ap.add_argument("--solo-particion", action="store_true")
    args = ap.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as file:
        result = preparar_candidata(csv.DictReader(file), args.carpeta,
                                    generar=not args.solo_particion)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
