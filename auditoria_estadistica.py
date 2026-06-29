import csv
import json
from collections import defaultdict

import os
from config_fase4 import RUTA_BACKTEST_RESULTADOS, RUTA_AUDITORIA
from normalizador import construir_clave_normalizada, normalizar_texto

ARCHIVO_BACKTEST = RUTA_BACKTEST_RESULTADOS
SALIDA_JSON = RUTA_AUDITORIA

MIN_MUESTRA_BAJA = 5
MIN_MUESTRA_MEDIA = 10
MIN_MUESTRA_ALTA = 20

WINRATE_FUERTE = 65
WINRATE_DEBIL = 45


def normalizar(valor):
    return normalizar_texto(valor)


def cargar_resultados(ruta=ARCHIVO_BACKTEST):
    with open(ruta, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def calcular_estadistica(filas):
    total = len(filas)
    wins = sum(1 for r in filas if normalizar(r.get("resultado")).upper() == "WIN")
    losses = total - wins
    winrate = round((wins / total) * 100, 2) if total else 0

    if total >= MIN_MUESTRA_ALTA:
        confianza_muestra = "ALTA"
    elif total >= MIN_MUESTRA_MEDIA:
        confianza_muestra = "MEDIA"
    elif total >= MIN_MUESTRA_BAJA:
        confianza_muestra = "BAJA"
    else:
        confianza_muestra = "INSUFICIENTE"

    # En fase de pruebas, permitimos clasificar desde MIN_MUESTRA_BAJA.
    # Si esperamos MIN_MUESTRA_MEDIA, muchas estrategias útiles desaparecen
    # de la base de conocimiento por falta de muestra.
    if total < MIN_MUESTRA_BAJA:
        clasificacion = "SIN_DECISION"
    elif winrate >= WINRATE_FUERTE:
        clasificacion = "FUERTE"
    elif winrate <= WINRATE_DEBIL:
        clasificacion = "DEBIL"
    else:
        clasificacion = "NEUTRA"

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "confianza_muestra": confianza_muestra,
        "clasificacion": clasificacion
    }

def agrupar_por_campos(resultados, campos):
    grupos = defaultdict(list)

    for r in resultados:
        clave = construir_clave_normalizada(r, campos)
        grupos[clave].append(r)

    estadisticas = {
        clave: calcular_estadistica(filas)
        for clave, filas in grupos.items()
    }

    return dict(
        sorted(
            estadisticas.items(),
            key=lambda x: (
                x[1]["clasificacion"] == "FUERTE",
                x[1]["confianza_muestra"] == "ALTA",
                x[1]["confianza_muestra"] == "MEDIA",
                x[1]["winrate"],
                x[1]["total"]
            ),
            reverse=True
        )
    )


def filtrar_por_clasificacion(bloque, clasificacion):
    return {
        clave: datos
        for clave, datos in bloque.items()
        if datos["clasificacion"] == clasificacion
    }


def generar_piramide_estadistica(resultados):
    niveles = {
        "nivel_1_estrategia": ["patron"],

        "nivel_2_estrategia_direccion": [
            "patron",
            "direccion"
        ],

        "nivel_3_estrategia_mercado": [
            "patron",
            "direccion",
            "tipo_mercado"
        ],

        "nivel_4_estrategia_mercado_tendencia": [
            "patron",
            "direccion",
            "tipo_mercado",
            "estado_tendencia"
        ],

        "nivel_5_estrategia_mercado_tendencia_pa": [
            "patron",
            "direccion",
            "tipo_mercado",
            "estado_tendencia",
            "pa_tipo",
            "pa_direccion"
        ],

        "nivel_6_estrategia_mercado_tendencia_pa_calidad": [
            "patron",
            "direccion",
            "tipo_mercado",
            "estado_tendencia",
            "pa_tipo",
            "pa_direccion",
            "calidad_mercado"
        ],

        "nivel_7_combinacion_completa": [
            "patron",
            "direccion",
            "activo",
            "tipo_mercado",
            "estado_tendencia",
            "pa_tipo",
            "pa_direccion",
            "calidad_mercado"
        ],
        "nivel_8_tipo_setup": [
            "tipo_setup"
        ],

        "nivel_9_setup_calidad": [
            "tipo_setup",
            "calidad_setup"
        ],

        "nivel_10_setup_modo": [
            "tipo_setup",
            "calidad_setup",
            "modo_entrada_setup"
        ],

        "nivel_11_setup_mercado": [
            "tipo_setup",
            "calidad_setup",
            "modo_entrada_setup",
            "tipo_mercado",
            "estado_tendencia"
        ],

        "nivel_12_setup_pa": [
            "tipo_setup",
            "calidad_setup",
            "modo_entrada_setup",
            "tipo_mercado",
            "estado_tendencia",
            "pa_tipo",
            "pa_direccion"
        ],
    }

    piramide = {}

    for nombre_nivel, campos in niveles.items():
        bloque = agrupar_por_campos(resultados, campos)

        piramide[nombre_nivel] = {
            "campos": campos,
            "total_combinaciones": len(bloque),
            "combinaciones": bloque,
            "fuertes": filtrar_por_clasificacion(bloque, "FUERTE"),
            "debiles": filtrar_por_clasificacion(bloque, "DEBIL"),
            "neutras": filtrar_por_clasificacion(bloque, "NEUTRA"),
            "sin_decision": filtrar_por_clasificacion(bloque, "SIN_DECISION")
        }

    return piramide


def generar_resumen_ejecutivo(piramide):
    resumen = {}

    for nivel, datos in piramide.items():
        resumen[nivel] = {
            "total_combinaciones": datos["total_combinaciones"],
            "fuertes": len(datos["fuertes"]),
            "debiles": len(datos["debiles"]),
            "neutras": len(datos["neutras"]),
            "sin_decision": len(datos["sin_decision"])
        }

    return resumen


def generar_auditoria(resultados):
    piramide = generar_piramide_estadistica(resultados)

    auditoria = {
        "resumen_general": calcular_estadistica(resultados),
        "resumen_piramide": generar_resumen_ejecutivo(piramide),
        "piramide_estadistica": piramide
    }

    return auditoria


def guardar_auditoria(auditoria, ruta=SALIDA_JSON):
    carpeta = os.path.dirname(ruta)

    if carpeta:
        os.makedirs(carpeta, exist_ok=True)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(auditoria, f, indent=4, ensure_ascii=False)

def imprimir_mejores_y_peores(auditoria, nivel, limite=10):
    datos = auditoria["piramide_estadistica"].get(nivel, {})

    print(f"\n===== {nivel.upper()} =====")

    print("\n--- FUERTES ---")
    for clave, stats in list(datos.get("fuertes", {}).items())[:limite]:
        print(
            clave,
            "| total:", stats["total"],
            "| winrate:", str(stats["winrate"]) + "%",
            "| muestra:", stats["confianza_muestra"]
        )

    print("\n--- DEBILES ---")
    for clave, stats in list(datos.get("debiles", {}).items())[:limite]:
        print(
            clave,
            "| total:", stats["total"],
            "| winrate:", str(stats["winrate"]) + "%",
            "| muestra:", stats["confianza_muestra"]
        )


def main():
    resultados = cargar_resultados()

    if not resultados:
        print("No hay resultados para auditar.")
        return

    auditoria = generar_auditoria(resultados)
    guardar_auditoria(auditoria)

    resumen = auditoria["resumen_general"]

    print("\n===== AUDITORÍA ESTADÍSTICA BOOTIQ - FASE 4.1 =====")
    print("Total operaciones:", resumen["total"])
    print("Wins:", resumen["wins"])
    print("Losses:", resumen["losses"])
    print("Winrate general:", str(resumen["winrate"]) + "%")
    print("Confianza muestra:", resumen["confianza_muestra"])
    print("Clasificación general:", resumen["clasificacion"])
    print("Archivo generado:", SALIDA_JSON)

    print("\n===== RESUMEN PIRÁMIDE =====")
    for nivel, datos in auditoria["resumen_piramide"].items():
        print(
            nivel,
            "| combinaciones:", datos["total_combinaciones"],
            "| fuertes:", datos["fuertes"],
            "| débiles:", datos["debiles"],
            "| neutras:", datos["neutras"],
            "| sin decisión:", datos["sin_decision"]
        )

    imprimir_mejores_y_peores(auditoria, "nivel_1_estrategia")
    imprimir_mejores_y_peores(auditoria, "nivel_3_estrategia_mercado")
    imprimir_mejores_y_peores(auditoria, "nivel_5_estrategia_mercado_tendencia_pa")
    imprimir_mejores_y_peores(auditoria, "nivel_7_combinacion_completa")


if __name__ == "__main__":
    main()