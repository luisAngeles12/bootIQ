"""Auditoría descriptiva por estrategia y régimen; no autoriza operaciones.

Las señales canceladas solo tienen resultado hipotético y jamás se
contabilizan como operaciones efectivamente ejecutadas.
"""

from collections import defaultdict
from math import sqrt


def _texto(valor):
    return str(valor or "").strip().upper()


def _resultado(valor):
    resultado = _texto(valor)
    return resultado if resultado in {"WIN", "LOSS"} else None


def _rango_rsi(valor):
    """Segmentos descriptivos fijos, sin emplearlos como umbrales de entrada."""
    try:
        rsi = float(valor)
    except (TypeError, ValueError):
        return "RSI_SIN_DATOS"
    if not 0 <= rsi <= 100:
        return "RSI_SIN_DATOS"
    if rsi < 30:
        return "RSI_MENOR_30"
    if rsi < 45:
        return "RSI_30_45"
    if rsi <= 55:
        return "RSI_45_55"
    if rsi <= 70:
        return "RSI_55_70"
    return "RSI_MAYOR_70"


def _limite_inferior_wilson(wins, total, z=1.96):
    """Cota conservadora descriptiva de WR; no autoriza operaciones."""
    if not total:
        return 0.0
    p = wins / total
    z2 = z * z
    return round(100 * ((p + z2 / (2 * total) - z * sqrt(
        (p * (1 - p) + z2 / (4 * total)) / total
    )) / (1 + z2 / total)), 2)


def _clase_senal(fila):
    estado = _texto(fila.get("estado_operacion"))
    decision = _texto(fila.get("cerebro_unico_decision"))
    motivo = _texto(fila.get("motivo_ejecucion"))
    if estado == "OPERADA_DIRECTA":
        return "DIRECTA_SIMULADA"
    if estado == "OPERADA_PROTOCOLO":
        return "PROTOCOLO_SIMULADO"
    if estado.startswith("CANCELADA_") or decision == "NO_OPERAR" or motivo.startswith("CANCELADA_"):
        return "CANCELADA_HIPOTETICA"
    return "OTRA_SENAL_EVALUADA"


def _resultado_contextual(fila, clase):
    """Usa resultado ejecutado en las entradas, hipotético en descartes.

    Es especialmente importante para protocolos: su entrada puede ocurrir
    varias velas después de la señal y diferir de resultado_hipotetico.
    Si falta el campo correspondiente, no inventamos ni sustituimos el dato.
    """
    campo = (
        "resultado"
        if clase in {"DIRECTA_SIMULADA", "PROTOCOLO_SIMULADO"}
        else "resultado_hipotetico"
    )
    return _resultado(fila.get(campo)), campo


def auditar_integridad_contextual(filas):
    """Cuenta cobertura y exclusiones antes de publicar cualquier WR por contexto.

    No inventa etiquetas ausentes ni elimina registros duplicados: un mismo
    instante puede producir señales diferentes. Solo audita los datos recibidos.
    """
    total = 0
    validos = 0
    sin_resultado = 0
    sin_estrategia = 0
    sin_mercado = 0
    sin_tendencia = 0
    sin_precio = 0
    por_clase = defaultdict(int)
    for fila in filas:
        total += 1
        if not isinstance(fila, dict):
            sin_resultado += 1
            continue
        clase = _clase_senal(fila)
        por_clase[clase] += 1
        resultado, _ = _resultado_contextual(fila, clase)
        if resultado is None:
            sin_resultado += 1
            continue
        validos += 1
        if not _texto(fila.get("patron")):
            sin_estrategia += 1
        if not _texto(fila.get("tipo_mercado")):
            sin_mercado += 1
        if not _texto(fila.get("estado_tendencia")):
            sin_tendencia += 1
        if not _texto(fila.get("accion_precio")):
            sin_precio += 1
    return {
        "total": total,
        "con_resultado_valido": validos,
        "sin_resultado_valido": sin_resultado,
        "sin_estrategia": sin_estrategia,
        "sin_mercado": sin_mercado,
        "sin_tendencia": sin_tendencia,
        "sin_accion_precio": sin_precio,
        "por_clase": dict(sorted(por_clase.items())),
    }


def agrupar_factores_estrategia(filas, minimo=10):
    """Cruza estrategia con mercado, PA y RSI, sin optimizar reglas in-sample.

    Cada dimensión se estudia por separado para evitar presentar combinaciones
    de 1-2 ejemplos como si fueran una ventaja estadística demostrada.
    Las operaciones no ejecutadas siempre conservan su clase hipotética.
    """
    factores = (
        ("MERCADO", "tipo_mercado"),
        ("CALIDAD_MERCADO", "calidad_mercado"),
        ("TENDENCIA", "estado_tendencia"),
        ("ACCION_PRECIO", "accion_precio"),
        ("RSI", None),
    )
    grupos = defaultdict(lambda: {"wins": 0, "losses": 0})
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        clase = _clase_senal(fila)
        resultado, _ = _resultado_contextual(fila, clase)
        if resultado is None:
            continue
        base = (
            clase,
            _texto(fila.get("patron")) or "SIN_PATRON",
            _texto(fila.get("direccion")) or "SIN_DIRECCION",
        )
        for dimension, columna in factores:
            valor = (_texto(fila.get(columna)) or "SIN_DATOS") if columna else _rango_rsi(fila.get("rsi"))
            grupos[base + (dimension, valor)]["wins" if resultado == "WIN" else "losses"] += 1

    salida = []
    for (clase, patron, direccion, dimension, valor), conteo in grupos.items():
        total = conteo["wins"] + conteo["losses"]
        if total < minimo:
            continue
        salida.append({
            "clase": clase, "patron": patron, "direccion": direccion,
            "dimension": dimension, "valor": valor, "total": total,
            "wins": conteo["wins"], "losses": conteo["losses"],
            "wr_contextual": round(100 * conteo["wins"] / total, 2),
            "fuente_resultado": (
                "resultado"
                if clase in {"DIRECTA_SIMULADA", "PROTOCOLO_SIMULADO"}
                else "resultado_hipotetico"
            ),
            "limite_inferior_wilson": _limite_inferior_wilson(conteo["wins"], total),
        })
    return sorted(salida, key=lambda x: (-x["total"], x["clase"], x["patron"], x["dimension"]))


def agrupar_senales_por_contexto(filas, minimo=1):
    """Agrupa únicamente registros evaluables y separa ejecución/sombra.

    No convierte resultados hipotéticos en operaciones reales. El umbral
    ``minimo`` solo afecta la presentación, nunca una decisión del bot.
    """
    grupos = defaultdict(lambda: {"wins": 0, "losses": 0})

    for fila in filas:
        if not isinstance(fila, dict):
            continue

        clase = _clase_senal(fila)

        resultado, _ = _resultado_contextual(fila, clase)
        if resultado is None:
            continue

        clave = (
            clase,
            _texto(fila.get("patron")) or "SIN_PATRON",
            _texto(fila.get("direccion")) or "SIN_DIRECCION",
            _texto(fila.get("tipo_mercado")) or "SIN_MERCADO",
            _texto(fila.get("estado_tendencia")) or "SIN_TENDENCIA",
        )
        grupos[clave]["wins" if resultado == "WIN" else "losses"] += 1

    reporte = []
    for clave, conteo in grupos.items():
        total = conteo["wins"] + conteo["losses"]
        if total < minimo:
            continue
        reporte.append({
            "clase": clave[0],
            "patron": clave[1],
            "direccion": clave[2],
            "mercado": clave[3],
            "tendencia": clave[4],
            "total": total,
            "wins": conteo["wins"],
            "losses": conteo["losses"],
            "wr_contextual": round(100 * conteo["wins"] / total, 2),
            "fuente_resultado": (
                "resultado"
                if clave[0] in {"DIRECTA_SIMULADA", "PROTOCOLO_SIMULADO"}
                else "resultado_hipotetico"
            ),
        })

    return sorted(
        reporte,
        key=lambda x: (-x["total"], x["clase"], x["patron"]),
    )


def imprimir_reporte_contextual(filas, minimo=10, limite=25):
    """Imprime evidencia descriptiva, sin umbrales ni recomendaciones de veto."""
    integridad = auditar_integridad_contextual(filas)
    print("\n===== INTEGRIDAD DEL UNIVERSO CONTEXTUAL =====")
    print("Total:", integridad["total"], "| Resultados válidos:", integridad["con_resultado_valido"])
    print("Sin resultado:", integridad["sin_resultado_valido"], "| Clases:", integridad["por_clase"])
    print(
        "Entre evaluables, falta estrategia:", integridad["sin_estrategia"],
        "| mercado:", integridad["sin_mercado"],
        "| tendencia:", integridad["sin_tendencia"],
        "| PA:", integridad["sin_accion_precio"],
    )
    reporte = agrupar_senales_por_contexto(filas, minimo=minimo)
    print("\n===== AUDITORIA CONTEXTUAL SOMBRA / EJECUCION =====")
    print("Entradas ejecutadas en simulación: RESULTADO; canceladas: HIPOTETICO.")
    print("No inferir ventaja productiva ni modificar reglas desde este reporte.")
    print("Grupos con muestra >=", minimo, "| mostrados:", min(limite, len(reporte)))
    for fila in reporte[:limite]:
        print(
            fila["clase"], "|", fila["patron"], "|", fila["direccion"],
            "|", fila["mercado"], "|", fila["tendencia"],
            "| n:", fila["total"], "| W:", fila["wins"],
            "| L:", fila["losses"], "| WR:", fila["wr_contextual"],
            "| fuente:", fila["fuente_resultado"],
        )
    print("\n===== FACTORES POR ESTRATEGIA (ANALISIS EXPLORATORIO) =====")
    print("RSI en rangos descriptivos; Wilson 95% no es garantía futura.")
    print("Canceladas/no ejecutadas: HIPOTETICOS; operadas: RESULTADO de entrada.")
    for fila in agrupar_factores_estrategia(filas, minimo=minimo)[:limite]:
        print(
            fila["clase"], "|", fila["patron"], "|", fila["direccion"],
            "|", fila["dimension"], "=", fila["valor"],
            "| n:", fila["total"], "| W:", fila["wins"],
            "| L:", fila["losses"], "| WR:", fila["wr_contextual"],
            "| fuente:", fila["fuente_resultado"],
            "| Wilson inferior:", fila["limite_inferior_wilson"],
        )
