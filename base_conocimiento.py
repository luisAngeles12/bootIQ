import json
import os
from datetime import datetime

from config_fase4 import RUTA_AUDITORIA, RUTA_BASE_CONOCIMIENTO


PESO_FUERTE = 1.18
PESO_NEUTRO = 1.00
PESO_DEBIL = 0.78

MIN_MUESTRA_USABLE = 5

def cargar_json(ruta):
    if not os.path.exists(ruta):
        print(f"No existe el archivo: {ruta}")
        return None

    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_json(datos, ruta):
    carpeta = os.path.dirname(ruta)

    if carpeta:
        os.makedirs(carpeta, exist_ok=True)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)


def calcular_peso(clasificacion, winrate):
    if clasificacion == "FUERTE":
        exceso = max(0, winrate - 50)
        return round(1 + (exceso / 100), 3)

    if clasificacion == "DEBIL":
        deficit = max(0, 50 - winrate)
        return round(1 - (deficit / 100), 3)

    return PESO_NEUTRO


def convertir_combinacion(clave, stats, nivel, campos):
    return {
        "clave": clave,
        "nivel": nivel,
        "campos": campos,
        "total": stats["total"],
        "wins": stats["wins"],
        "losses": stats["losses"],
        "winrate": stats["winrate"],
        "confianza_muestra": stats["confianza_muestra"],
        "clasificacion": stats["clasificacion"],
        "peso": calcular_peso(stats["clasificacion"], stats["winrate"]),
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def extraer_conocimiento_util(auditoria):
    piramide = auditoria.get("piramide_estadistica", {})

    conocimiento = {
        "version": "4.1",
        "descripcion": "Base de conocimiento estadística generada desde auditoría de backtest.",
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "min_muestra_usable": MIN_MUESTRA_USABLE,
        "niveles": {}
    }

    for nombre_nivel, datos_nivel in piramide.items():
        campos = datos_nivel.get("campos", [])

        conocimiento["niveles"][nombre_nivel] = {
            "campos": campos,
            "fuertes": {},
            "debiles": {},
            "neutras": {}
        }

        for grupo in ["fuertes", "debiles", "neutras"]:
            combinaciones = datos_nivel.get(grupo, {})

            for clave, stats in combinaciones.items():
                if stats["total"] < MIN_MUESTRA_USABLE:
                    continue

                conocimiento["niveles"][nombre_nivel][grupo][clave] = convertir_combinacion(
                    clave=clave,
                    stats=stats,
                    nivel=nombre_nivel,
                    campos=campos
                )

    return conocimiento


def imprimir_resumen(conocimiento):
    print("\n===== BASE DE CONOCIMIENTO BOOTIQ =====")
    print("Versión:", conocimiento["version"])
    print("Última actualización:", conocimiento["ultima_actualizacion"])

    for nivel, datos in conocimiento["niveles"].items():
        print(
            nivel,
            "| fuertes:", len(datos["fuertes"]),
            "| débiles:", len(datos["debiles"]),
            "| neutras:", len(datos["neutras"])
        )


def main():
    auditoria = cargar_json(RUTA_AUDITORIA)

    if auditoria is None:
        print("Primero ejecuta auditoria_estadistica.py")
        return

    conocimiento = extraer_conocimiento_util(auditoria)
    guardar_json(conocimiento, RUTA_BASE_CONOCIMIENTO)

    imprimir_resumen(conocimiento)
    print("Archivo generado:", RUTA_BASE_CONOCIMIENTO)


if __name__ == "__main__":
    main()