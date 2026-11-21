"""Seguimiento PRE-REGISTRADO de dos hipotesis CHOCH; solo observacion.

Fecha de cierre de investigacion: 2026-11-21 (UTC). Se descartan
TODOS los resultados anteriores o iguales a esa fecha, incluidos los
usados para descubrir las hipotesis. Se informa exclusivamente del
universo hipotetico de velas rechazadas, SIN fill ni PnL de IQ.

Las hipotesis se congelaron ANTES de observar velas posteriores.
Ningun resultado de este modulo concede permiso de operar.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from validar_hipotesis_sombra_oos_practice import _extraer, _metrica, _normalizar, CALIDAD

FECHA_CORTE_UTC = "2026-11-21"
HIPOTESIS = (
    ("CHOCH_BAJISTA_NORMAL", "CHOCH BAJISTA", "BAJISTA_NORMAL"),
    ("CHOCH_BAJISTA_INDEFINIDA", "CHOCH BAJISTA", "INDEFINIDA"),
)


def evaluar(rows):
    # Conservar tambien el universo bruto para no confundir falta de
    # observaciones futuras con senales pendientes de resolucion.
    filas = list(rows)
    registros, descartes = _extraer(filas)
    posteriores = [r for r in registros if r["dia"] > FECHA_CORTE_UTC]
    anteriores = [r for r in registros if r["dia"] <= FECHA_CORTE_UTC]
    pendientes_posteriores = 0
    pendientes_fecha_no_verificable = 0
    resolucion_posterior_no_confiable = 0
    for fila in filas:
        if _normalizar(fila, "decision") != "NO_OPERAR":
            continue
        # La clasificacion temporal no calcula resultados de mercado.
        # Preferir timestamp de entrada si existe; si falta en pendientes,
        # derivar inicio teorico desde el timestamp de la senal.
        try:
            entrada_cruda = str(fila.get("vela_entrada_from") or "").strip()
            if entrada_cruda:
                ts = int(entrada_cruda)
            else:
                # La columna vela_entrada_from permanece vacia HASTA que
                # se resuelve. Para clasificar el dia de una pendiente
                # usamos la vela de senal + 60, no un fill inventado.
                ts = int(str(fila.get("vela_senal_from") or "")) + 60
            if ts <= 0:
                raise ValueError("FECHA_INVALIDA")
            dia = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            pendientes_fecha_no_verificable += 1
            continue
        if dia <= FECHA_CORTE_UTC:
            continue
        if (_normalizar(fila, "resultado_hipotetico") not in ("WIN", "LOSS")
                or fila.get("calidad_tiempo") != CALIDAD):
            pendientes_posteriores += 1
            resolucion_posterior_no_confiable += 1
    salida = []
    for nombre, patron, tendencia in HIPOTESIS:
        grupo = [
            r for r in posteriores
            if r["feats"].get("patron") == patron
            and r["feats"].get("estado_tendencia") == tendencia
        ]
        por_dia = defaultdict(list)
        for r in grupo:
            por_dia[r["dia"]].append(r)
        m = _metrica(grupo)
        dias = {d: _metrica(items) for d, items in sorted(por_dia.items())}
        # Indicador de cobertura, NO una autorizacion:
        # 30 minutos independientes, 3 dias y >=10 por dia.
        cobertura = (
            m["minutos_distintos"] >= 30
            and len(dias) >= 3
            and all(v["minutos_distintos"] >= 10 for v in dias.values())
        )
        salida.append({
            "hipotesis": nombre,
            "patron": patron,
            "estado_tendencia": tendencia,
            "resumen_hipotetico": m,
            "por_dia": dias,
            "cobertura_minima_de_observacion": cobertura,
            "autoriza_operaciones": False,
            "pnl_broker": None,
        })
    return {
        "tipo": "REGISTRO_PROSPECTIVO_CHOCH_SOMBRA",
        "fecha_corte_exclusiva_utc": FECHA_CORTE_UTC,
        "filas_elegibles_anteriores_excluidas": len(anteriores),
        "filas_elegibles_posteriores": len(posteriores),
        "pendientes_o_no_confiables_posteriores": pendientes_posteriores,
        "pendientes_con_fecha_no_verificable": pendientes_fecha_no_verificable,
        "resoluciones_posteriores_no_confiables": resolucion_posterior_no_confiable,
        "diagnostico_cobertura": (
            "SIN_OBSERVACIONES_POSTERIORES"
            if not posteriores and not pendientes_posteriores
            else "PENDIENTES_SIN_RESOLUCION"
            if not posteriores and pendientes_posteriores
            else "OBSERVACIONES_POSTERIORES_DISPONIBLES"
        ),
        "descartes": dict(descartes),
        "hipotesis_congeladas": salida,
        "autoriza_operaciones": False,
        "puede_promover_memoria_oficial": False,
        "advertencia": (
            "Las hipotesis nacen de una busqueda retrospectiva; "
            "solo velas UTC desde 2026-11-22 pueden evaluarlas. "
            "Sombra no es operacion ejecutada: nunca estimar PnL broker "
            "ni cambiar estrategia basandose en este resultado."
        ),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archivo", nargs="?",
                    default="auditoria_candidatas_sombra_practice.csv")
    args = ap.parse_args()
    with Path(args.archivo).open(encoding="utf-8-sig", newline="") as f:
        print(json.dumps(evaluar(csv.DictReader(f)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
