import csv
import os
import contextlib
import io

import estado
import estrategia

from contexto_mercado import (
    detectar_tipo_mercado,
    diagnostico_calidad_mercado,
    diagnostico_tendencia_avanzada
)

CARPETA_DATA = "data_backtest"
SALIDA = "backtest_real_resultados.csv"

MAX_ACTIVOS_ANALIZAR = 40
MIN_SCORE_ACTIVO = 65

# Para que corra más rápido
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

        tipo = velas[0].get("tipo", "")
        activo = velas[0].get("activo", archivo.replace(".csv", ""))

        datasets.append({
            "tipo": tipo,
            "activo": activo,
            "velas": velas
        })

    return datasets


def construir_ctx_backtest(activo, ventana):
    opens = [v["open"] for v in ventana]
    closes = [v["close"] for v in ventana]
    highs = [v["max"] for v in ventana]
    lows = [v["min"] for v in ventana]

    if len(closes) < 130:
        return None

    data = {
        "open": opens,
        "close": closes,
        "high": highs,
        "low": lows,
    }

    original_obtener_velas = estrategia.obtener_velas
    estrategia.obtener_velas = lambda activo_param: data

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ctx = estrategia.leer_contexto_grafico(activo)
    finally:
        estrategia.obtener_velas = original_obtener_velas

    if ctx is None:
        return None

    candles_contexto = []

    for i in range(len(closes)):
        candles_contexto.append({
            "from": i,
            "open": opens[i],
            "close": closes[i],
            "max": highs[i],
            "min": lows[i],
        })

    tipo_mercado, razon_mercado = detectar_tipo_mercado(candles_contexto)
    diagnostico = diagnostico_calidad_mercado(candles_contexto)
    tendencia = diagnostico_tendencia_avanzada(candles_contexto)

    ctx["tipo_mercado"] = tipo_mercado
    ctx["razon_mercado"] = razon_mercado
    ctx["calidad_mercado"] = diagnostico.get("calidad", "SIN_DATOS")
    ctx["score_mercado"] = diagnostico.get("score", 0)
    ctx["estado_tendencia"] = tendencia.get("estado_tendencia", "INDEFINIDA")
    ctx["fuerza_tendencia"] = tendencia.get("fuerza_tendencia", 0)
    ctx["direccion_tendencia"] = tendencia.get("direccion_tendencia", "INDEFINIDA")

    return ctx


def calcular_score_filtro(ctx, activo):
    calidad = ctx.get("calidad_mercado", "SIN_DATOS")
    score = ctx.get("score_mercado", 0)
    tipo_mercado = ctx.get("tipo_mercado", "INDEFINIDO")
    estado_tendencia = ctx.get("estado_tendencia", "INDEFINIDA")
    fuerza_tendencia = ctx.get("fuerza_tendencia", 0)

    if "-op" in activo:
        return None

    if "/" in activo:
        return None

    if calidad not in ["LIMPIO", "NORMAL"]:
        return None

    if score < 58:
        return None

    if estado_tendencia == "INDEFINIDA":
        return None

    if "DEBIL" in estado_tendencia and score < 68:
        return None

    if "AGOTADA" in estado_tendencia:
        return None

    if (
        tipo_mercado == "RANGO"
        and "FUERTE" not in estado_tendencia
        and "NORMAL" not in estado_tendencia
    ):
        return None

    score_filtro = score

    if calidad == "LIMPIO":
        score_filtro += 25

    if calidad == "NORMAL":
        score_filtro += 15

    if "FUERTE" in estado_tendencia:
        score_filtro += 25

    if "NORMAL" in estado_tendencia:
        score_filtro += 15

    if tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]:
        score_filtro += 15

    if tipo_mercado == "RANGO":
        score_filtro -= 5

    if "-OTC" in activo:
        score_filtro += 5

    if score_filtro < MIN_SCORE_ACTIVO:
        return None

    return {
        "score_filtro": score_filtro,
        "calidad": calidad,
        "score": score,
        "tipo_mercado": tipo_mercado,
        "estado_tendencia": estado_tendencia,
        "fuerza_tendencia": fuerza_tendencia,
    }


def filtrar_senales_reales(senales):
    limpias = []

    for s in senales:
        if s is None:
            continue

        patron = str(s.get("patron", "")).lower()

        # Núcleo ganador actual
        if "liquidity sweep" in patron:
            continue

        if "pullback" in patron:
            continue

        if "continuación" in patron or "continuacion" in patron:
            continue

        limpias.append(s)

    return limpias


def resultado_binario(velas, index_entrada, direccion):
    entrada = velas[index_entrada]["close"]
    cierre = velas[index_entrada + 1]["close"]

    if direccion == "call":
        return "WIN" if cierre > entrada else "LOSS"

    if direccion == "put":
        return "WIN" if cierre < entrada else "LOSS"

    return "LOSS"


def reset_estado_backtest():
    estado.cooldown_activos = {}
    estado.zonas_operadas = {}
    estado.snapshot_mercados = {}
    estado.cooldown_estrategias = {}
    estado.senales_pendientes = []


def ejecutar_backtest(datasets):
    resultados = []

    max_len = min(len(d["velas"]) for d in datasets)

    total_rondas = len(range(180, max_len - 2, PASO_RONDA))
    ronda_actual = 0

    for i in range(180, max_len - 2, PASO_RONDA):
        ronda_actual += 1

        if ronda_actual % 25 == 0:
            print("Progreso:", ronda_actual, "/", total_rondas)

        candidatos = []

        for data in datasets:
            activo = data["activo"]
            tipo = data["tipo"]
            velas = data["velas"]
            ventana = velas[i - 180:i + 1]

            ctx = construir_ctx_backtest(activo, ventana)

            if ctx is None:
                continue

            filtro = calcular_score_filtro(ctx, activo)

            if filtro is None:
                continue

            candidatos.append({
                "activo": activo,
                "tipo": tipo,
                "velas": velas,
                "ctx": ctx,
                "score_filtro": filtro["score_filtro"]
            })

        candidatos = sorted(
            candidatos,
            key=lambda x: x["score_filtro"],
            reverse=True
        )

        top_activos = candidatos[:MAX_ACTIVOS_ANALIZAR]

        for item in top_activos:
            activo = item["activo"]
            tipo = item["tipo"]
            velas = item["velas"]
            ctx = item["ctx"]

            with contextlib.redirect_stdout(io.StringIO()):
                senales = estrategia.motor_estrategias_profesional(ctx)

            if not senales:
                continue

            if isinstance(senales, dict):
                senales = [senales]

            senales = filtrar_senales_reales(senales)

            if not senales:
                continue

            senales = sorted(
                senales,
                key=lambda x: (
                    x.get("score_final", 0),
                    x.get("prioridad", 0),
                    x.get("puntaje", 0)
                ),
                reverse=True
            )

            senal = senales[0]

            resultado = resultado_binario(
                velas,
                i,
                senal["direccion"]
            )

            resultados.append({
                "tipo": tipo,
                "activo": activo,
                "fecha": velas[i]["from"],
                "direccion": senal["direccion"],
                "patron": senal["patron"],
                "puntaje": senal.get("puntaje", 0),
                "prioridad": senal.get("prioridad", 0),
                "score_final": senal.get("score_final", 0),
                "calidad": senal.get("calidad", ""),
                "rsi": senal.get("rsi", ""),
                "tipo_mercado": ctx.get("tipo_mercado", ""),
                "calidad_mercado": ctx.get("calidad_mercado", ""),
                "score_mercado": ctx.get("score_mercado", 0),
                "estado_tendencia": ctx.get("estado_tendencia", ""),
                "score_filtro": item["score_filtro"],
                "resultado": resultado,
                "precio_entrada": velas[i]["close"],
                "precio_cierre": velas[i + 1]["close"],
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
        "score_final",
        "calidad",
        "rsi",
        "tipo_mercado",
        "calidad_mercado",
        "score_mercado",
        "estado_tendencia",
        "score_filtro",
        "resultado",
        "precio_entrada",
        "precio_cierre",
    ]

    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for r in resultados:
            writer.writerow(r)


def resumen_por_campo(resultados, campo, minimo=1):
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
        if d["total"] < minimo:
            continue

        wr = round((d["win"] / d["total"]) * 100, 2)

        filas.append({
            "clave": clave,
            "total": d["total"],
            "win": d["win"],
            "loss": d["total"] - d["win"],
            "winrate": wr
        })

    return sorted(filas, key=lambda x: x["winrate"], reverse=True)


def imprimir_resumen(resultados):
    total = len(resultados)
    ganadas = sum(1 for r in resultados if r["resultado"] == "WIN")
    perdidas = total - ganadas
    winrate = round((ganadas / total) * 100, 2) if total else 0

    print("\n===== BACKTEST REAL TOP", MAX_ACTIVOS_ANALIZAR, "=====")
    print("Datasets usados:", LIMITE_DATASETS)
    print("Paso ronda:", PASO_RONDA)
    print("Total operaciones:", total)
    print("Ganadas:", ganadas)
    print("Perdidas:", perdidas)
    print("Winrate:", winrate, "%")
    print("===============================\n")

    print("===== POR ESTRATEGIA =====")
    for f in resumen_por_campo(resultados, "patron", minimo=1):
        print(
            f["clave"],
            "| total:", f["total"],
            "| win:", f["win"],
            "| loss:", f["loss"],
            "| winrate:", str(f["winrate"]) + "%"
        )

    print("\n===== POR TIPO =====")
    for f in resumen_por_campo(resultados, "tipo", minimo=1):
        print(
            f["clave"],
            "| total:", f["total"],
            "| winrate:", str(f["winrate"]) + "%"
        )

    print("\n===== POR MERCADO =====")
    for f in resumen_por_campo(resultados, "tipo_mercado", minimo=1):
        print(
            f["clave"],
            "| total:", f["total"],
            "| winrate:", str(f["winrate"]) + "%"
        )

    print("\n===== POR CALIDAD MERCADO =====")
    for f in resumen_por_campo(resultados, "calidad_mercado", minimo=1):
        print(
            f["clave"],
            "| total:", f["total"],
            "| winrate:", str(f["winrate"]) + "%"
        )

    print("\n===== MEJORES ACTIVOS =====")
    for f in resumen_por_campo(resultados, "activo", minimo=5)[:20]:
        print(
            f["clave"],
            "| total:", f["total"],
            "| winrate:", str(f["winrate"]) + "%"
        )


def main():
    reset_estado_backtest()

    datasets = cargar_datasets()

    datasets = datasets[:LIMITE_DATASETS]

    print("Datasets cargados:", len(datasets))
    print("Simulando TOP", MAX_ACTIVOS_ANALIZAR, "por score_filtro...")
    print("PASO_RONDA:", PASO_RONDA)

    resultados = ejecutar_backtest(datasets)

    guardar_resultados(resultados)
    imprimir_resumen(resultados)

    print("Archivo generado:", SALIDA)


if __name__ == "__main__":
    main()