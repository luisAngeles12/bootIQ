import time
import csv
import os

import estado
from conexion import conectar
from config import CANDLE_TIME

from mercado import obtener_activos
CARPETA_DATA = "data_backtest"
VELAS_POR_ACTIVO = 1000
TIPOS_BACKTEST = ["binary", "turbo"]


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
                c.get("volume", 0)
            ])

    print("Guardado:", ruta, "| velas:", len(candles))


def descargar_velas_activo(tipo, activo):
    try:
        print("Descargando:", tipo, activo)

        candles = estado.Iq.get_candles(
            activo,
            CANDLE_TIME,
            VELAS_POR_ACTIVO,
            time.time()
        )

        if not candles or len(candles) < 200:
            print("Sin suficientes velas:", tipo, activo)
            return False

        candles = sorted(candles, key=lambda x: x["from"])

        guardar_velas_csv(tipo, activo, candles)
        return True

    except Exception as e:
        print("Error descargando", tipo, activo, e)
        return False


def obtener_activos_abiertos():
    print("Solicitando mercados abiertos...")
    abiertos = estado.Iq.get_all_open_time()
    print("Mercados abiertos recibidos")
    activos = []

    for tipo in TIPOS_BACKTEST:
        mercados = abiertos.get(tipo, {})

        for activo, info in mercados.items():
            if not info.get("open", False):
                continue

            if not activo_compatible(activo):
                continue

            activos.append({
                "tipo": tipo,
                "activo": activo
            })

    activos_unicos = []
    vistos = set()

    for item in activos:
        clave = item["tipo"] + "_" + item["activo"]

        if clave in vistos:
            continue

        vistos.add(clave)
        activos_unicos.append(item)

    return activos_unicos


def main():
    conectar()

    print("Actualizando activos/OPCODE...")
    estado.Iq.update_ACTIVES_OPCODE()
    print("Activos/OPCODE actualizados")

    print("Obteniendo TOP activos con lógica real del bot...")
    activos = obtener_activos()

    print("Activos seleccionados por el bot:", len(activos))

    descargados = 0

    for item in activos:
        ok = descargar_velas_activo(
            item["tipo"],
            item["activo"]
        )

        if ok:
            descargados += 1

        time.sleep(0.35)

    print("Descarga terminada.")
    print("Archivos descargados:", descargados)

if __name__ == "__main__":
    main()