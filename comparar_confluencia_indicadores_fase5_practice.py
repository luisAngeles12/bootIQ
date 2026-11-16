"""Fase 5: comparacion predefinida de confluencia tecnica, SOLO PRACTICE.

Usa exclusivamente cierres identificados y snapshots registrados junto a la
orden. Nunca recalcula indicadores con velas futuras ni reconstruye fills.
Filtros observacionales: no prueban causalidad ni autorizan trading.
"""
import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path


def _finito(valor):
    if valor is None or isinstance(valor, bool) or str(valor).strip() == "":
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    return numero if math.isfinite(numero) else None


def _snapshot(fila):
    datos = {}
    raw = str(fila.get("indicadores_tecnicos_json") or "").strip()
    if raw:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                datos = obj
        except (ValueError, TypeError):
            pass
    # Columna explicita tiene prioridad; nunca asumir que cero significa ausencia.
    def leer(*nombres):
        for nombre in nombres:
            valor = fila.get(nombre)
            if valor is not None and str(valor).strip() != "":
                return _finito(valor)
        for nombre in nombres:
            if nombre in datos:
                return _finito(datos[nombre])
        return None
    return {
        "ema9": leer("ema9"),
        "ema21": leer("ema21"),
        "rsi": leer("rsi_indicador", "rsi"),
        "bb_superior": leer("bb_superior"),
        "bb_media": leer("bb_media"),
        "bb_inferior": leer("bb_inferior"),
        "precio": leer("precio_cierre_indicadores", "ultima_close"),
    }


def evaluar_confluencia(filas, minimo_test=20):
    if minimo_test < 20:
        raise ValueError("MINIMO_TEST_DEBE_SER_20_O_MAS")

    registros = []
    ids = set()
    descartes = Counter()
    for fila in filas:
        if str(fila.get("estado") or "").strip().upper() != "CERRADA":
            descartes["NO_CERRADA"] += 1
            continue
        oid = str(fila.get("order_id") or "").strip()
        if not oid or oid in ids:
            descartes["ID_AUSENTE_O_DUPLICADO"] += 1
            continue
        try:
            fecha = datetime.fromisoformat(str(fila.get("fecha") or "").replace("Z", "+00:00"))
            pnl = _finito(fila.get("resultado"))
            if pnl is None:
                raise ValueError("PNL_INVALIDO")
        except ValueError:
            descartes["FECHA_O_PNL_INVALIDO"] += 1
            continue
        ids.add(oid)
        if pnl == 0:
            descartes["EMPATE"] += 1
            continue
        direccion = str(fila.get("direccion") or "").strip().upper()
        if direccion not in ("CALL", "PUT"):
            descartes["SIN_DIRECCION"] += 1
            continue
        pa = str(fila.get("pa_direccion") or "").strip().upper()
        ind = _snapshot(fila)
        ema_ok = ind["ema9"] is not None and ind["ema21"] is not None
        ema_alineada = ema_ok and (
            (direccion == "CALL" and ind["ema9"] > ind["ema21"])
            or (direccion == "PUT" and ind["ema9"] < ind["ema21"])
        )
        rsi = ind["rsi"]
        rsi_neutro = rsi is not None and 30 <= rsi <= 70
        bb = [ind[k] for k in ("bb_inferior", "bb_media", "bb_superior")]
        bb_valida = all(x is not None for x in bb) and bb[0] < bb[2] and bb[0] <= bb[1] <= bb[2]
        bb_dentro = bb_valida and ind["precio"] is not None and bb[0] <= ind["precio"] <= bb[2]
        registros.append({
            "order_id": oid, "fecha": fecha, "pnl": pnl,
            "patron": str(fila.get("patron") or "SIN_PATRON").strip(),
            "ema_disponible": ema_ok,
            "ema_alineada": ema_alineada,
            "pa_alineada": pa == direccion,
            "pa_disponible": pa in ("CALL", "PUT", "NEUTRA", "NEUTRAL"),
            "rsi_disponible": rsi is not None and 0 <= rsi <= 100,
            "rsi_neutro": rsi_neutro,
            "bb_disponible": bool(bb_valida and ind["precio"] is not None),
            "bb_dentro": bool(bb_dentro),
        })

    zonas = {x["fecha"].tzinfo is None for x in registros}
    if len(zonas) > 1:
        raise ValueError("FECHAS_ZONAS_MIXTAS")
    registros.sort(key=lambda x: x["fecha"])
    dias = sorted({x["fecha"].date().isoformat() for x in registros})
    ultimo_dia = dias[-1] if dias else None

    def resumen(subconjunto, universo):
        n = len(subconjunto)
        wins = sum(x["pnl"] > 0 for x in subconjunto)
        ventanas = [subconjunto[i:i + 20] for i in range(max(0, n - 19))]
        fallidas = sum(sum(x["pnl"] > 0 for x in ventana) < 12 for ventana in ventanas)
        return {
            "n": n, "universo": len(universo), "wins": wins,
            "losses": n - wins,
            "winrate_pct": round(100 * wins / n, 2) if n else None,
            "neto": round(sum(x["pnl"] for x in subconjunto), 2),
            "retencion_pct": round(100 * n / len(universo), 2) if universo else None,
            "ventanas_20": len(ventanas),
            "ventanas_20_bajo_60": fallidas,
            "consistencia_20_observada": bool(ventanas) and fallidas == 0,
        }

    reglas = (
        ("BASELINE", lambda x: True),
        ("EMA_ALINEADA", lambda x: x["ema_alineada"]),
        ("PA_Y_EMA_ALINEADAS", lambda x: x["pa_alineada"] and x["ema_alineada"]),
        ("PA_EMA_RSI_NEUTRO", lambda x: x["pa_alineada"] and x["ema_alineada"] and x["rsi_disponible"] and x["rsi_neutro"]),
        ("PA_EMA_BB_DENTRO", lambda x: x["pa_alineada"] and x["ema_alineada"] and x["bb_disponible"] and x["bb_dentro"]),
    )

    train = [x for x in registros if x["fecha"].date().isoformat() != ultimo_dia]
    test = [x for x in registros if x["fecha"].date().isoformat() == ultimo_dia]

    escenarios = []
    for nombre, regla in reglas:
        seleccion_train = [x for x in train if regla(x)]
        seleccion_test = [x for x in test if regla(x)]
        escenarios.append({
            "hipotesis_fija": nombre,
            "train": resumen(seleccion_train, train),
            "ultimo_dia_oos_descriptivo": resumen(seleccion_test, test),
            "muestra_test_suficiente": len(dias) >= 2 and len(seleccion_test) >= minimo_test,
            "habilita_cambios": False,
        })

    return {
        "modo": "CONFLUENCIA_OBSERVACIONAL_PRACTICE",
        "dias": dias, "dia_test": ultimo_dia,
        "total_cerradas_evaluables": len(registros),
        "descartes": dict(sorted(descartes.items())),
        "cobertura": {
            campo: sum(bool(x[campo]) for x in registros)
            for campo in ("pa_disponible", "ema_disponible", "rsi_disponible", "bb_disponible")
        },
        "escenarios": escenarios,
        "limitaciones": [
            "Sin snapshots de indicadores no se imputan valores ni se evaluan confluencias.",
            "Seleccion de operaciones ejecutadas, no simulacion causal de alternativas.",
            "El ultimo dia es historico OOS descriptivo, no validacion prospectiva.",
            "No ajusta filtros, thresholds, estrategia, memoria ni autoriza operaciones.",
        ],
        "operaciones_autorizadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(newline="", encoding="utf-8-sig") as archivo:
        reporte = evaluar_confluencia(csv.DictReader(archivo))
    print(json.dumps(reporte, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
