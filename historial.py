import os
import json
import pandas as pd
import estado
from config import HISTORIAL_CSV, OPERACIONES_PENDIENTES_JSON

def columnas_historial():
    return ["fecha", "estado", "order_id", "activo", "tipo", "direccion", "puntaje", "patron", "rsi", "resultado", "razon"]


COLUMNAS_HISTORIAL = ["fecha", "estado", "order_id", "activo", "tipo", "direccion", "puntaje", "patron", "rsi", "resultado", "razon"]

def guardar_historial(data):
    asegurar_historial_csv()

    ruta = os.path.abspath(HISTORIAL_CSV)
    print("Guardando historial en:", ruta)

    cols = COLUMNAS_HISTORIAL
    fila = {col: data.get(col, "") for col in cols}

    try:
        df = pd.DataFrame([fila], columns=cols)
        df.to_csv(
            HISTORIAL_CSV,
            mode="a",
            header=False,
            index=False,
            encoding="utf-8-sig"
        )
    except Exception as e:
        print("Error guardando historial:", e)


def asegurar_historial_csv():
    if not os.path.exists(HISTORIAL_CSV):
        df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")
        return

    if os.path.getsize(HISTORIAL_CSV) == 0:
        df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")
        return

    try:
        df = pd.read_csv(HISTORIAL_CSV, encoding="utf-8-sig")

        if df.empty:
            df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
            df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")
            return

        columnas_actuales = list(df.columns)

        if "order_id" not in columnas_actuales:
            print("Historial viejo detectado. Se recreará con columnas correctas.")
            df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
            df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")
            return

        for col in COLUMNAS_HISTORIAL:
            if col not in df.columns:
                df[col] = ""

        df = df[COLUMNAS_HISTORIAL]
        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")

    except Exception as e:
        print("Historial dañado. Se recreará:", e)
        df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")


def actualizar_historial_cierre(order_id, resultado):
    asegurar_historial_csv()

    try:
        df = pd.read_csv(HISTORIAL_CSV, encoding="utf-8-sig")

        if "order_id" not in df.columns:
            print("Historial sin order_id. No se puede actualizar cierre.")
            return False

        df["order_id"] = df["order_id"].astype(str)
        order_id = str(order_id)

        mask = df["order_id"] == order_id

        if not mask.any():
            print("No existe historial para actualizar:", order_id)
            return False

        df.loc[mask, "estado"] = "CERRADA"
        df.loc[mask, "resultado"] = round(float(resultado), 2)

        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")

        print("Historial actualizado:", order_id, round(float(resultado), 2))
        return True

    except Exception as e:
        print("Error actualizando historial:", e)
        return False


def cargar_historial():
    if not os.path.exists(HISTORIAL_CSV):
        return None

    if os.path.getsize(HISTORIAL_CSV) == 0:
        return None

    try:
        df = pd.read_csv(HISTORIAL_CSV, encoding="utf-8-sig")

        if df.empty:
            return None

        if "estado" not in df.columns or "resultado" not in df.columns:
            return None

        df = df[df["estado"] == "CERRADA"]
        df["resultado"] = pd.to_numeric(df["resultado"], errors="coerce")
        df = df.dropna(subset=["resultado"])

        if df.empty:
            return None

        return df

    except Exception:
        return None


def guardar_operaciones_pendientes():
    try:
        with open(OPERACIONES_PENDIENTES_JSON, "w", encoding="utf-8") as f:
            json.dump(estado.operaciones_abiertas, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error guardando operaciones pendientes:", e)


def cargar_operaciones_pendientes():
    if not os.path.exists(OPERACIONES_PENDIENTES_JSON):
        return
    try:
        with open(OPERACIONES_PENDIENTES_JSON, "r", encoding="utf-8") as f:
            estado.operaciones_abiertas = json.load(f)
        if not isinstance(estado.operaciones_abiertas, list):
            estado.operaciones_abiertas = []
        print("Operaciones pendientes recuperadas:", len(estado.operaciones_abiertas))
    except Exception as e:
        print("Error cargando operaciones pendientes:", e)
        estado.operaciones_abiertas = []


def winrate_activo(activo):
    df = cargar_historial()
    if df is None:
        return 0.5
    df = df[df["activo"] == activo]
    if len(df) < 5:
        return 0.5
    return len(df[df["resultado"] > 0]) / len(df)


def winrate_patron(patron):
    df = cargar_historial()
    if df is None:
        return 0.5
    df = df[df["patron"] == patron]
    if len(df) < 5:
        return 0.5
    return len(df[df["resultado"] > 0]) / len(df)


def perdidas_recientes_activo(activo, cantidad=2):
    df = cargar_historial()
    if df is None:
        return False
    df = df[df["activo"] == activo]
    if len(df) < cantidad:
        return False
    return all(df.tail(cantidad)["resultado"] < 0)


def ajustar_por_memoria(activo, patron, puntaje):
    wr_activo = winrate_activo(activo)
    wr_patron = winrate_patron(patron)
    if wr_activo >= 0.65:
        puntaje += 1
    if wr_activo <= 0.35:
        puntaje -= 2
    if wr_patron >= 0.65:
        puntaje += 1
    if wr_patron <= 0.35:
        puntaje -= 1
    if perdidas_recientes_activo(activo, 2):
        puntaje -= 2
    return puntaje
