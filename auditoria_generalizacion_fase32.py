"""Contraste descriptivo en universo ampliado de señales del replay.

El universo del replay puede superar 20 activos; eso NO modifica el
máximo de veinte mercados simultáneamente admitidos por el bot.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from auditoria_hipotesis_fase32 import coincide_hipotesis, META_WINRATE


def _dia_utc(fila):
    try:
        valor = fila.get("fecha_senal") or fila.get("fecha")
        if valor is None:
            return "SIN_FECHA"
        if str(valor).replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(valor), timezone.utc).date().isoformat()
        return str(valor)[:10]
    except (ValueError, TypeError, OverflowError, OSError):
        return "SIN_FECHA"


def evaluar_generalizacion(filas):
    """Cuenta señales únicas sin promover WIN hipotético a PNL ejecutado."""
    datos = []
    identidades = set()
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        # Solo se deduplica con identidad temporal y estructural completa.
        # La falta de telemetría NO se interpreta como duplicación.
        marca = fila.get("fecha_senal") or fila.get("fecha")
        clave = (marca, fila.get("activo"), fila.get("patron"), fila.get("direccion"))
        if all(v not in (None, "") for v in clave):
            if clave in identidades:
                raise ValueError("Señal repetida en universo de generalización")
            identidades.add(clave)
        datos.append(fila)
    resultado = {}
    for nombre in ("A", "B"):
        muestras = [r for r in datos
                    if isinstance(r, dict) and coincide_hipotesis(r, nombre)
                    and r.get("resultado_hipotetico") in ("WIN", "LOSS")]
        ganadas = sum(r["resultado_hipotetico"] == "WIN" for r in muestras)
        por_dia = defaultdict(list)
        for r in muestras:
            por_dia[_dia_utc(r)].append(r)
        n = len(muestras)
        resultado[nombre] = {
            "n_senales": n, "wins_hipoteticos": ganadas,
            "losses_hipoteticas": n - ganadas,
            "winrate_hipotetico": round(100*ganadas/n, 2) if n else None,
            "mercados_distintos_en_replay": len({r.get("activo") for r in muestras if r.get("activo")}),
            "dias": {dia: {"n": len(grupo),
                            "wins": sum(r["resultado_hipotetico"] == "WIN" for r in grupo)}
                     for dia, grupo in sorted(por_dia.items())},
            "supera_meta_59": bool(n and 100*ganadas/n >= META_WINRATE),
            "apto_para_promocion": False,
            "nota": "Replay descriptivo: no equivale a operar mercados simultaneamente",
        }
    return resultado
