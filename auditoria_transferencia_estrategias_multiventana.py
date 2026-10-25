"""Transferencia de estrategias entre ventanas OOS sobre mercados comunes.

Análisis descriptivo solamente: WIN/LOSS hipotéticos no son operaciones
ejecutadas. No activa señales ni modifica la autoridad del cerebro.
"""
import csv
import itertools
import zipfile
from collections import Counter, defaultdict
from io import TextIOWrapper


FACTORES = ("patron", "tipo_mercado", "direccion", "estado_tendencia", "accion_precio")


def evaluar_transferencia_estrategias(train, oos, minimo_por_periodo=30,
                                    objetivo_winrate=59.0, max_factores=3):
    train = [r for r in train if isinstance(r,dict)]
    oos = [r for r in oos if isinstance(r,dict)]
    activos = {str(r.get("activo")) for r in train if r.get("activo")} & {
        str(r.get("activo")) for r in oos if r.get("activo")
    }
    contador = defaultdict(Counter)
    universos = Counter()
    for periodo, filas in (("TRAIN", train), ("OOS", oos)):
        for fila in filas:
            if fila.get("activo") not in activos:
                continue
            resultado = str(fila.get("resultado_hipotetico") or "").upper()
            if resultado not in {"WIN","LOSS"}:
                continue
            universos[periodo] += 1
            for n in range(1, max_factores+1):
                for combinacion in itertools.combinations(FACTORES,n):
                    clave = tuple((campo,str(fila.get(campo) or "")) for campo in combinacion)
                    if all(valor for _,valor in clave):
                        contador[clave][(periodo,resultado)] += 1
    resultados = []
    for clave, c in contador.items():
        nt = c[("TRAIN","WIN")] + c[("TRAIN","LOSS")]
        no = c[("OOS","WIN")] + c[("OOS","LOSS")]
        if min(nt,no) < minimo_por_periodo:
            continue
        wt = 100*c[("TRAIN","WIN")]/nt
        wo = 100*c[("OOS","WIN")]/no
        resultados.append({
            "factores": clave,
            "n_train": nt, "n_oos": no,
            "wr_train_hipotetico": round(wt,2),
            "wr_oos_hipotetico": round(wo,2),
            "objetivo_59_en_ambos": wt >= objetivo_winrate and wo >= objetivo_winrate,
            "participacion_oos_pct": round(100*no/universos["OOS"],2) if universos["OOS"] else None,
            "autoriza_trading": False,
        })
    resultados.sort(key=lambda x:(-x["n_oos"],x["factores"]))
    return {
        "mercados_comunes": len(activos),
        "senales_train_comunes": universos["TRAIN"],
        "senales_oos_comunes": universos["OOS"],
        "combinaciones_elegibles": len(resultados),
        "combinaciones_superan_59_ambos": sum(r["objetivo_59_en_ambos"] for r in resultados),
        "resultados": resultados,
    }


def leer_csv_o_zip(ruta):
    if str(ruta).lower().endswith(".zip"):
        with zipfile.ZipFile(ruta) as comprimido:
            archivos = [x for x in comprimido.namelist() if x.lower().endswith(".csv")]
            if len(archivos) != 1:
                raise ValueError("El ZIP debe tener un único CSV")
            with comprimido.open(archivos[0]) as archivo:
                return list(csv.DictReader(TextIOWrapper(archivo,encoding="utf-8-sig")))
    with open(ruta,encoding="utf-8-sig",newline="") as archivo:
        return list(csv.DictReader(archivo))


def main():
    import argparse
    p=argparse.ArgumentParser(description="Transferencia multiventana sin brokers")
    p.add_argument("train_csv_o_zip")
    p.add_argument("oos_csv_o_zip")
    args=p.parse_args()
    out=evaluar_transferencia_estrategias(leer_csv_o_zip(args.train_csv_o_zip),
                                         leer_csv_o_zip(args.oos_csv_o_zip))
    print("MERCADOS_COMUNES",out["mercados_comunes"])
    print("SENALES_TRAIN_COMUNES",out["senales_train_comunes"])
    print("SENALES_OOS_COMUNES",out["senales_oos_comunes"])
    print("COMBINACIONES_ELEGIBLES",out["combinaciones_elegibles"])
    print("SUPERAN_59_AMBOS",out["combinaciones_superan_59_ambos"])


if __name__=="__main__":
    main()
