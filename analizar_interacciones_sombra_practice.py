"""Investigación sombra por interacciones y días futuros retenidos.

Solo análisis exploratorio. Nunca modifica el bot ni autoriza operaciones.
Utiliza depuración existente y retiene jornadas cronológicas posteriores
para evitar elegir combinaciones con los mismos datos donde se validan.
"""
import argparse
import json
from collections import defaultdict

from experimento_alineacion_sombra_practice import depurar, leer_csv

MIN_DIAS_ENTRENAMIENTO = 3
MIN_DIAS_VALIDACION = 2


def _resumen(eventos): 
    n = len(eventos)
    w = sum(e["resultado"] == "WIN" for e in eventos)
    l = sum(e["resultado"] == "LOSS" for e in eventos)
    m = len({e["minuto"] for e in eventos})
    return {
        "n": n, "wins": w, "losses": l, "empates": n-w-l,
        "acierto_pct": round(100*w/n, 2) if n else None,
        "dias": len({e["minuto"] // 86400 for e in eventos}),
        "minutos_utc_distintos": m,
        "simultaneos": n-m,
    }


def analizar(filas, min_train=40, min_valid=20, proporcion_dias_train=0.7):
    if (type(min_train) is not int or min_train < 1
            or type(min_valid) is not int or min_valid < 1
            or not 0 < proporcion_dias_train < 1):
        raise ValueError("PARAMETROS_INVALIDOS")
    originales = list(filas)
    eventos, descartes = depurar(originales)
    dias = sorted({e["minuto"] // 86400 for e in eventos})
    if len(dias) < MIN_DIAS_ENTRENAMIENTO + MIN_DIAS_VALIDACION:
        return {"estado": "JORNADAS_INSUFICIENTES", "dias": len(dias),
                "descartes": descartes, "autoriza_real": False,
                "promueve_estrategia": False}
    corte = max(MIN_DIAS_ENTRENAMIENTO, min(len(dias)-MIN_DIAS_VALIDACION,
                                            int(len(dias)*proporcion_dias_train)))
    train_dias = set(dias[:corte])
    valid_dias = set(dias[corte:])
    # Evita atribuir una sola señal a múltiples estrategias coincidentes.
    unicos = [e for e in eventos if len(e["patrones"]) == 1]
    sin_patron_unico = len(eventos)-len(unicos)
    grupos = defaultdict(list)
    for e in unicos:
        # Alineación, dirección y PA son observables antes de conocer el cierre.
        # No usar resultado en la clave.
        clave = (e["patrones"][0], e["direccion"],
                 e["alineacion"], e["accion_precio"])
        grupos[clave].append(e)
    resultados = []
    for clave, muestras in sorted(grupos.items()):
        train = [e for e in muestras if e["minuto"] // 86400 in train_dias]
        valid = [e for e in muestras if e["minuto"] // 86400 in valid_dias]
        a, b = _resumen(train), _resumen(valid)
        evaluable = (a["n"] >= min_train and b["n"] >= min_valid
                     and a["dias"] >= MIN_DIAS_ENTRENAMIENTO
                     and b["dias"] >= MIN_DIAS_VALIDACION)
        resultados.append({
            "patron": clave[0], "direccion": clave[1],
            "alineacion": clave[2], "accion_precio": clave[3],
            "train": a, "validacion_posterior": b,
            "muestra_suficiente_para_comparacion_exploratoria": evaluable,
            "mejora_replicada_60_proxy": (
                a["acierto_pct"] >= 60 and b["acierto_pct"] >= 60
                if evaluable else None),
            "autorizacion": False,
        })
    # Ordenar por criterio definido sin mirar el resultado posterior.
    resultados.sort(key=lambda r: (-r["train"]["n"], r["patron"],
                                    r["direccion"], r["alineacion"],
                                    r["accion_precio"]))
    elegibles = [r for r in resultados
                 if r["muestra_suficiente_para_comparacion_exploratoria"]]
    return {
        "tipo": "INVESTIGACION_EXPLORATORIA_INTERACCIONES_SOMBRA",
        "estado": "ANALISIS_RETROSPECTIVO_PARTIDO",
        "filas_originales": len(originales),
        "oportunidades_depuradas": len(eventos),
        "sin_patron_unico": sin_patron_unico,
        "descartes": descartes,
        "dias_train": dias[:corte],
        "dias_validacion_posterior": dias[corte:],
        "total_interacciones": len(resultados),
        "interacciones_con_muestra_suficiente": len(elegibles),
        "interacciones_60_ambas_partes": sum(
            r["mejora_replicada_60_proxy"] for r in elegibles),
        "interacciones": resultados,
        "promueve_estrategia": False,
        "autoriza_real": False,
        "advertencia": ("La validacion posterior es solo retencion historica y se inspecciona "
                        "tras explorar múltiples hipótesis: NO es OOS fresco ni rentabilidad. "
                        "Un mismo minuto en varios activos puede estar correlacionado; "
                        "sin fills ni payout no hay beneficio monetario probado."),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archivo", default="auditoria_candidatas_sombra_practice.csv")
    p.add_argument("--min-train", type=int, default=40)
    p.add_argument("--min-valid", type=int, default=20)
    args = p.parse_args()
    print(json.dumps(analizar(leer_csv(args.archivo), args.min_train, args.min_valid),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
