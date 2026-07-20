import json
import os
from math import sqrt

from config_fase4 import RUTA_BASE_CONOCIMIENTO
from normalizador import (
    construir_clave_normalizada,
    normalizar_evidencia,
    normalizar_texto,
)


CONFIANZA_BASE = 50.0

# La base estadística debe orientar, no dominar.
AJUSTE_MAXIMO_CONFIANZA = 12.0
AJUSTE_MINIMO_CONFIANZA = -12.0

# Muestra mínima para que una coincidencia pueda afectar la confianza.
MIN_MUESTRA_NIVEL = 20

# Una coincidencia individual no puede producir un ajuste extremo.
AJUSTE_MAXIMO_POR_NIVEL = 4.0
AJUSTE_MINIMO_POR_NIVEL = -4.0

UMBRAL_FAVORABLE = 58.0
UMBRAL_DEBIL = 42.0

GRUPOS_VALIDOS = ("fuertes", "debiles", "neutras")


def _numero(valor, default=0.0):
    try:
        return float(valor if valor is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _entero(valor, default=0):
    try:
        return int(float(valor if valor is not None else default))
    except (TypeError, ValueError):
        return int(default)


def _limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def cargar_base_conocimiento(ruta=RUTA_BASE_CONOCIMIENTO):
    """
    Carga la base estadística.

    Devuelve None cuando el archivo no existe, no es JSON válido o no tiene
    una estructura utilizable. El motor no debe detener el bot por un problema
    de lectura.
    """

    if not ruta or not os.path.exists(ruta):
        return None

    try:
        with open(ruta, "r", encoding="utf-8-sig") as archivo:
            base = json.load(archivo)
    except (OSError, json.JSONDecodeError, TypeError):
        return None

    if not isinstance(base, dict):
        return None

    niveles = base.get("niveles")
    if not isinstance(niveles, dict):
        return None

    return base


def _campo_valido(signal, campo):
    valor = normalizar_texto(signal.get(campo))
    return valor not in {"sin_dato", "", "none", "null"}


def _nivel_usable(signal, campos):
    """
    Un nivel solo se evalúa cuando todos sus campos están presentes.
    """

    if not isinstance(campos, list) or not campos:
        return False

    return all(_campo_valido(signal, campo) for campo in campos)


def _confiabilidad_muestra(total):
    """
    Reduce el impacto de muestras pequeñas.

    Una coincidencia necesita al menos 20 operaciones para modificar
    la confianza. Su influencia aumenta progresivamente según la muestra.
    """

    total = _entero(total, 0)

    if total < MIN_MUESTRA_NIVEL:
        return 0.0, "INSUFICIENTE"

    if total < 40:
        return 0.35, "BAJA"

    if total < 80:
        return 0.60, "MEDIA"

    if total < 150:
        return 0.80, "MEDIA_ALTA"

    return 1.0, "ALTA"

def _ajuste_desde_combinacion(combinacion, grupo):
    """
    Convierte una coincidencia histórica en un ajuste aditivo moderado.

    Se usa el winrate y la muestra real. El peso almacenado se conserva como
    dato de auditoría, pero no se multiplica con otros pesos porque eso genera
    acumulación exponencial y doble conteo entre niveles solapados.
    """

    if not isinstance(combinacion, dict):
        return 0.0, {
            "usable": False,
            "motivo": "Combinación inválida.",
        }

    total = _entero(combinacion.get("total"), 0)
    winrate = _numero(combinacion.get("winrate"), 50.0)
    peso_original = _numero(combinacion.get("peso"), 1.0)

    factor_muestra, confiabilidad = _confiabilidad_muestra(total)

    if factor_muestra <= 0:
        return 0.0, {
            "usable": False,
            "total": total,
            "winrate": winrate,
            "peso_original": peso_original,
            "confiabilidad": confiabilidad,
            "motivo": (
                f"Muestra insuficiente: {total}; "
                f"mínimo requerido: {MIN_MUESTRA_NIVEL}."
            ),
        }

    # Distancia respecto a una referencia neutral del 50%.
    distancia = (winrate - 50.0) / 10.0

    # El grupo funciona como control de coherencia, no como segunda fuente
    # de impacto. Se corrige el signo si la etiqueta contradice el winrate.
    # El rendimiento observado determina el signo del ajuste.
    # El grupo se conserva únicamente para auditoría.
    #
    # No se fuerza una combinación "fuerte" a ser positiva ni una
    # combinación "débil" a ser negativa, porque las etiquetas pueden
    # estar desactualizadas o estadísticamente invertidas.
    distancia = _limitar(
        distancia,
        AJUSTE_MINIMO_POR_NIVEL,
        AJUSTE_MAXIMO_POR_NIVEL,
    )
    ajuste = distancia * factor_muestra
    ajuste = _limitar(
        ajuste,
        AJUSTE_MINIMO_POR_NIVEL,
        AJUSTE_MAXIMO_POR_NIVEL,
    )

    return round(ajuste, 2), {
        "usable": True,
        "total": total,
        "winrate": round(winrate, 2),
        "peso_original": peso_original,
        "confiabilidad": confiabilidad,
        "factor_muestra": factor_muestra,
    }


def _firma_campos(campos):
    """
    Identifica niveles que utilizan exactamente los mismos campos.
    """

    return tuple(sorted(str(campo) for campo in campos))


def _seleccionar_coincidencias(candidatas):
    """
    Evita contabilizar dos veces niveles con la misma firma de campos.

    Cuando dos niveles representan la misma evidencia, se conserva la
    coincidencia con mayor muestra. En empate, se conserva la de mayor ajuste
    absoluto.
    """

    seleccionadas = {}

    for candidata in candidatas:
        firma = candidata["firma_campos"]
        actual = seleccionadas.get(firma)

        if actual is None:
            seleccionadas[firma] = candidata
            continue

        total_nuevo = candidata.get("total", 0)
        total_actual = actual.get("total", 0)

        if total_nuevo > total_actual:
            seleccionadas[firma] = candidata
            continue

        if (
            total_nuevo == total_actual
            and abs(candidata.get("ajuste", 0))
            > abs(actual.get("ajuste", 0))
        ):
            seleccionadas[firma] = candidata

    return list(seleccionadas.values())


def _combinar_ajustes(coincidencias):
    """
    Combina evidencia estadística con rendimiento decreciente.

    La primera coincidencia aporta todo su ajuste. Las siguientes aportan menos
    para impedir que niveles correlacionados acumulen el mismo dato varias veces.
    """

    if not coincidencias:
        return 0.0, []

    ordenadas = sorted(
        coincidencias,
        key=lambda item: (
            item.get("total", 0),
            abs(item.get("ajuste", 0)),
        ),
        reverse=True,
    )

    factores = []
    suma = 0.0

    for indice, coincidencia in enumerate(ordenadas):
        # 1.00, 0.71, 0.58, 0.50...
        factor = 1.0 / sqrt(indice + 1)
        aporte = coincidencia.get("ajuste", 0.0) * factor
        suma += aporte

        factores.append({
            "nivel": coincidencia.get("nivel", ""),
            "ajuste_original": coincidencia.get("ajuste", 0.0),
            "factor_correlacion": round(factor, 3),
            "aporte_final": round(aporte, 2),
        })

    suma = _limitar(
        suma,
        AJUSTE_MINIMO_CONFIANZA,
        AJUSTE_MAXIMO_CONFIANZA,
    )

    return round(suma, 2), factores


def _clasificar_confianza(confianza):
    if confianza >= UMBRAL_FAVORABLE:
        return "FAVORABLE"

    if confianza <= UMBRAL_DEBIL:
        return "DEBIL"

    return "NEUTRA"


def evaluar_senal(signal, base_conocimiento=None):
    """
    Calcula la confianza estadística base de BootIQ.

    Responsabilidad única:
    - consultar la base de conocimiento;
    - localizar coincidencias utilizables;
    - producir un ajuste estadístico moderado.

    No decide si operar.
    No bloquea.
    No interpreta protocolos.
    No vuelve a evaluar Price Action, mercado o riesgo por reglas manuales.
    """

    if not isinstance(signal, dict):
        signal = {}

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

    if not isinstance(base_conocimiento, dict):
        return {
            "confianza": CONFIANZA_BASE,
            "decision": "SIN_BASE_CONOCIMIENTO",
            "peso_final": 1.0,
            "ajuste_estadistico": 0.0,
            "motivos": ["No se encontró una base de conocimiento válida."],
            "coincidencias": [],
            "coincidencias_descartadas": [],
            "aportes_estadisticos": [],
            "niveles_evaluados": 0,
            "niveles_descartados": 0,
            "cantidad_coincidencias": 0,
            "campos_setup_disponibles": campos_setup_disponibles,
        }

    niveles = base_conocimiento.get("niveles", {})

    if not isinstance(niveles, dict):
        niveles = {}

    motivos = []
    candidatas = []
    descartadas = []

    niveles_evaluados = 0
    niveles_descartados = 0

    for nombre_nivel, datos_nivel in niveles.items():
        if not isinstance(datos_nivel, dict):
            niveles_descartados += 1
            continue

        campos = datos_nivel.get("campos", [])

        if not _nivel_usable(signal, campos):
            niveles_descartados += 1
            continue

        niveles_evaluados += 1

        try:
            clave = construir_clave_normalizada(signal, campos)
        except (TypeError, ValueError, KeyError):
            niveles_descartados += 1
            continue

        coincidencia_encontrada = False

        for grupo in GRUPOS_VALIDOS:
            grupo_datos = datos_nivel.get(grupo, {})

            if not isinstance(grupo_datos, dict):
                continue

            combinacion = grupo_datos.get(clave)

            if not combinacion:
                continue

            coincidencia_encontrada = True

            ajuste, detalle = _ajuste_desde_combinacion(
                combinacion=combinacion,
                grupo=grupo,
            )

            registro = {
                "nivel": nombre_nivel,
                "grupo": grupo,
                "clave": clave,
                "campos": list(campos),
                "firma_campos": _firma_campos(campos),
                "winrate": detalle.get("winrate"),
                "total": detalle.get("total", 0),
                "peso": detalle.get("peso_original", 1.0),
                "ajuste": ajuste,
                "confiabilidad_muestra": detalle.get(
                    "confiabilidad",
                    "INSUFICIENTE",
                ),
            }

            if detalle.get("usable", False):
                candidatas.append(registro)
            else:
                registro["motivo_descarte"] = detalle.get(
                    "motivo",
                    "Coincidencia no utilizable.",
                )
                descartadas.append(registro)

            # Una clave no debe aparecer simultáneamente en varios grupos.
            break

        if not coincidencia_encontrada:
            continue

    coincidencias = _seleccionar_coincidencias(candidatas)
    ajuste_estadistico, aportes = _combinar_ajustes(coincidencias)

    confianza = round(
        _limitar(
            CONFIANZA_BASE + ajuste_estadistico,
            0.0,
            100.0,
        ),
        2,
    )

    decision = _clasificar_confianza(confianza)

    for coincidencia in coincidencias:
        motivos.append(
            f"{coincidencia['nivel']}: {coincidencia['grupo'].upper()}, "
            f"winrate {coincidencia['winrate']}% en "
            f"{coincidencia['total']} operaciones, "
            f"ajuste {coincidencia['ajuste']:+.2f}."
        )

    if not coincidencias:
        motivos.append(
            "No hay coincidencias estadísticas con muestra suficiente."
        )

    # Compatibilidad temporal con consumidores antiguos.
    # Representa la confianza relativa frente a la base 50, no una
    # multiplicación de pesos entre niveles.
    peso_final = round(confianza / CONFIANZA_BASE, 3)
    peso_final = _limitar(peso_final, 0.0, 2.0)

    return {
        "confianza": confianza,
        "decision": decision if coincidencias else "SIN_EVIDENCIA_ESTADISTICA",
        "peso_final": peso_final,
        "ajuste_estadistico": ajuste_estadistico,
        "motivos": motivos,
        "coincidencias": coincidencias,
        "coincidencias_descartadas": descartadas,
        "aportes_estadisticos": aportes,
        "niveles_evaluados": niveles_evaluados,
        "niveles_descartados": niveles_descartados,
        "cantidad_coincidencias": len(coincidencias),
        "campos_setup_disponibles": campos_setup_disponibles,
    }


def probar_motor(base_conocimiento=None):
    """
    Prueba rápida del contrato público.
    """

    ejemplos = [
        {
            "patron": "liquidity sweep alcista",
            "direccion": "call",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
            "calidad_mercado": "NORMAL",
            "activo": "BIDU-OTC",
        },
        {
            "patron": "liquidity sweep bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
            "calidad_mercado": "NORMAL",
            "activo": "COCOA-OTC",
        },
        {
            "patron": "CHOCH bajista",
            "direccion": "put",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
            "pa_direccion": "PUT",
            "calidad_mercado": "NORMAL",
            "activo": "XPTUSD-OTC",
        },
    ]

    resultados = []

    for signal in ejemplos:
        resultado = evaluar_senal(
            signal,
            base_conocimiento=base_conocimiento,
        )

        assert 0.0 <= resultado["confianza"] <= 100.0
        assert "peso_final" in resultado
        assert "coincidencias" in resultado

        resultados.append(resultado)

    return resultados


if __name__ == "__main__":
    for indice, resultado in enumerate(probar_motor(), start=1):
        print(f"\n--- EJEMPLO {indice} ---")
        print("Confianza:", resultado["confianza"])
        print("Decisión estadística:", resultado["decision"])
        print("Ajuste:", resultado["ajuste_estadistico"])
        print("Coincidencias:", resultado["cantidad_coincidencias"])

        for motivo in resultado["motivos"]:
            print("-", motivo)