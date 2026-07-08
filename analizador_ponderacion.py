import csv
from collections import defaultdict

RUTA_CSV = "backtest_bot_real_resultados.csv"
MIN_MUESTRA = 5


def _txt(v):
    return str(v or "").strip()


def _num(v, defecto=0):
    try:
        return float(v)
    except Exception:
        return defecto


def _resultado_win(row):
    return _txt(row.get("resultado")).upper() == "WIN"


def cargar_csv(ruta=RUTA_CSV):
    with open(ruta, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resumir_grupo(nombre, grupos):
    print("\n===== " + nombre + " =====")

    filas = []

    for clave, datos in grupos.items():
        total = datos["total"]
        wins = datos["wins"]
        losses = datos["losses"]

        if total < MIN_MUESTRA:
            continue

        winrate = round((wins / total) * 100, 2)

        filas.append({
            "clave": clave,
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
        })

    filas = sorted(filas, key=lambda x: (x["winrate"], x["total"]), reverse=True)

    for f in filas[:40]:
        print(
            f"{f['clave']} | total: {f['total']} | "
            f"win: {f['wins']} | loss: {f['losses']} | "
            f"winrate: {f['winrate']}%"
        )


def analizar_por_columna(rows, columna):
    grupos = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})

    for row in rows:
        clave = _txt(row.get(columna))

        if not clave:
            clave = "SIN_DATO"

        grupos[clave]["total"] += 1

        if _resultado_win(row):
            grupos[clave]["wins"] += 1
        else:
            grupos[clave]["losses"] += 1

    return grupos


def analizar_motivos_individuales(rows):
    grupos = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})

    for row in rows:
        motivos = _txt(row.get("motivos_ponderacion"))
        resultado_win = _resultado_win(row)

        for motivo in motivos.split("|"):
            motivo = motivo.strip()

            if not motivo:
                continue

            grupos[motivo]["total"] += 1

            if resultado_win:
                grupos[motivo]["wins"] += 1
            else:
                grupos[motivo]["losses"] += 1

    return grupos


def analizar_pesos_individuales(rows):
    grupos = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})

    for row in rows:
        pesos = _txt(row.get("pesos_aplicados"))
        resultado_win = _resultado_win(row)

        for peso in pesos.split("|"):
            peso = peso.strip()

            if not peso:
                continue

            grupos[peso]["total"] += 1

            if resultado_win:
                grupos[peso]["wins"] += 1
            else:
                grupos[peso]["losses"] += 1

    return grupos


def generar_recomendaciones(rows):
    print("\n===== RECOMENDACIONES AUTOMÁTICAS =====")

    grupos_motivos = analizar_motivos_individuales(rows)

    recomendaciones = []

    for motivo, d in grupos_motivos.items():
        total = d["total"]

        if total < MIN_MUESTRA:
            continue

        winrate = round((d["wins"] / total) * 100, 2)

        motivo_lower = motivo.lower()

        if winrate >= 55 and "(-" in motivo:
            recomendaciones.append(
                f"REVISAR CASTIGO: {motivo} tiene winrate {winrate}% en {total} casos."
            )

        elif winrate <= 42 and "(+" in motivo:
            recomendaciones.append(
                f"REVISAR BONO: {motivo} tiene winrate {winrate}% en {total} casos."
            )

        elif winrate >= 60 and "(+" in motivo:
            recomendaciones.append(
                f"MANTENER/REFORZAR BONO: {motivo} tiene winrate {winrate}% en {total} casos."
            )

        elif winrate <= 40 and "(-" in motivo:
            recomendaciones.append(
                f"MANTENER/ENDURECER CASTIGO: {motivo} tiene winrate {winrate}% en {total} casos."
            )

    if not recomendaciones:
        print("No hay recomendaciones suficientes con la muestra actual.")
        return

    for r in recomendaciones[:50]:
        print("-", r)


def main():
    rows = cargar_csv()

    print("\n===== ANALIZADOR DE PONDERACIÓN BOOTIQ =====")
    print("Total filas:", len(rows))

    resumir_grupo(
        "POR AJUSTE PONDERACION",
        analizar_por_columna(rows, "ajuste_ponderacion")
    )

    resumir_grupo(
        "POR DECISION CEREBRO",
        analizar_por_columna(rows, "cerebro_unico_decision")
    )

    resumir_grupo(
        "POR DECISION BOOTIQ",
        analizar_por_columna(rows, "bootiq_decision_unificada_accion")
    )

    resumir_grupo(
        "POR MOTIVOS DE PONDERACION",
        analizar_motivos_individuales(rows)
    )

    resumir_grupo(
        "POR PESOS INDIVIDUALES",
        analizar_pesos_individuales(rows)
    )

    generar_recomendaciones(rows)


if __name__ == "__main__":
    main()