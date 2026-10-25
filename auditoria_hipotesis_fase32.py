"""Hipótesis CONGELADAS de Fase 3.2 para validación prospectiva.

A/B fueron descubiertas explorando 1,171 combinaciones SEP/OCT.
No son estrategias autorizadas, ni afectan generación, decisión o órdenes.
"""
from collections import Counter
from math import sqrt


META_WINRATE = 59.0


def _numero(fila, campo):
    try:
        return float(fila[campo])
    except (KeyError, TypeError, ValueError):
        return None


def coincide_hipotesis(fila, nombre):
    pa = _numero(fila, "pa_fuerza")
    if pa is None or not 0.25 <= pa < 0.50:
        return False
    if nombre == "A":
        rsi, puntos = _numero(fila, "rsi"), _numero(fila, "puntaje")
        return rsi is not None and puntos is not None and 40 <= rsi < 50 and 15 <= puntos < 20
    if nombre == "B":
        return (fila.get("calidad_setup") == "BUENA"
                and fila.get("subtipo_setup") == "SWEEP_RUPTURA_CONFIRMABLE")
    raise ValueError("Hipótesis desconocida")


def _limite_inferior(wins, total):
    if not total:
        return 0.0
    z = 1.96
    p = wins / total
    return 100*(p+z*z/(2*total)-z*sqrt(p*(1-p)/total+z*z/(4*total*total)))/(1+z*z/total)


def resumir_hipotesis_ventanas(ventanas, minimo_total=100, minimo_ventanas=3,
                              minimo_por_ventana=30):
    """ventanas: pares (nombre_temporal, iterable de filas históricas).

    Evita usar una ventana incompleta como evidencia de estabilidad.
    Resultados de canceladas siempre son hipotéticos.
    """
    vistos = set()
    datos = {"A": [], "B": []}
    for nombre, filas in ventanas:
        if not nombre or nombre in vistos:
            raise ValueError("Ventana temporal repetida o sin nombre")
        vistos.add(nombre)
        filas = list(filas)
        for clave in datos:
            seleccionadas = [r for r in filas
                             if isinstance(r,dict) and coincide_hipotesis(r, clave)
                             and r.get("resultado_hipotetico") in {"WIN","LOSS"}]
            w = sum(r["resultado_hipotetico"] == "WIN" for r in seleccionadas)
            datos[clave].append({
                "ventana": nombre, "n": len(seleccionadas), "wins": w,
                "losses": len(seleccionadas)-w,
                "activos": len({r.get("activo") for r in seleccionadas if r.get("activo")}),
            })
    salida = {}
    for clave, detalle in datos.items():
        n = sum(r["n"] for r in detalle)
        w = sum(r["wins"] for r in detalle)
        wr = 100*w/n if n else None
        inferior = _limite_inferior(w,n)
        cobertura = n >= minimo_total and sum(r["n"] >= minimo_por_ventana for r in detalle) >= minimo_ventanas
        transferible = bool(cobertura and wr is not None and wr >= META_WINRATE
                             and inferior >= META_WINRATE
                             and all(100*r["wins"]/r["n"] >= META_WINRATE
                                     for r in detalle if r["n"] >= minimo_por_ventana))
        salida[clave] = {
            "n": n,"wins_hipoteticos":w,"losses_hipoteticas":n-w,
            "wr_hipotetico":round(wr,2) if wr is not None else None,
            "wilson_inferior_95":round(inferior,2),
            "ventanas":detalle,"cobertura_suficiente":cobertura,
            "evidencia_59_transferible":transferible,
            "autoriza_operacion":False,
        }
    return salida
