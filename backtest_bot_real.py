import csv
import os
import contextlib
import io

import estado
import estrategia

CARPETA_DATA = "data_backtest"
SALIDA = "backtest_bot_real_resultados.csv"

MAX_ACTIVOS_ANALIZAR = 20
LIMITE_DATASETS = 160
PASO_RONDA = 3


def leer_csv_velas(ruta):
    velas = []

    with open(ruta, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            velas.append({
                "tipo": row.get("tipo", ""),
                "activo": row.get("activo", ""),
                "from": int(float(row["from"])),
                "open": float(row["open"]),
                "close": float(row["close"]),
                "max": float(row["max"]),
                "min": float(row["min"]),
                "volume": float(row.get("volume", 0) or 0),
            })

    return sorted(velas, key=lambda x: x["from"])


def cargar_datasets():
    datasets = []

    for archivo in os.listdir(CARPETA_DATA):
        if not archivo.endswith(".csv"):
            continue

        ruta = os.path.join(CARPETA_DATA, archivo)
        velas = leer_csv_velas(ruta)

        if len(velas) < 200:
            continue

        datasets.append({
            "tipo": velas[0].get("tipo", ""),
            "activo": velas[0].get("activo", archivo.replace(".csv", "")),
            "velas": velas
        })

    return datasets[:LIMITE_DATASETS]


def reset_estado():
    estado.cooldown_activos = {}
    estado.zonas_operadas = {}
    estado.snapshot_mercados = {}
    estado.cooldown_estrategias = {}
    estado.senales_pendientes = []
    estado.operaciones_abiertas = []


def analizar_activo_con_ventana(activo, ventana):
    data = {
        "open": [v["open"] for v in ventana],
        "close": [v["close"] for v in ventana],
        "high": [v["max"] for v in ventana],
        "low": [v["min"] for v in ventana],
    }

    original_obtener_velas = estrategia.obtener_velas
    estrategia.obtener_velas = lambda activo_param: data

    try:
       senal = estrategia.analizar_activo(activo)
    finally:
        estrategia.obtener_velas = original_obtener_velas

    return senal


def resultado_binario(velas, index_entrada, direccion):
    entrada = velas[index_entrada]["close"]
    cierre = velas[index_entrada + 1]["close"]

    if direccion == "call":
        return "WIN" if cierre > entrada else "LOSS"

    if direccion == "put":
        return "WIN" if cierre < entrada else "LOSS"

    return "LOSS"


def ejecutar_backtest(datasets):
    resultados = []
    max_len = min(len(d["velas"]) for d in datasets)

    total_rondas = len(range(180, max_len - 2, PASO_RONDA))
    ronda = 0

    for i in range(180, max_len - 2, PASO_RONDA):
        ronda += 1

        if ronda % 25 == 0:
            print("Progreso:", ronda, "/", total_rondas)

        senales_ronda = []

        for data in datasets:
            activo = data["activo"]
            tipo = data["tipo"]
            velas = data["velas"]
            ventana = velas[i - 180:i + 1]

            senal = analizar_activo_con_ventana(activo, ventana)

            if senal is None:
                continue

            senal["tipo"] = tipo
            senal["_velas"] = velas
            senal["_index"] = i

            senales_ronda.append(senal)

        senales_ronda = sorted(
            senales_ronda,
            key=lambda x: (
                x.get("prioridad", 0),
                x.get("puntaje", 0)
            ),
            reverse=True
        )

        for senal in senales_ronda[:MAX_ACTIVOS_ANALIZAR]:
            velas = senal["_velas"]
            idx = senal["_index"]

            resultado = resultado_binario(
                velas,
                idx,
                senal["direccion"]
            )

            resultados.append({
                "tipo": senal.get("tipo", ""),
                "activo": senal.get("activo", ""),
                "fecha": velas[idx]["from"],
                "direccion": senal.get("direccion", ""),
                "patron": senal.get("patron", ""),
                "puntaje": senal.get("puntaje", 0),
                "prioridad": senal.get("prioridad", 0),
                "calidad": senal.get("calidad", ""),
                "rsi": senal.get("rsi", ""),
                "tipo_mercado": senal.get("tipo_mercado", ""),
                "calidad_mercado": senal.get("calidad_mercado", ""),
                "score_mercado": senal.get("score_mercado", 0),
                "estado_tendencia": senal.get("estado_tendencia", ""),
                "resultado": resultado,
                "precio_entrada": velas[idx]["close"],
                "precio_cierre": velas[idx + 1]["close"],
            })

    return resultados


def guardar_resultados(resultados):
    campos = [
        "tipo",
        "activo",
        "fecha",
        "direccion",
        "patron",
        "puntaje",
        "prioridad",
        "calidad",
        "rsi",
        "tipo_mercado",
        "calidad_mercado",
        "score_mercado",
        "estado_tendencia",
        "resultado",
        "precio_entrada",
        "precio_cierre",
    ]

    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados)


def resumen_por_campo(resultados, campo):
    grupos = {}

    for r in resultados:
        clave = r.get(campo, "")

        if clave not in grupos:
            grupos[clave] = {"total": 0, "win": 0}

        grupos[clave]["total"] += 1

        if r["resultado"] == "WIN":
            grupos[clave]["win"] += 1

    filas = []

    for clave, d in grupos.items():
        wr = round((d["win"] / d["total"]) * 100, 2)
        filas.append((clave, d["total"], d["win"], d["total"] - d["win"], wr))

    return sorted(filas, key=lambda x: x[4], reverse=True)


def imprimir_resumen(resultados):
    total = len(resultados)
    wins = sum(1 for r in resultados if r["resultado"] == "WIN")
    losses = total - wins
    wr = round((wins / total) * 100, 2) if total else 0

    print("\n===== BACKTEST BOT REAL =====")
    print("Datasets:", LIMITE_DATASETS)
    print("Paso ronda:", PASO_RONDA)
    print("Total operaciones:", total)
    print("Ganadas:", wins)
    print("Perdidas:", losses)
    print("Winrate:", wr, "%")
    print("============================\n")

    for titulo, campo in [
        ("POR ESTRATEGIA", "patron"),
        ("POR TIPO", "tipo"),
        ("POR MERCADO", "tipo_mercado"),
        ("POR CALIDAD MERCADO", "calidad_mercado"),
        ("POR ACTIVO", "activo"),
    ]:
        print("\n=====", titulo, "=====")
        for clave, total, win, loss, winrate in resumen_por_campo(resultados, campo)[:20]:
            print(
                clave,
                "| total:", total,
                "| win:", win,
                "| loss:", loss,
                "| winrate:", str(winrate) + "%"
            )


def main():
    reset_estado()

    datasets = cargar_datasets()

    print("Datasets cargados:", len(datasets))
    print("Ejecutando backtest usando analizar_activo() real...")

    resultados = ejecutar_backtest(datasets)

    guardar_resultados(resultados)
    imprimir_resumen(resultados)

    print("Archivo generado:", SALIDA)


if __name__ == "__main__":
    main()