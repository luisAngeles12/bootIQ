import os
import pandas as pd
from datetime import datetime, timedelta
from config import HISTORIAL_CSV


# =========================
# CARGAR HISTORIAL CERRADO
# =========================
def cargar_historial_cerrado():
    if not os.path.exists(HISTORIAL_CSV):
        return pd.DataFrame()

    try:
        df = pd.read_csv(HISTORIAL_CSV, encoding="utf-8-sig")

        if df.empty:
            return pd.DataFrame()

        if "estado" not in df.columns:
            return pd.DataFrame()

        df = df[df["estado"] == "CERRADA"].copy()

        if df.empty:
            return pd.DataFrame()

        df["resultado"] = pd.to_numeric(df["resultado"], errors="coerce")
        df = df.dropna(subset=["resultado"])

        if "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df = df.dropna(subset=["fecha"])
            df = df.sort_values("fecha")

        return df

    except Exception as e:
        print("Error cargando historial estadístico:", e)
        return pd.DataFrame()


# =========================
# RESUMEN POR ESTRATEGIA
# =========================
def resumen_por_estrategia():
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    resumen = []

    for patron, grupo in df.groupby("patron"):
        total = len(grupo)
        ganadas = len(grupo[grupo["resultado"] > 0])
        perdidas = len(grupo[grupo["resultado"] < 0])
        empates = len(grupo[grupo["resultado"] == 0])
        neto = round(grupo["resultado"].sum(), 2)
        winrate = round((ganadas / total) * 100, 2) if total > 0 else 0

        resumen.append({
            "estrategia": patron,
            "total": total,
            "ganadas": ganadas,
            "perdidas": perdidas,
            "empates": empates,
            "winrate": winrate,
            "neto": neto
        })

    return sorted(resumen, key=lambda x: x["neto"], reverse=True)


# =========================
# RESUMEN POR ACTIVO
# =========================
def resumen_por_activo():
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    resumen = []

    for activo, grupo in df.groupby("activo"):
        total = len(grupo)
        ganadas = len(grupo[grupo["resultado"] > 0])
        perdidas = len(grupo[grupo["resultado"] < 0])
        empates = len(grupo[grupo["resultado"] == 0])
        neto = round(grupo["resultado"].sum(), 2)
        winrate = round((ganadas / total) * 100, 2) if total > 0 else 0

        resumen.append({
            "activo": activo,
            "total": total,
            "ganadas": ganadas,
            "perdidas": perdidas,
            "empates": empates,
            "winrate": winrate,
            "neto": neto
        })

    return sorted(resumen, key=lambda x: x["neto"], reverse=True)


# =========================
# IMPRIMIR ESTADÍSTICAS
# =========================
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


# =========================
# PÉRDIDAS CONSECUTIVAS POR ACTIVO
# =========================
def perdidas_consecutivas_activo(activo):
    df = cargar_historial_cerrado()

    if df.empty or not activo:
        return 0, None

    if "activo" not in df.columns or "fecha" not in df.columns:
        return 0, None

    df_activo = df[df["activo"] == activo].copy()

    if df_activo.empty:
        return 0, None

    df_activo = df_activo.sort_values("fecha")

    contador = 0
    ultima_fecha = None

    for _, fila in df_activo.iloc[::-1].iterrows():
        resultado = fila["resultado"]

        if resultado < 0:
            contador += 1
            ultima_fecha = fila["fecha"]
        elif resultado > 0:
            break

    return contador, ultima_fecha


# =========================
# COOLDOWN TEMPORAL POR ACTIVO
# =========================
def activo_en_cooldown_por_perdidas(
    activo,
    perdidas_maximas=3,
    minutos_bloqueo=30
):
    perdidas, ultima_fecha = perdidas_consecutivas_activo(activo)

    if perdidas < perdidas_maximas:
        return False, "activo sin racha negativa"

    if ultima_fecha is None:
        return False, "sin fecha válida para cooldown"

    desbloqueo = ultima_fecha + timedelta(minutes=minutos_bloqueo)
    ahora = datetime.now()

    if ahora < desbloqueo:
        minutos_restantes = round((desbloqueo - ahora).total_seconds() / 60, 1)
        return True, (
            "activo en cooldown por "
            + str(perdidas)
            + " pérdidas consecutivas. Restan "
            + str(minutos_restantes)
            + " minutos"
        )

    return False, "cooldown terminado"


# =========================
# ACTIVOS BLOQUEABLES
# =========================
def activos_bloqueables(
    min_operaciones=6,
    winrate_minimo=40,
    neto_minimo=-40,
    perdidas_maximas=3,
    minutos_bloqueo=30
):
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    bloqueados = set()

    # Bloqueo temporal por pérdidas consecutivas.
    for activo in df["activo"].dropna().unique():
        bloqueado, _ = activo_en_cooldown_por_perdidas(
            activo,
            perdidas_maximas=perdidas_maximas,
            minutos_bloqueo=minutos_bloqueo
        )

        if bloqueado:
            bloqueados.add(activo)

    # Bloqueo por rendimiento general, solo con muestra suficiente.
    for activo, grupo in df.groupby("activo"):
        total = len(grupo)

        if total < min_operaciones:
            continue

        ganadas = len(grupo[grupo["resultado"] > 0])
        neto = grupo["resultado"].sum()
        winrate = (ganadas / total) * 100 if total > 0 else 0

        if winrate < winrate_minimo or neto <= neto_minimo:
            bloqueados.add(activo)

    return list(bloqueados)


# =========================
# ESTRATEGIAS BLOQUEABLES
# =========================
def estrategias_bloqueables(
    min_operaciones=8,
    winrate_minimo=40,
    neto_minimo=-40
):
    df = cargar_historial_cerrado()

    if df.empty:
        return []

    bloqueadas = []

    for patron, grupo in df.groupby("patron"):
        total = len(grupo)

        if total < min_operaciones:
            continue

        ganadas = len(grupo[grupo["resultado"] > 0])
        neto = grupo["resultado"].sum()
        winrate = (ganadas / total) * 100 if total > 0 else 0

        if winrate < winrate_minimo or neto <= neto_minimo:
            bloqueadas.append(patron)

    return bloqueadas


# =========================
# VALIDADORES INDIVIDUALES
# =========================
def activo_bloqueado(activo):
    if not activo:
        return False

    return activo in activos_bloqueables()


def razon_activo_bloqueado(activo):
    if not activo:
        return "activo inválido"

    bloqueado, razon = activo_en_cooldown_por_perdidas(activo)

    if bloqueado:
        return razon

    if activo in activos_bloqueables():
        return "activo bloqueado por bajo rendimiento general"

    return "activo permitido"


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
        return False, razon_activo_bloqueado(activo)

    if estrategia_bloqueada(patron):
        return False, "estrategia bloqueada por bajo rendimiento"

    return True, "señal permitida por estadísticas"