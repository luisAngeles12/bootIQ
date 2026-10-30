"""Puerta estadistica conservadora y solo informativa para analisis PRACTICE.

Nunca autoriza ordenes: informa si hay evidencia prospectiva suficiente.
"""
from datetime import datetime, timezone
from math import sqrt


def limite_inferior_wilson(wins, total, z=1.96):
    if not 0 <= wins <= total or total <= 0:
        return 0.0
    p = wins / total
    z2 = z * z
    return (
        (p + z2 / (2 * total) - z * sqrt((p * (1 - p) + z2 / (4 * total)) / total))
        / (1 + z2 / total)
    )


def verificar_evidencia_sostenida(sesiones, objetivo=0.57):
    """Sesiones: secuencia de (activo, primera_vela_utc, eventos).

    Criterios predefinidos: >=3 dias, >=100 outcomes evaluables,
    >=15 outcomes evaluables por sesion, cada sesion supera el objetivo
    y limite inferior Wilson 95% global tambien lo supera.
    """
    if not 0 < objetivo < 1:
        raise ValueError("OBJETIVO_INVALIDO")
    sesiones = list(sesiones)
    motivos = []
    dias = set()
    conteos = []
    rangos = set()
    eventos_vistos = set()
    intervalos_por_activo = {}
    for activo, comienzo, eventos in sesiones:
        if (activo, comienzo) in rangos:
            motivos.append("SESION_DUPLICADA")
        rangos.add((activo, comienzo))
        dia_sesion = datetime.fromtimestamp(comienzo, tz=timezone.utc).date()
        dias.add(dia_sesion)
        # Una observacion debe tener timestamp verificable y no repetirse.
        # Esta puerta evita inflar el winrate con capturas solapadas.
        anterior = None
        ultimo_evento = None
        for evento in eventos:
            instante = evento.get("timestamp_senal")
            if isinstance(instante, bool) or not isinstance(instante, int):
                motivos.append("SIN_TRAZABILIDAD_TEMPORAL")
                continue
            if instante < comienzo:
                motivos.append("EVENTO_ANTERIOR_A_LA_SESION")
            if datetime.fromtimestamp(instante, tz=timezone.utc).date() != dia_sesion:
                # La division OOS se realiza por dia de inicio. Una senal
                # del dia siguiente no puede clasificarse como desarrollo.
                motivos.append("EVENTO_FUERA_DIA_SESION")
            if anterior is not None and instante <= anterior:
                motivos.append("EVENTOS_DESORDENADOS_O_REPETIDOS")
            anterior = instante
            ultimo_evento = max(instante, ultimo_evento) if ultimo_evento is not None else instante
            clave_evento = (activo, instante)
            if clave_evento in eventos_vistos:
                motivos.append("EVENTO_DUPLICADO_ENTRE_SESIONES")
            eventos_vistos.add(clave_evento)
        # Dos capturas del mismo activo pueden compartir intervalo
        # observado sin repetir exactamente el timestamp de una senal.
        # No tratarlas como muestras independientes.
        if ultimo_evento is not None:
            intervalos_por_activo.setdefault(activo, []).append((comienzo, ultimo_evento))
        evaluables = [e for e in eventos if e["resultado"] in ("WIN", "LOSS")]
        wins = sum(e["resultado"] == "WIN" for e in evaluables)
        n = len(evaluables)
        conteos.append((wins, n))
        if n < 15:
            motivos.append("MUESTRA_POR_SESION_INSUFICIENTE")
        elif wins / n <= objetivo:
            motivos.append("SESION_BAJO_OBJETIVO")
        if any(e.get("calidad_tiempo") != "TIEMPO_VERIFICADO" for e in eventos):
            motivos.append("LATENCIA_SIN_VERIFICAR_O_TARDIA")
    for intervalos in intervalos_por_activo.values():
        anterior_fin = None
        for comienzo, fin in sorted(intervalos):
            if anterior_fin is not None and comienzo <= anterior_fin:
                motivos.append("SESIONES_SOLAPADAS_MISMO_ACTIVO")
            anterior_fin = max(fin, anterior_fin) if anterior_fin is not None else fin
    total = sum(n for _, n in conteos)
    wins_total = sum(w for w, _ in conteos)
    if len(dias) < 3:
        motivos.append("MENOS_DE_TRES_DIAS")
    if total < 100:
        motivos.append("MENOS_DE_100_RESULTADOS")
    inferior = limite_inferior_wilson(wins_total, total)
    if inferior <= objetivo:
        motivos.append("LIMITE_INFERIOR_NO_SUPERA_OBJETIVO")
    return {
        "estado": "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO" if not motivos else "NO_VALIDADA",
        "sesiones": len(sesiones),
        "dias": len(dias),
        "evaluables": total,
        "wins": wins_total,
        "wr_hipotetico": round(100 * wins_total / total, 2) if total else None,
        "limite_inferior_95_pct": round(100 * inferior, 2),
        "objetivo_principal_wr_pct": 60.0,
        "minimo_aprobacion_pct": round(100 * objetivo, 2),
        "objetivo_principal_60_respaldado": (
            not motivos and inferior >= 0.60
        ),
        "motivos": sorted(set(motivos)),
        "operaciones_autorizadas": False,
    }
