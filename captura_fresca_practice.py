"""Persistencia optativa de velas NUEVAS de 1 s, capturadas en PRACTICE.

No importa datos historicos ni proporciona senales operativas.
"""
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
import re

COLUMNAS = ("activo", "timestamp_utc", "open", "high", "low", "close", "capturado_en_utc", "latencia_primera_recepcion_s")


def preparar_filas(activo, velas, inicio, fin):
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,80}", activo):
        raise ValueError("ACTIVO_INVALIDO")
    if not isinstance(inicio, int) or not isinstance(fin, int) or fin <= inicio:
        raise ValueError("RANGO_INVALIDO")
    if not isinstance(velas, dict) or not velas:
        raise ValueError("SIN_VELAS_FRESCAS")
    filas = []
    marcas = sorted(velas)
    for timestamp in marcas:
        if not isinstance(timestamp, int) or not inicio <= timestamp or timestamp + 1 > fin:
            raise ValueError("VELA_FUERA_DE_SESION")
        vela = velas[timestamp]
        if int(vela["from"]) != timestamp:
            raise ValueError("TIMESTAMP_INCONSISTENTE")
        apertura, alto, bajo, cierre = (
            float(vela[campo]) for campo in ("open", "max", "min", "close")
        )
        if not all(math.isfinite(v) for v in (apertura, alto, bajo, cierre)):
            raise ValueError("PRECIO_NO_FINITO")
        if bajo > min(apertura, cierre) or alto < max(apertura, cierre):
            raise ValueError("OHLC_INVALIDO")
        filas.append((activo, timestamp, apertura, alto, bajo, cierre))
    if any(b - a != 1 for a, b in zip(marcas, marcas[1:])):
        raise ValueError("HUECO_TEMPORAL_NO_SE_EXPORTA")
    return filas


def guardar_captura_fresca(activo, velas, inicio, fin, directorio, latencias=None):
    """Una captura por archivo exclusivo; nunca reescribe ni mezcla sesiones."""
    filas = preparar_filas(activo, velas, inicio, fin)
    destino = Path(directorio)
    destino.mkdir(parents=True, exist_ok=True)
    marca_captura = datetime.now(timezone.utc).isoformat()
    ruta = destino / f"practice_1s_{activo}_{inicio}_{fin}.csv"
    # x impide sobrescribir capturas previas o mezclar periodos.
    with ruta.open("x", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)
        for fila in filas:
            demora = latencias.get(fila[1]) if latencias is not None else None
            escritor.writerow((*fila, marca_captura,
                               "" if demora is None else int(demora)))
    return ruta, len(filas)
