"""Fase 5.9: comparacion estricta de dos salidas del backtest oficial.

SOLO LECTURA. Compara el mismo universo de senales historicas entre commits.
Una reduccion retrospectiva de operaciones no prueba rentabilidad futura.
No usa datos posteriores para generar una decision y no opera en IQ.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ESTADOS_OPERADOS = {"OPERADA_DIRECTA", "OPERADA_PROTOCOLO"}
ESTADOS_CONOCIDOS = ESTADOS_OPERADOS | {
    "NO_OPERADA", "NO_OPERAR", "RECHAZADA", "CANCELADA_PROTOCOLO",
    "CANCELADA_CEREBRO", "CANCELADA", "DESCARTADA",
}
COLUMNAS = ("activo", "fecha_senal", "fecha", "direccion", "patron",
            "estado_operacion", "resultado_hipotetico", "resultado",
            "idx_entrada", "precio_entrada", "precio_cierre")
KEYS = ("activo", "fecha", "direccion", "patron")
ETIQUETAS = {"WIN", "LOSS", "EMPATE"}


def _fecha_utc(valor):
    raw = str(valor or "").strip()
    if not raw:
        raise ValueError("FECHA_VACIA")
    try:
        if raw.isdigit() and len(raw) in (10, 13):
            n = int(raw)
            if len(raw) == 13:
                n /= 1000
            return datetime.fromtimestamp(n, tz=timezone.utc)
        x = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if x.tzinfo is None:
            raise ValueError("FECHA_SIN_ZONA_HORARIA")
        return x.astimezone(timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("FECHA_INVALIDA_O_SIN_ZONA") from exc


def _normalizar(filas):
    registros = {}
    for fila in filas:
        if not isinstance(fila, dict):
            raise ValueError("FILA_NO_DICT")
        # DictReader conserva filas con columnas faltantes; validar cada
        # registro impide comparar una muestra parcialmente malformada.
        if not set(COLUMNAS).issubset(fila) or any(
            fila[columna] is None for columna in COLUMNAS
        ):
            raise ValueError("COLUMNAS_INSUFICIENTES")
        nombre = str(fila["activo"] or "").strip()
        direccion = str(fila["direccion"] or "").strip().upper()
        patron = str(fila["patron"] or "").strip()
        if not nombre or direccion not in {"CALL", "PUT"} or not patron:
            raise ValueError("IDENTIDAD_SENAL_INVALIDA")
        instante = _fecha_utc(fila["fecha_senal"])
        instante_entrada = _fecha_utc(fila["fecha"])
        # Identidad causal: la vela que GENERO la senal, no la vela
        # de entrada, que puede variar por cambios de protocolo.
        clave = (nombre, instante.isoformat(), direccion, patron)
        if clave in registros:
            raise ValueError("SENAL_DUPLICADA_IDENTIDAD: " + repr(clave))
        estado = str(fila["estado_operacion"] or "").strip().upper()
        if estado not in ESTADOS_CONOCIDOS:
            raise ValueError("ESTADO_OPERACION_NO_RECONOCIDO: " + estado)
        etiqueta = str(fila["resultado_hipotetico"] or "").strip().upper()
        if etiqueta not in ETIQUETAS:
            raise ValueError("RESULTADO_HIPOTETICO_NO_RECONOCIDO")
        resultado_real = str(fila["resultado"] or "").strip().upper()
        if estado in ESTADOS_OPERADOS and resultado_real not in ETIQUETAS:
            raise ValueError("RESULTADO_OPERADO_INVALIDO")
        registros[clave] = {
            "fecha": instante, "fecha_entrada": instante_entrada,
            "dia": instante.date().isoformat(),
            "estado": estado, "operada": estado in ESTADOS_OPERADOS,
            "etiqueta_hipotetica": etiqueta,
            "etiqueta": resultado_real if estado in ESTADOS_OPERADOS else None,
            "idx_entrada": str(fila.get("idx_entrada") or "").strip(),
            "precio_entrada": str(fila.get("precio_entrada") or "").strip(),
            "precio_cierre": str(fila.get("precio_cierre") or "").strip(),
        }
    if not registros:
        raise ValueError("BACKTEST_VACIO")
    return registros


def _resumen(registros, ganancia_win=None, perdida_loss=None):
    n = len(registros)
    wins = sum(r["etiqueta"] == "WIN" for r in registros)
    losses = sum(r["etiqueta"] == "LOSS" for r in registros)
    empates = n-wins-losses
    salida = {
        "n": n, "wins": wins, "losses": losses, "empates": empates,
        "winrate_pct": round(100 * wins/(wins+losses), 2)
        if wins+losses else None,
    }
    # Nunca presentar PnL como real: requiere supuestos explicitos.
    if ganancia_win is not None and perdida_loss is not None:
        salida["neto_teorico"] = round(
            wins*ganancia_win - losses*perdida_loss, 2
        )
    return salida


def _ventanas_20(registros, ganancia_win=None, perdida_loss=None):
    ventanas = []
    for i in range(max(0, len(registros)-19)):
        resumen = _resumen(registros[i:i+20], ganancia_win, perdida_loss)
        cumple = resumen["winrate_pct"] is not None and resumen["winrate_pct"] >= 60
        if ganancia_win is not None:
            cumple = cumple and resumen["neto_teorico"] > 0
        ventanas.append(cumple)
    return {"total": len(ventanas),
            "bajo_objetivo": len(ventanas)-sum(ventanas),
            "todas_cumplen": bool(ventanas) and all(ventanas)}


def comparar(antes, despues, ganancia_win=None, perdida_loss=None):
    if (ganancia_win is None) != (perdida_loss is None):
        raise ValueError("SUPUESTOS_PNL_INCOMPLETOS")
    if ganancia_win is not None and (
        isinstance(ganancia_win, bool) or isinstance(perdida_loss, bool)
        or not isinstance(ganancia_win, (float, int))
        or not isinstance(perdida_loss, (float, int))
        or not 0 < ganancia_win < float("inf")
        or not 0 < perdida_loss < float("inf")
    ):
        raise ValueError("SUPUESTOS_PNL_INVALIDOS")
    a, b = _normalizar(antes), _normalizar(despues)
    keys_a, keys_b = set(a), set(b)
    comunes = keys_a & keys_b
    diferencias_resultado = sum(
        a[k]["etiqueta_hipotetica"] != b[k]["etiqueta_hipotetica"] for k in comunes
    )
    # Una etiqueta WIN comun no acredita igualdad de precio o instante
    # simulado. Solo cotejar estos valores cuando ambas politicas operan.
    # Los campos son opcionales en registros antiguos: su ausencia es
    # incertidumbre, nunca evidencia de paridad.
    entradas_divergentes = 0
    entradas_sin_verificacion = 0
    resultados_operados_divergentes = 0
    for clave in comunes:
        x, y = a[clave], b[clave]
        if not (x["operada"] and y["operada"]):
            continue
        if x["etiqueta"] != y["etiqueta"]:
            resultados_operados_divergentes += 1
        campos = ("idx_entrada", "precio_entrada", "precio_cierre", "fecha_entrada")
        if any(not x[k] or not y[k] for k in campos):
            entradas_sin_verificacion += 1
        elif any(x[k] != y[k] for k in campos):
            entradas_divergentes += 1
    universos_iguales = (
        keys_a == keys_b and diferencias_resultado == 0
        and entradas_divergentes == 0 and entradas_sin_verificacion == 0
        and resultados_operados_divergentes == 0
    )
    resumen = {
        "modo": "COMPARACION_BACKTEST_CRONOLOGICO_SOLO_PRACTICE_NO_OPERATIVO",
        "universo": {
            "senales_antes": len(a), "senales_despues": len(b),
            "comunes": len(comunes),
            "solo_antes": len(keys_a-keys_b),
            "solo_despues": len(keys_b-keys_a),
            "etiquetas_distintas_en_comunes": diferencias_resultado,
            "entradas_operadas_divergentes": entradas_divergentes,
            "resultados_ejecutados_divergentes": resultados_operados_divergentes,
            "entradas_operadas_sin_precio_o_indice_verificable": entradas_sin_verificacion,
            "comparable_estrictamente": universos_iguales,
        },
        "estado": ("COMPARABLE_DESCRIPTIVO" if universos_iguales
                   else "NO_COMPARABLE_UNIVERSO_ETIQUETAS_O_EJECUCION"),
        "por_dia": [],
        "transiciones": {},
        "supuestos_pnl": (
            {"win": ganancia_win, "loss": perdida_loss,
             "tipo": "HIPOTETICOS_NO_PNL_BROKER"}
            if ganancia_win is not None else None
        ),
        "autoriza_operaciones": False,
        "memoria_productiva_modificada": False,
        "validacion_rentabilidad_futura": False,
        "limitaciones": [
            "Solo resultados hipoteticos calculados sobre velas de backtest.",
            "La estrategia corregida puede generar o descartar senales; "
            "si el universo cambia, no se atribuye causalidad a la diferencia de winrate.",
            "No se simula el precio real del broker ni contrafactual de senales nuevas.",
            "Las ventanas de 20 corresponden a simulacion, no a sesiones PRACTICE.",
        ],
    }
    # Los cambios de generacion/entrada suelen alterar el universo.
    # Conservar las estadisticas de cada version sin atribuir causalidad.
    # No se confunden estas estadisticas con la comparacion pareada.
    if not universos_iguales:
        def describir_politica(registros):
            orden = sorted(registros.items(), key=lambda par: (par[1]["fecha"], par[0]))
            operadas = [r for _, r in orden if r["operada"]]
            return {
                "operaciones": _resumen(operadas, ganancia_win, perdida_loss),
                "ventanas_20": _ventanas_20(operadas, ganancia_win, perdida_loss),
                "senales_generadas": len(registros),
                "dias": len({r["dia"] for r in registros.values()}),
            }

        resumen["descriptivo_no_pareado"] = {
            "antes": describir_politica(a),
            "despues": describir_politica(b),
            "senales_comunes": len(comunes),
            "misma_serie_causal": False,
            "comparacion_causal_permitida": False,
            "advertencia": (
                "Las versiones generan o ejecutan universos distintos; "
                "no interpretar variaciones de winrate como mejora causal."
            ),
        }
        return resumen

    ordenadas = sorted(comunes, key=lambda k: (a[k]["fecha"], k))
    transiciones = Counter()
    por_dia = defaultdict(lambda: {"antes": [], "despues": []})
    antes_operadas, despues_operadas = [], []
    for k in ordenadas:
        r_a, r_b = a[k], b[k]
        transiciones[
            ("OPERADA" if r_a["operada"] else "NO_OPERADA",
             "OPERADA" if r_b["operada"] else "NO_OPERADA")
        ] += 1
        dia = r_a["dia"]
        if r_a["operada"]:
            antes_operadas.append(r_a)
            por_dia[dia]["antes"].append(r_a)
        if r_b["operada"]:
            despues_operadas.append(r_b)
            por_dia[dia]["despues"].append(r_b)
    resumen["transiciones"] = {
        f"{x}_A_{y}": n for (x, y), n in sorted(transiciones.items())
    }
    resumen["antes"] = _resumen(antes_operadas, ganancia_win, perdida_loss)
    resumen["despues"] = _resumen(despues_operadas, ganancia_win, perdida_loss)
    resumen["ventanas_20_antes"] = _ventanas_20(
        antes_operadas, ganancia_win, perdida_loss
    )
    resumen["ventanas_20_despues"] = _ventanas_20(
        despues_operadas, ganancia_win, perdida_loss
    )
    resumen["por_dia"] = [
        {"dia": dia,
         "antes": _resumen(grupos["antes"], ganancia_win, perdida_loss),
         "despues": _resumen(grupos["despues"], ganancia_win, perdida_loss)}
        for dia, grupos in sorted(por_dia.items())
    ]
    resumen["dias_con_ambas_politicas_evaluables"] = sum(
        x["antes"]["n"] and x["despues"]["n"] for x in resumen["por_dia"]
    )
    return resumen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("antes", help="CSV backtest oficial del commit previo")
    p.add_argument("despues", help="CSV backtest oficial del commit actual")
    p.add_argument("--win", type=float, default=None,
                   help="Ganancia por WIN hipotetica explicitamente suministrada")
    p.add_argument("--loss", type=float, default=None,
                   help="Perdida por LOSS hipotetica explicitamente suministrada")
    args = p.parse_args()
    with open(Path(args.antes), encoding="utf-8-sig", newline="") as f:
        antes = list(csv.DictReader(f))
    with open(Path(args.despues), encoding="utf-8-sig", newline="") as f:
        despues = list(csv.DictReader(f))
    print(json.dumps(comparar(antes, despues, args.win, args.loss),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
