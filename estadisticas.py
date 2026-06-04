import pandas as pd
import os
from config import HISTORIAL_CSV


def cargar_historial_cerrado():
    if not os.path.exists(HISTORIAL_CSV):
        return pd.DataFrame()

    try:
        df = pd.read_csv(HISTORIAL_CSV, encoding="utf-8-sig")

        if df.empty:
            return pd.DataFrame()

        df = df[df["estado"] == "CERRADA"].copy()
        df["resultado"] = pd.to_numeric(df["resultado"], errors="coerce")
        df = df.dropna(subset=["resultado"])

        return df

    except Exception as e:
        print("Error cargando estadísticas:", e)
        return pd.DataFrame()


def resumen_por_estrategia():
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    resumen = []

    for patron, grupo in df.groupby("patron"):
        total = len(grupo)
        ganadas = len(grupo[grupo["resultado"] > 0])
        perdidas = len(grupo[grupo["resultado"] < 0])
        empate = len(grupo[grupo["resultado"] == 0])
        neto = round(grupo["resultado"].sum(), 2)
        winrate = round((ganadas / total) * 100, 2) if total > 0 else 0

        resumen.append({
            "estrategia": patron,
            "total": total,
            "ganadas": ganadas,
            "perdidas": perdidas,
            "empate": empate,
            "winrate": winrate,
            "neto": neto
        })

    return sorted(resumen, key=lambda x: x["neto"], reverse=True)


def resumen_por_activo():
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    resumen = []

    for activo, grupo in df.groupby("activo"):
        total = len(grupo)
        ganadas = len(grupo[grupo["resultado"] > 0])
        perdidas = len(grupo[grupo["resultado"] < 0])
        empate = len(grupo[grupo["resultado"] == 0])
        neto = round(grupo["resultado"].sum(), 2)
        winrate = round((ganadas / total) * 100, 2) if total > 0 else 0

        resumen.append({
            "activo": activo,
            "total": total,
            "ganadas": ganadas,
            "perdidas": perdidas,
            "empate": empate,
            "winrate": winrate,
            "neto": neto
        })

    return sorted(resumen, key=lambda x: x["neto"], reverse=True)


def imprimir_estadisticas():
    estrategias = resumen_por_estrategia()
    activos = resumen_por_activo()

    if not estrategias and not activos:
        print("Estadísticas: sin historial suficiente.")
        return

    print("\n===== ESTADÍSTICAS POR ESTRATEGIA =====")

    for e in estrategias:
        print(
            e["estrategia"],
            "| total:", e["total"],
            "| ganadas:", e["ganadas"],
            "| perdidas:", e["perdidas"],
            "| winrate:", str(e["winrate"]) + "%",
            "| neto:", e["neto"]
        )

    print("\n===== ESTADÍSTICAS POR ACTIVO =====")

    for a in activos:
        print(
            a["activo"],
            "| total:", a["total"],
            "| ganadas:", a["ganadas"],
            "| perdidas:", a["perdidas"],
            "| winrate:", str(a["winrate"]) + "%",
            "| neto:", a["neto"]
        )


def estrategias_bloqueables(min_operaciones=8, winrate_minimo=40):
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    bloqueadas = []

    for patron, grupo in df.groupby("patron"):
        total = len(grupo)

        if total < min_operaciones:
            continue

        ganadas = len(grupo[grupo["resultado"] > 0])
        winrate = (ganadas / total) * 100

        if winrate < winrate_minimo:
            bloqueadas.append(patron)

    return bloqueadas


def activos_bloqueables(min_operaciones=6, winrate_minimo=40):
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    bloqueados = []

    for activo, grupo in df.groupby("activo"):
        total = len(grupo)

        if total < min_operaciones:
            continue

        ganadas = len(grupo[grupo["resultado"] > 0])
        winrate = (ganadas / total) * 100

        if winrate < winrate_minimo:
            bloqueados.append(activo)

    return bloqueados


def activo_bloqueado(activo):
    if not activo:
        return False

    return activo in activos_bloqueables()


def estrategia_bloqueada(patron):
    if not patron:
        return False

    return patron in estrategias_bloqueables()


def validar_senal_por_estadistica(senal):
    if not senal:
        return False, "señal vacía"

    activo = senal.get("activo")
    patron = senal.get("patron")

    if activo_bloqueado(activo):
        return False, "activo bloqueado por bajo rendimiento"

    if estrategia_bloqueada(patron):
        return False, "patrón bloqueado por bajo rendimiento"

    return True, "señal permitida por estadísticas"