"""Auditoria retrospectiva de un bloque de 20 PRACTICE, solo lectura.

Cruza resultados reales con direccion, Price Action, estrategia y autoridad.
No estima operaciones contrafactuales, no cambia filtros ni autoriza trades.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from comparar_bloques_20_practice import _evaluar_bloque


def _texto(valor):
    return str(valor or "").strip()


def _resumen(ops):
    n = len(ops)
    wins = sum(x["pnl"] > 0 for x in ops)
    losses = sum(x["pnl"] < 0 for x in ops)
    empates = n-wins-losses
    neto = round(sum(x["pnl"] for x in ops), 2)
    return {"n": n, "wins": wins, "losses": losses, "empates": empates,
            "winrate_pct": round(100*wins/(wins+losses), 2)
            if wins+losses else None, "neto": neto}


def _precios_iq_verificados(fila):
    bruto = fila.get("auditoria_orden_iq_json")
    if not bruto:
        return {"estado": "SIN_PRECIO_IQ"}
    try:
        dato = json.loads(bruto)
    except (TypeError, ValueError):
        return {"estado": "METADATOS_INVALIDOS"}
    if not isinstance(dato, dict):
        return {"estado": "METADATOS_INVALIDOS"}
    if (
        str(dato.get("order_id") or "").strip()
        != str(fila.get("order_id") or "").strip()
        or dato.get("fuente") != "IQ_ORDER_ASYNC_EVENTOS_CACHE"
    ):
        return {"estado": "PROCEDENCIA_NO_VERIFICADA"}
    precios = dato.get("precios")
    if not isinstance(precios, dict):
        return {"estado": "METADATOS_INVALIDOS"}
    salida = {"estado": "PRECIOS_IQ_EN_CACHE",
              "unidad_verificada": dato.get("unidades_confirmadas") is True}
    for campo in ("precio_apertura_iq", "precio_cierre_iq"):
        valor = precios.get(campo)
        if isinstance(valor, bool):
            continue
        try:
            num = float(valor)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(num) and num > 0:
            salida[campo] = num
    if not any(k in salida for k in ("precio_apertura_iq", "precio_cierre_iq")):
        return {"estado": "SIN_PRECIO_IQ"}
    # No comparar precios IQ con OHLC hasta confirmar unidades de escala.
    return salida


def auditar(reporte):
    validado, error = _evaluar_bloque(reporte)
    if error:
        return {"estado": "NO_EVALUABLE", "motivo": error,
                "autoriza_operaciones": False}
    ops = []
    for i, original in enumerate(reporte["operaciones"], 1):
        pnl = float(original["pnl_numerico"])
        direccion = _texto(original.get("direccion")).upper()
        accion = _texto(original.get("accion_precio")).upper()
        origen = _texto(original.get("origen_autoridad")).upper()
        riesgo_zona = (
            "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            if direccion == "PUT" and accion == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            else "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
            if direccion == "CALL" and accion == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
            else "OTRO_CONTEXTO"
        )
        ops.append({
            "numero": i, "order_id": _texto(original["order_id"]),
            "activo": _texto(original.get("activo")),
            "direccion": direccion or "SIN_DATO",
            "estrategia": _texto(original.get("patron")) or "SIN_DATO",
            "accion_precio": accion or "SIN_DATO",
            "origen_autoridad": origen or "SIN_DATO",
            "riesgo_zona": riesgo_zona,
            "bootstrap_sin_memoria": origen == "BOOTSTRAP_PRACTICE_SIN_HISTORIAL",
            "precio_ejecucion_iq": _precios_iq_verificados(original),
            "pnl": pnl,
        })
    grupos = {}
    for campo in ("riesgo_zona", "origen_autoridad", "estrategia",
                  "direccion", "accion_precio"):
        dic = defaultdict(list)
        for operacion in ops:
            dic[operacion[campo]].append(operacion)
        grupos[campo] = [
            {"valor": k, **_resumen(v)}
            for k, v in sorted(dic.items(), key=lambda kv: kv[0])
        ]
    bootstrap_put_soporte = [
        x for x in ops if x["bootstrap_sin_memoria"]
        and x["riesgo_zona"] == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
    ]
    bootstrap_call_resistencia = [
        x for x in ops if x["bootstrap_sin_memoria"]
        and x["riesgo_zona"] == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
    ]
    return {
        "estado": "AUDITORIA_ENTRADAS_BLOQUE20_PRACTICE",
        "bloque_inicio": _texto(reporte.get("bloque_inicio")),
        "resultado": _resumen(ops),
        "riesgo_bootstrap_put_soporte": {
            **_resumen(bootstrap_put_soporte),
            "order_ids": [x["order_id"] for x in bootstrap_put_soporte],
        },
        "riesgo_bootstrap_call_resistencia": {
            **_resumen(bootstrap_call_resistencia),
            "order_ids": [x["order_id"] for x in bootstrap_call_resistencia],
        },
        "desglose": grupos,
        "operaciones": ops,
        "cobertura_precio_iq": {
            "con_apertura": sum(
                "precio_apertura_iq" in x["precio_ejecucion_iq"] for x in ops
            ),
            "con_cierre": sum(
                "precio_cierre_iq" in x["precio_ejecucion_iq"] for x in ops
            ),
            "sin_apertura": sum(
                "precio_apertura_iq" not in x["precio_ejecucion_iq"] for x in ops
            ),
        },
        "limitaciones": [
            "Los precios IQ se presentan sin calcular distancias con OHLC hasta verificar las unidades.",
            "Asociacion retrospectiva; no demuestra que el nivel provocara cada resultado.",
            "No se puede inferir el resultado de las operaciones hipoteticamente omitidas.",
            "La captura grafica y el snapshot almacenado pueden corresponder a momentos distintos.",
        ],
        "autoriza_operaciones": False,
        "memoria_productiva_modificada": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reporte", help="JSON final del bloque, generado por bot.py")
    args = parser.parse_args()
    with Path(args.reporte).open(encoding="utf-8-sig") as f:
        informe = auditar(json.load(f))
    print(json.dumps(informe, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
