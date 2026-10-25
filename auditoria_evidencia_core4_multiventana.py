"""Seguimiento pasivo multiventana de rutas CORE4.

El porcentaje 59 es un objetivo de desempeño estadístico del conjunto,
NO una condición para que una señal individual opere.
"""
from math import sqrt


OBJETIVO_WINRATE = 59.0
MIN_OPERACIONES = 30
MIN_VENTANAS = 3


def _limite_inferior(wins, total, z=1.96):
    if total <= 0:
        return 0.0
    p = wins/total
    return 100*(p+z*z/(2*total)-z*sqrt(p*(1-p)/total+z*z/(4*total*total)))/(1+z*z/total)


def evaluar_evidencia_multiventana(ventanas, minimo_operaciones=MIN_OPERACIONES,
                                  minimo_ventanas=MIN_VENTANAS,
                                  objetivo=OBJETIVO_WINRATE):
    """Consume recuentos previamente auditados de operaciones backtest.

    Ventanas son etiquetas temporales independientes suministradas por
    auditoría; rechaza ventanas repetidas y muestras inválidas.
    """
    nombres = set()
    detalles = []
    total = wins = 0
    for dato in ventanas:
        if not isinstance(dato, dict):
            raise ValueError("ventana no estructurada")
        nombre = str(dato.get("ventana") or "").strip()
        if not nombre or nombre in nombres:
            raise ValueError("ventana ausente o repetida")
        nombres.add(nombre)
        w, l = dato.get("wins"), dato.get("losses")
        if not isinstance(w, int) or not isinstance(l, int) or isinstance(w, bool) or isinstance(l, bool) or min(w, l) < 0:
            raise ValueError("resultados inválidos")
        n = w+l
        if n == 0:
            continue
        detalles.append({"ventana":nombre,"n":n,"winrate":round(100*w/n,2)})
        total += n
        wins += w
    wr = (100*wins/total) if total else None
    inferior = _limite_inferior(wins,total)
    cumple_muestra = total >= minimo_operaciones and len(detalles) >= minimo_ventanas
    cumple_objetivo = bool(cumple_muestra and wr is not None and wr >= objetivo and inferior >= objetivo)
    return {"n":total,"wins":wins,"losses":total-wins,
            "wr_observado":round(wr,2) if wr is not None else None,
            "wilson_inferior_95":round(inferior,2),
            "ventanas_con_datos":len(detalles),"detalle":detalles,
            "cumple_minimo_muestra_y_tiempo":cumple_muestra,
            "supera_59_con_confianza":cumple_objetivo,
            "autoriza_trading":False}


def evaluar_rutas_por_separado(filas, **criterios):
    """Evita que resultados de R1 y R1+R2 se sumen como una estrategia.

    Cada fila incluye regla exacta, ventana independiente y WIN/LOSS
    ya auditados; se preserva la decisión de no operar del cerebro.
    """
    grupos = {}
    for fila in filas:
        if not isinstance(fila, dict):
            raise ValueError("fila no estructurada")
        regla = str(fila.get("regla") or "").strip()
        if not regla:
            raise ValueError("ruta CORE4 sin nombre")
        grupos.setdefault(regla, []).append({
            "ventana": fila.get("ventana"),
            "wins": fila.get("wins"),
            "losses": fila.get("losses"),
        })
    return {regla: evaluar_evidencia_multiventana(ventanas, **criterios)
            for regla, ventanas in sorted(grupos.items())}
