"""Auditoría descriptiva por estrategia y régimen; no autoriza operaciones.

Las señales canceladas solo tienen resultado hipotético y jamás se
contabilizan como operaciones efectivamente ejecutadas.
"""

from collections import defaultdict


def _texto(valor):
    return str(valor or "").strip().upper()


def _resultado(valor):
    resultado = _texto(valor)
    return resultado if resultado in {"WIN", "LOSS"} else None


def agrupar_senales_por_contexto(filas, minimo=1):
    """Agrupa únicamente registros evaluables y separa ejecución/sombra.

    No convierte resultados hipotéticos en operaciones reales. El umbral
    ``minimo`` solo afecta la presentación, nunca una decisión del bot.
    """
    grupos = defaultdict(lambda: {"wins": 0, "losses": 0})

    for fila in filas:
        if not isinstance(fila, dict):
            continue

        decision = _texto(fila.get("cerebro_unico_decision"))
        motivo = _texto(fila.get("motivo_ejecucion"))
        if decision == "NO_OPERAR" or motivo.startswith("CANCELADA_"):
            clase = "CANCELADA_HIPOTETICA"
        elif motivo == "OPERACION_DIRECTA_CEREBRO_UNICO":
            clase = "DIRECTA_SIMULADA"
        else:
            # No inferimos ejecución a partir de una autorización: una señal
            # podría estar pendiente de protocolo o tener otro estado.
            clase = "OTRA_SENAL_EVALUADA"

        resultado = _resultado(fila.get("resultado_hipotetico"))
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
            "wr_hipotetico": round(100 * conteo["wins"] / total, 2),
        })

    return sorted(
        reporte,
        key=lambda x: (-x["total"], x["clase"], x["patron"]),
    )


def imprimir_reporte_contextual(filas, minimo=10, limite=25):
    """Imprime evidencia descriptiva, sin umbrales ni recomendaciones de veto."""
    reporte = agrupar_senales_por_contexto(filas, minimo=minimo)
    print("\n===== AUDITORIA CONTEXTUAL SOMBRA / EJECUCION =====")
    print("Resultados de canceladas y protocolos no confirmados son HIPOTETICOS.")
    print("No inferir ventaja productiva ni modificar reglas desde este reporte.")
    print("Grupos con muestra >=", minimo, "| mostrados:", min(limite, len(reporte)))
    for fila in reporte[:limite]:
        print(
            fila["clase"], "|", fila["patron"], "|", fila["direccion"],
            "|", fila["mercado"], "|", fila["tendencia"],
            "| n:", fila["total"], "| W:", fila["wins"],
            "| L:", fila["losses"], "| WR hipotético:", fila["wr_hipotetico"],
        )
