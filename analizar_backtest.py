import csv
from collections import defaultdict

ARCHIVO = "backtest_resultados.csv"


def cargar_resultados():
    datos = []

    with open(ARCHIVO, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            datos.append(row)

    return datos


def resumen_grupo(datos, campo, minimo=30):
    grupos = defaultdict(lambda: {"total": 0, "win": 0, "loss": 0})

    for r in datos:
        clave = r[campo]
        grupos[clave]["total"] += 1

        if r["resultado"] == "WIN":
            grupos[clave]["win"] += 1
        else:
            grupos[clave]["loss"] += 1

    filas = []

    for clave, d in grupos.items():
        if d["total"] < minimo:
            continue

        winrate = round((d["win"] / d["total"]) * 100, 2)

        filas.append({
            "grupo": clave,
            "total": d["total"],
            "win": d["win"],
            "loss": d["loss"],
            "winrate": winrate,
        })

    return sorted(filas, key=lambda x: x["winrate"], reverse=True)


def resumen_combinado(datos, campos, minimo=30):
    grupos = defaultdict(lambda: {"total": 0, "win": 0, "loss": 0})

    for r in datos:
        clave = " | ".join(r[c] for c in campos)
        grupos[clave]["total"] += 1

        if r["resultado"] == "WIN":
            grupos[clave]["win"] += 1
        else:
            grupos[clave]["loss"] += 1

    filas = []

    for clave, d in grupos.items():
        if d["total"] < minimo:
            continue

        winrate = round((d["win"] / d["total"]) * 100, 2)

        filas.append({
            "grupo": clave,
            "total": d["total"],
            "win": d["win"],
            "loss": d["loss"],
            "winrate": winrate,
        })

    return sorted(filas, key=lambda x: x["winrate"], reverse=True)


def imprimir_tabla(titulo, filas, limite=15):
    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    for f in filas[:limite]:
        print(
            f["grupo"],
            "| total:", f["total"],
            "| win:", f["win"],
            "| loss:", f["loss"],
            "| winrate:", str(f["winrate"]) + "%"
        )


def main():
    datos = cargar_resultados()

    print("Total registros:", len(datos))

    imprimir_tabla(
        "MEJORES ACTIVOS",
        resumen_grupo(datos, "activo", minimo=100),
        limite=20
    )

    imprimir_tabla(
        "PEORES ACTIVOS",
        list(reversed(resumen_grupo(datos, "activo", minimo=100))),
        limite=20
    )

    imprimir_tabla(
        "POR DIRECCIÓN",
        resumen_grupo(datos, "direccion", minimo=100),
        limite=10
    )

    imprimir_tabla(
        "POR PATRÓN",
        resumen_grupo(datos, "patron", minimo=100),
        limite=10
    )

    imprimir_tabla(
        "MEJOR ACTIVO + PATRÓN",
        resumen_combinado(datos, ["activo", "patron"], minimo=40),
        limite=25
    )

    imprimir_tabla(
        "MEJOR ACTIVO + DIRECCIÓN",
        resumen_combinado(datos, ["activo", "direccion"], minimo=40),
        limite=25
    )


if __name__ == "__main__":
    main()