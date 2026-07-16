import json
import os

from config_fase4 import RUTA_BASE_CONOCIMIENTO
from normalizador import construir_clave_normalizada, normalizar_evidencia, normalizar_texto

PESO_MINIMO = 0.50
PESO_MAXIMO = 1.35

CONFIANZA_BASE = 50.0

UMBRAL_FAVORABLE = 65.0
UMBRAL_DEBIL = 45.0


def cargar_base_conocimiento(ruta=RUTA_BASE_CONOCIMIENTO):
    if not os.path.exists(ruta):
        return None

    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def limitar_peso(peso):
    return max(PESO_MINIMO, min(PESO_MAXIMO, peso))


def aplicar_pesos(pesos):
    peso_final = 1.0

    for peso in pesos:
        peso_final *= peso

    return limitar_peso(round(peso_final, 3))


def calcular_confianza_desde_peso(peso_final):
    confianza = CONFIANZA_BASE * peso_final
    return round(max(0, min(100, confianza)), 2)


def _campo_valido(signal, campo):
    valor = normalizar_texto(signal.get(campo))
    return valor not in ["sin_dato", "", "none", "null"]


def _nivel_usable(signal, campos):
    """
    Evita usar niveles estadísticos cuando la señal aún no tiene
    todos los campos necesarios.

    Ejemplo:
    Fase 4 no debe usar motivo_ejecucion si todavía no existe.
    """

    if not campos:
        return False

    for campo in campos:
        if not _campo_valido(signal, campo):
            return False

    return True


def evaluar_senal(signal, base_conocimiento=None):
    signal = normalizar_evidencia(signal)
    campos_setup_disponibles = {
        campo: signal.get(campo)
        for campo in [
            "tipo_setup",
            "calidad_setup",
            "modo_entrada_setup",
            "balance_setup",
            "familia_setup",
            "subtipo_setup",
            "nivel_setup",
            "estado_setup",
            "confianza_setup",
        ]
        if _campo_valido(signal, campo)
    }
    if base_conocimiento is None:
        base_conocimiento = cargar_base_conocimiento()

    if base_conocimiento is None:
        return {
            "confianza": CONFIANZA_BASE,
            "decision": "SIN_BASE_CONOCIMIENTO",
            "peso_final": 1.0,
            "motivos": ["No se encontró base_conocimiento.json"],
            "coincidencias": [],
            "niveles_evaluados": 0,
            "niveles_descartados": 0,
            "cantidad_coincidencias": 0,
            "campos_setup_disponibles": campos_setup_disponibles,
        }

    motivos = []
    pesos = []
    coincidencias = []
    
    niveles_evaluados = 0
    niveles_descartados = 0

    niveles = base_conocimiento.get("niveles", {})

    for nombre_nivel, datos_nivel in niveles.items():
        campos = datos_nivel.get("campos", [])

        if not _nivel_usable(signal, campos):
            niveles_descartados += 1
            continue
        niveles_evaluados += 1
        clave = construir_clave_normalizada(signal, campos)

        for grupo in ["fuertes", "debiles", "neutras"]:
            combinacion = datos_nivel.get(grupo, {}).get(clave)

            if not combinacion:
                continue

            peso = float(combinacion.get("peso", 1.0))
            pesos.append(peso)

            coincidencias.append({
                "nivel": nombre_nivel,
                "grupo": grupo,
                "clave": clave,
                "winrate": combinacion.get("winrate"),
                "total": combinacion.get("total"),
                "peso": peso
            })

            motivos.append(
                f"{nombre_nivel} detectado como {grupo.upper()} "
                f"con winrate {combinacion.get('winrate')}% "
                f"en {combinacion.get('total')} operaciones. Peso aplicado: {peso}"
            )

    if not pesos:
        return {
            "confianza": CONFIANZA_BASE,
            "decision": "SIN_EVIDENCIA_ESTADISTICA",
            "peso_final": 1.0,
            "motivos": [
                "No hay coincidencias suficientes en la base de conocimiento."
            ],
            "coincidencias": [],
            "niveles_evaluados": niveles_evaluados,
            "niveles_descartados": niveles_descartados,
            "cantidad_coincidencias": 0,
            "campos_setup_disponibles": campos_setup_disponibles,
     }

    peso_final = aplicar_pesos(pesos)
    confianza = calcular_confianza_desde_peso(peso_final)

    if confianza >= UMBRAL_FAVORABLE:
        decision = "FAVORABLE"
    elif confianza <= UMBRAL_DEBIL:
        decision = "DEBIL"
    else:
        decision = "NEUTRA"

    return {
        "confianza": confianza,
        "decision": decision,
        "peso_final": peso_final,
        "motivos": motivos,
        "coincidencias": coincidencias,
        "niveles_evaluados": niveles_evaluados,
        "niveles_descartados": niveles_descartados,
        "cantidad_coincidencias": len(coincidencias),
        "campos_setup_disponibles": campos_setup_disponibles,
    }


def probar_motor():
    ejemplos = [
        {
            "patron": "liquidity sweep alcista",
            "direccion": "call",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
            "calidad_mercado": "NORMAL",
            "activo": "BIDU-OTC"
        },
        {
            "patron": "liquidity sweep bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
            "calidad_mercado": "NORMAL",
            "activo": "COCOA-OTC"
        },
        {
            "patron": "CHOCH bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
            "pa_direccion": "PUT",
            "calidad_mercado": "NORMAL",
            "activo": "XPTUSD-OTC"
        }
    ]

    print("\n===== PRUEBA MOTOR DE CONFIANZA BOOTIQ =====")

    for i, signal in enumerate(ejemplos, start=1):
        resultado = evaluar_senal(signal)

        print(f"\n--- EJEMPLO {i} ---")
        print("Patrón:", signal["patron"])
        print("Dirección:", signal["direccion"])
        print("Mercado:", signal["tipo_mercado"])
        print("Confianza:", str(resultado["confianza"]) + "%")
        print("Decisión:", resultado["decision"])
        print("Peso final:", resultado["peso_final"])

        print("Motivos:")
        for motivo in resultado["motivos"]:
            print("-", motivo)


if __name__ == "__main__":
    probar_motor()