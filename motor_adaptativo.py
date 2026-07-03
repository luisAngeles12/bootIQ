import json
import os

from config_fase4 import RUTA_BASE_CONOCIMIENTO
from normalizador import normalizar_texto


MIN_TOTAL_USABLE = 5
WINRATE_FUERTE = 58
WINRATE_DEBIL = 48


def cargar_base_conocimiento(ruta=RUTA_BASE_CONOCIMIENTO):
    if not os.path.exists(ruta):
        return {}

    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _txt(v):
    return normalizar_texto(v)


def _buscar_en_nivel(base, nivel, campo, valor):
    valor_norm = _txt(valor)
    clave = f"{campo}:{valor_norm}"

    datos_nivel = base.get("niveles", {}).get(nivel, {})

    for grupo in ["fuertes", "debiles", "neutras"]:
        data = datos_nivel.get(grupo, {}).get(clave)

        if data:
            return {
                "encontrado": True,
                "grupo": grupo,
                "clave": clave,
                "total": data.get("total", 0),
                "winrate": data.get("winrate", 50),
                "peso": data.get("peso", 1.0),
                "clasificacion": data.get("clasificacion", "NEUTRA"),
            }

    return {
        "encontrado": False,
        "grupo": "sin_datos",
        "clave": clave,
        "total": 0,
        "winrate": 50,
        "peso": 1.0,
        "clasificacion": "SIN_DATOS",
    }


def evaluar_factor_adaptativo(base, nivel, campo, valor):
    data = _buscar_en_nivel(base, nivel, campo, valor)

    if not data.get("encontrado"):
        return "SIN_DATOS", data

    total = int(data.get("total", 0) or 0)
    winrate = float(data.get("winrate", 50) or 50)

    if total < MIN_TOTAL_USABLE:
        return "MUESTRA_INSUFICIENTE", data

    if winrate >= WINRATE_FUERTE:
        return "FORTALEZA", data

    if winrate <= WINRATE_DEBIL:
        return "RIESGO", data

    return "NEUTRO", data


def ajustar_fortalezas_riesgos_por_aprendizaje(senal):
    """
    Ajusta fortalezas_base y riesgos_base usando base_conocimiento.json.

    No bloquea.
    No ejecuta.
    Solo reclasifica factores según estadística real.

    Regla importante:
    - Si el historial valida una fortaleza, se conserva.
    - Si el historial degrada una fortaleza, pasa a riesgo.
    - Si no hay datos o muestra suficiente, se conserva la fortaleza original.
    - Si el historial revierte un riesgo, pasa a fortaleza.
    - Si el historial valida un riesgo, se conserva.
    - Si no hay datos o muestra suficiente, se conserva el riesgo original.
    """

    base = cargar_base_conocimiento()

    fortalezas = [
        x.strip()
        for x in str(senal.get("fortalezas_base", "") or "").split("|")
        if x.strip()
    ]

    riesgos = [
        x.strip()
        for x in str(senal.get("riesgos_base", "") or "").split("|")
        if x.strip()
    ]

    nuevas_fortalezas = []
    nuevos_riesgos = []
    razones = []

    for f in fortalezas:
        decision, data = evaluar_factor_adaptativo(
            base,
            "nivel_13_fortalezas_base",
            "fortalezas_base",
            f
        )

        if decision == "FORTALEZA":
            nuevas_fortalezas.append(f)
            razones.append(
                f"Fortaleza validada por historial: {f} | winrate {data.get('winrate')}% | total {data.get('total')}"
            )

        elif decision == "RIESGO":
            nuevos_riesgos.append(f + "_DEGRADADA_HISTORICO")
            razones.append(
                f"Fortaleza degradada a riesgo: {f} | winrate {data.get('winrate')}% | total {data.get('total')}"
            )

        else:
            nuevas_fortalezas.append(f)
            razones.append(
                f"Fortaleza conservada sin evidencia suficiente: {f} | estado {decision}"
            )

    for r in riesgos:
        decision, data = evaluar_factor_adaptativo(
            base,
            "nivel_14_riesgos_base",
            "riesgos_base",
            r
        )

        if decision == "FORTALEZA":
            nuevas_fortalezas.append(r + "_REVERTIDO_HISTORICO")
            razones.append(
                f"Riesgo revertido por historial: {r} | winrate {data.get('winrate')}% | total {data.get('total')}"
            )

        elif decision == "RIESGO":
            nuevos_riesgos.append(r)
            razones.append(
                f"Riesgo validado por historial: {r} | winrate {data.get('winrate')}% | total {data.get('total')}"
            )

        else:
            nuevos_riesgos.append(r)
            razones.append(
                f"Riesgo conservado sin evidencia suficiente: {r} | estado {decision}"
            )

    senal["fortalezas_base"] = "|".join(dict.fromkeys(nuevas_fortalezas))
    senal["riesgos_base"] = "|".join(dict.fromkeys(nuevos_riesgos))
    senal["razon_motor_adaptativo"] = " | ".join(razones)

    return senal