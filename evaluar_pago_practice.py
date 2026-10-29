"""Evaluacion conservadora de pagos de opciones binarias en PRACTICE.

El payout debe venir documentado antes de cada posible entrada, no
deducirse de WIN/LOSS ni suponerse constante. No emite operaciones.
"""
from math import isfinite

from validar_evidencia_practice import limite_inferior_wilson


def evaluar_viabilidad_pago(eventos, objetivo=0.57):
    """Cada evento evaluable requiere payout_neto, payout_fuente y tiempo.

    payout_neto: beneficio por 1 unidad apostada si WIN (p.ej. 0.8).
    LOSS supone perdida de 1 unidad. EMPATE/SIN_FUTURO no son evaluables
    y no pueden usarse para estimar rentabilidad.
    """
    eventos = list(eventos)
    motivos = []
    validos = []
    payouts = []
    for evento in eventos:
        if evento.get("resultado") not in ("WIN", "LOSS"):
            continue
        if evento.get("calidad_tiempo") != "TIEMPO_VERIFICADO":
            motivos.append("TIEMPO_NO_VERIFICADO")
        pago = evento.get("payout_neto")
        if (isinstance(pago, bool) or not isinstance(pago, (int, float))
                or not isfinite(pago) or not 0 < pago <= 1):
            motivos.append("PAYOUT_NO_VERIFICADO")
            continue
        if evento.get("payout_fuente") != "PRACTICE_PREENTRADA":
            motivos.append("PAYOUT_SIN_PROCEDENCIA_PREENTRADA")
            continue
        payouts.append(float(pago))
        validos.append(evento)
    if len(validos) != sum(e.get("resultado") in ("WIN", "LOSS") for e in eventos):
        motivos.append("EVENTOS_EVALUABLES_SIN_PAYOUT")
    wins = sum(e["resultado"] == "WIN" for e in validos)
    total = len(validos)
    inferior = limite_inferior_wilson(wins, total)
    # El pago mas bajo documentado evita inferir ventaja con una media
    # elevada por pocos eventos de alta remuneracion.
    minimo = min(payouts) if payouts else None
    equilibrio = 1 / (1 + minimo) if minimo is not None else None
    if total < 100:
        motivos.append("MUESTRA_INSUFICIENTE")
    if equilibrio is None or inferior <= max(objetivo, equilibrio):
        motivos.append("LIMITE_ESTADISTICO_NO_SUPERA_OBJETIVO_Y_EQUILIBRIO")
    return {
        "estado": ("EVIDENCIA_ECONOMICA_PRELIMINAR" if not motivos
                   else "NO_VALIDADA"),
        "evaluables_con_pago": total,
        "wins": wins,
        "wr_observado_pct": round(100 * wins / total, 2) if total else None,
        "limite_inferior_95_pct": round(100 * inferior, 2),
        "payout_minimo_pct": round(100 * minimo, 2) if minimo is not None else None,
        "equilibrio_con_payout_minimo_pct": (round(100 * equilibrio, 2)
                                            if equilibrio is not None else None),
        "motivos": sorted(set(motivos)),
        "operaciones_autorizadas": False,
        "advertencia": "MODELO_SIN_COMISIONES_REEMBOLSOS_NI_COSTES_DE_EJECUCION",
    }
