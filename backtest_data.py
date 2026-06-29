import time
import csv
import os

import estado
from conexion import conectar
from config import CANDLE_TIME , CANDLE_NUMBER
from mercado import obtener_activos

CARPETA_DATA = "data_backtest"
VELAS_POR_ACTIVO = CANDLE_NUMBER
MIN_VELAS_VALIDAS = 200
ESPERA_ENTRE_DESCARGAS = 0.35


def limpiar_data_backtest():
    os.makedirs(CARPETA_DATA, exist_ok=True)

    eliminados = 0

    for archivo in os.listdir(CARPETA_DATA):
        if archivo.endswith(".csv"):
            os.remove(os.path.join(CARPETA_DATA, archivo))
            eliminados += 1

    print("data_backtest limpiada. Archivos eliminados:", eliminados, flush=True)


def activo_compatible(activo):
    if not activo:
        return False

    if "/" in activo:
        return False

    if "-op" in activo:
        return False

    return True


def guardar_velas_csv(tipo, activo, candles):
    os.makedirs(CARPETA_DATA, exist_ok=True)

    nombre_seguro = activo.replace("/", "_")
    ruta = os.path.join(CARPETA_DATA, f"{tipo}_{nombre_seguro}.csv")

    candles = sorted(candles, key=lambda x: x["from"])

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "tipo",
            "activo",
            "from",
            "open",
            "close",
            "max",
            "min",
            "volume"
        ])

        for c in candles:
            writer.writerow([
                tipo,
                activo,
                c.get("from"),
                c.get("open"),
                c.get("close"),
                c.get("max"),
                c.get("min"),
                c.get("volume", 0),
            ])

    print("Guardado:", ruta, "| velas:", len(candles), flush=True)


def descargar_velas_activo(tipo, activo):
    if not activo_compatible(activo):
        print("Activo incompatible:", tipo, activo, flush=True)
        return False

    try:
        print("Descargando:", tipo, activo, "| velas objetivo:", VELAS_POR_ACTIVO, flush=True)

        todas_las_velas = []
        timestamp_final = time.time()
        velas_restantes = VELAS_POR_ACTIVO
        max_por_bloque = 1000

        while velas_restantes > 0:
            cantidad = min(max_por_bloque, velas_restantes)

            print(
                "Bloque:",
                tipo,
                activo,
                "| solicitando:",
                cantidad,
                "| timestamp:",
                int(timestamp_final),
                flush=True
            )

            candles = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                cantidad,
                timestamp_final
            )

            if not candles:
                print("Bloque vacío:", tipo, activo, flush=True)
                break

            todas_las_velas.extend(candles)

            candles_ordenadas = sorted(candles, key=lambda x: x["from"])
            timestamp_final = candles_ordenadas[0]["from"] - 1

            velas_restantes -= len(candles)

            print(
                "Recibidas bloque:",
                len(candles),
                "| acumuladas:",
                len(todas_las_velas),
                flush=True
            )

            if len(candles) < cantidad:
                print("IQ devolvió menos velas de las solicitadas. Se detiene este activo.", flush=True)
                break

            time.sleep(ESPERA_ENTRE_DESCARGAS)

        # Eliminar duplicados por timestamp
        velas_unicas = {}
        for c in todas_las_velas:
            velas_unicas[c["from"]] = c

        candles_finales = list(velas_unicas.values())
        candles_finales = sorted(candles_finales, key=lambda x: x["from"])

        if not candles_finales or len(candles_finales) < MIN_VELAS_VALIDAS:
            print(
                "Sin suficientes velas:",
                tipo,
                activo,
                "| recibidas:",
                len(candles_finales) if candles_finales else 0,
                flush=True
            )
            return False

        guardar_velas_csv(tipo, activo, candles_finales)
        return True

    except Exception as e:
        print("Error descargando", tipo, activo, e, flush=True)
        return False

def main():
    print("1. Iniciando backtest_data", flush=True)

    conectar()
    print("2. Conectado", flush=True)

    limpiar_data_backtest()
    print("3. Carpeta lista", flush=True)

    print("4. Obteniendo activos con la lógica REAL del bot...", flush=True)
    activos = obtener_activos()
    print("5. Activos seleccionados:", len(activos), flush=True)

    descargados = 0

    for item in activos:
        ok = descargar_velas_activo(
            item["tipo"],
            item["activo"]
        )

        if ok:
            descargados += 1

        time.sleep(ESPERA_ENTRE_DESCARGAS)

    print("Descarga terminada.", flush=True)
    print("Archivos descargados:", descargados, flush=True)
    print("Carpeta:", CARPETA_DATA, flush=True)


if __name__ == "__main__":
    main()