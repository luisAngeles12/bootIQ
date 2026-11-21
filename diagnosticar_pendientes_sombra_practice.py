"""Auditoria de resoluciones sombra sin reescribir datos ni abrir operaciones.

Separa pendientes recientes, pendientes rezagadas y velas fuera de buffer.
El estado de una vela no se infiere de su antiguedad: nunca crear WIN/LOSS.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ESTADOS_SIN_RESULTADO = (
    "PENDIENTE_VELA_POSTERIOR", "SIN_VELA_POSTERIOR_EN_BUFFER"
)


def diagnosticar(filas, referencia_utc=None):
    if referencia_utc is None:
        referencia_utc = datetime.now(timezone.utc)
    if referencia_utc.tzinfo is None or referencia_utc.utcoffset() is None:
        raise ValueError("REFERENCIA_SIN_ZONA_HORARIA")
    ahora = referencia_utc.astimezone(timezone.utc)
    por_estado = Counter()
    por_dia = defaultdict(Counter)
    por_activo = defaultdict(Counter)
    pendientes_antiguas = 0
    pendientes_recientes = 0
    pendientes_futuras = 0
    sin_timestamp = 0
    timestamps_inconsistentes = 0
    for fila in filas:
        if str(fila.get("decision") or "").strip().upper() != "NO_OPERAR":
            continue
        if str(fila.get("resultado_hipotetico") or "").strip():
            continue
        estado = str(fila.get("calidad_tiempo") or "").strip()
        if estado not in ESTADOS_SIN_RESULTADO:
            continue
        por_estado[estado] += 1
        activo = str(fila.get("activo") or "SIN_ACTIVO")
        por_activo[activo][estado] += 1
        try:
            ts = int(str(fila.get("vela_senal_from") or ""))
            if ts <= 0:
                raise ValueError("TIMESTAMP_NO_POSITIVO")
            fecha = datetime.fromtimestamp(ts, timezone.utc)
        except (ValueError, TypeError, OverflowError, OSError):
            sin_timestamp += 1
            por_dia["FECHA_NO_VERIFICABLE"][estado] += 1
            continue
        por_dia[fecha.date().isoformat()][estado] += 1
        if estado != "PENDIENTE_VELA_POSTERIOR":
            continue
        # Solo clasificacion de antiguedad: el cierre esperado seria ts+120
        # para una vela de senal cerrada seguida por una vela de 60s.
        # Si falta confirmar el reloj de la fuente, no resolver.
        segundos = (ahora - fecha).total_seconds()
        if segundos < 0:
            pendientes_futuras += 1
        elif segundos >= 3600:
            pendientes_antiguas += 1
        else:
            pendientes_recientes += 1
        # Una vela de entrada en conflicto es anomalía, no WIN/LOSS.
        entrada_cruda = str(fila.get("vela_entrada_from") or "").strip()
        if entrada_cruda:
            try:
                if int(entrada_cruda) != ts + 60:
                    timestamps_inconsistentes += 1
            except (ValueError, TypeError, OverflowError):
                timestamps_inconsistentes += 1
    return {
        "tipo": "DIAGNOSTICO_PENDIENTES_SOMBRA_SOLO_LECTURA",
        "referencia_utc": ahora.isoformat(),
        "total_sin_resultado": sum(por_estado.values()),
        "por_estado": dict(sorted(por_estado.items())),
        "por_dia_utc": {k: dict(sorted(v.items()))
                        for k, v in sorted(por_dia.items())},
        "por_activo": {k: dict(sorted(v.items()))
                       for k, v in sorted(por_activo.items())},
        "pendientes_mas_de_una_hora": pendientes_antiguas,
        "pendientes_ultima_hora": pendientes_recientes,
        "pendientes_en_futuro": pendientes_futuras,
        "sin_timestamp_senal": sin_timestamp,
        "timestamps_entrada_inconsistentes": timestamps_inconsistentes,
        "hipotesis_causal": (
            "La conciliacion requiere que el mismo activo vuelva a "
            "procesarse con un buffer continuo que contenga la vela "
            "siguiente. No se ha demostrado por fila la ausencia de "
            "este reprocesamiento."
        ),
        "autoriza_operaciones": False,
        "altera_historial": False,
        "genera_resultados": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archivo", nargs="?",
                    default="auditoria_candidatas_sombra_practice.csv")
    args = ap.parse_args()
    with Path(args.archivo).open("r", newline="", encoding="utf-8-sig") as f:
        resultado = diagnosticar(csv.DictReader(f))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
