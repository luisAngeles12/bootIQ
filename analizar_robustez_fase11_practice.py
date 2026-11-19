"""Análisis descriptivo de incertidumbre para cierres PRACTICE, sin broker.

No es un certificado de rentabilidad ni una prueba de independencia de trades.
"""
from collections import Counter
from datetime import datetime, timezone
from math import sqrt


RESULTADOS = {"WIN", "LOSS", "EMPATE"}


def wilson_95(wins, total):
    """Intervalo Wilson binomial al 95%; solo interpretable bajo sus supuestos."""
    if not isinstance(wins, int) or not isinstance(total, int) or total < 0 or wins < 0 or wins > total:
        raise ValueError("CONTEOS_INVALIDOS")
    if total == 0:
        return None
    z = 1.959963984540054
    p = wins / total
    z2 = z * z
    denom = 1 + z2 / total
    centro = (p + z2 / (2 * total)) / denom
    margen = z * sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / denom
    return [round(max(0.0, centro - margen) * 100, 2),
            round(min(1.0, centro + margen) * 100, 2)]


def _fecha_utc(cadena):
    try:
        fecha = datetime.fromisoformat(str(cadena).replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            raise ValueError("ZONA_HORARIA_REQUERIDA")
        return fecha.astimezone(timezone.utc).date().isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("FECHA_CIERRE_INVALIDA") from exc


def analizar(filas):
    """Lista de filas con resultado, fecha_cierre y tipo_cuenta; sin filtrar pérdidas."""
    registros = list(filas)
    por_dia = Counter()
    wins_por_dia = Counter()
    for fila in registros:
        if not isinstance(fila, dict):
            raise ValueError("FILA_INVALIDA")
        if str(fila.get("tipo_cuenta", "")).strip().upper() != "PRACTICE":
            raise ValueError("SOLO_PRACTICE")
        resultado = str(fila.get("resultado", "")).strip().upper()
        if resultado not in RESULTADOS:
            raise ValueError("RESULTADO_NO_CERRADO")
        dia = _fecha_utc(fila.get("fecha_cierre"))
        por_dia[dia] += 1
        if resultado == "WIN":
            wins_por_dia[dia] += 1
    total = len(registros)
    wins = sum(wins_por_dia.values())
    intervalo = wilson_95(wins, total)
    return {
        "operaciones": total,
        "wins": wins,
        "winrate_pct": round(100 * wins / total, 2) if total else None,
        "intervalo_wilson_95_pct": intervalo,
        "dias_utc_distintos": len(por_dia),
        "operaciones_por_dia_utc": dict(sorted(por_dia.items())),
        "wins_por_dia_utc": dict(sorted(wins_por_dia.items())),
        "limite_inferior_supera_60": intervalo is not None and intervalo[0] >= 60.0,
        "advertencia": "Wilson supone ensayos binomiales comparables e independientes. "
                       "La correlacion temporal, dependencia entre activos y seleccion multiple "
                       "pueden invalidar su cobertura. No certifica beneficio ni resultados futuros.",
        "validacion_prospectiva_confirmada": False,
        "autoriza_real": False,
    }
