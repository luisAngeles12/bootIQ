"""Seguimiento prospectivo congelado de CHOCH bajista en PRACTICE.

Hipotesis registrada con datos del 10/11-nov-2026; evaluar SOLO
operaciones posteriores al corte (fecha local del historial).
No recalibra condiciones, no dispara ordenes, no modifica memoria.
"""
import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

from auditar_consistencia_20_practice import evaluar_filas

CORTE_EXCLUSIVO = "2026-11-11"
PATRON_OBJETIVO = "CHOCH bajista"
MINIMO_OPERACIONES = 20
MINIMO_DIAS = 3


def _resumen(filas):
    n = len(filas)
    wins = sum(float(f["resultado"]) > 0 for f in filas)
    return {
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "winrate_pct": round(100 * wins / n, 2) if n else None,
        "neto": round(sum(float(f["resultado"]) for f in filas), 2),
    }


def evaluar_choch_prospectivo(filas):
    nuevas = []
    descartes = {}
    ids = set()
    fechas_naive = set()
    for f in filas:
        try:
            fecha = datetime.fromisoformat(str(f.get("fecha") or "").strip().replace("Z", "+00:00"))
        except ValueError:
            descartes["FECHA_INVALIDA"] = descartes.get("FECHA_INVALIDA", 0) + 1
            continue
        # No permitir series con zona mezclada o etiquetado temporal ambiguo.
        fechas_naive.add(fecha.tzinfo is None)
        if fecha.date().isoformat() <= CORTE_EXCLUSIVO:
            descartes["HISTORICO_ANTES_O_EN_CORTE"] = descartes.get("HISTORICO_ANTES_O_EN_CORTE", 0) + 1
            continue
        if str(f.get("estado") or "").upper().strip() != "CERRADA":
            descartes["NO_CERRADA"] = descartes.get("NO_CERRADA", 0) + 1
            continue
        oid = str(f.get("order_id") or "").strip()
        if not oid or oid in ids:
            descartes["ID_FALTANTE_O_DUPLICADO"] = descartes.get("ID_FALTANTE_O_DUPLICADO", 0) + 1
            continue
        try:
            pnl = float(str(f.get("resultado") or "").strip())
        except ValueError:
            descartes["RESULTADO_INVALIDO"] = descartes.get("RESULTADO_INVALIDO", 0) + 1
            continue
        if not math.isfinite(pnl) or pnl == 0:
            descartes["EMPATE_O_NO_FINITO"] = descartes.get("EMPATE_O_NO_FINITO", 0) + 1
            continue
        ids.add(oid)
        nueva = dict(f)
        nueva["fecha"] = fecha.isoformat()
        nueva["resultado"] = str(pnl)
        nuevas.append(nueva)
    if len(fechas_naive) > 1:
        raise ValueError("FECHAS_MIXTAS_CON_Y_SIN_ZONA")
    nuevas.sort(key=lambda x: x["fecha"])
    objetivo = [f for f in nuevas if str(f.get("patron") or "").strip().casefold() == PATRON_OBJETIVO.casefold()]
    alineada = [
        f for f in objetivo
        if str(f.get("direccion") or "").strip().upper() == "PUT"
        and str(f.get("pa_direccion") or "").strip().upper() == "PUT"
    ]
    dias = sorted({f["fecha"][:10] for f in objetivo})
    control = evaluar_filas(objetivo)
    control_pa = evaluar_filas(alineada)
    resumen_objetivo = _resumen(objetivo)
    resumen_pa = _resumen(alineada)
    # El cumplimiento de una sola ventana nunca certifica estabilidad.
    completo = len(dias) >= MINIMO_DIAS and len(objetivo) >= MINIMO_OPERACIONES
    criterio_observado = (
        completo
        and resumen_objetivo["winrate_pct"] >= 60
        and resumen_objetivo["neto"] > 0
        and control["ventanas_moviles"] > 0
        and control["ventanas_moviles_bajo_objetivo"] == 0
    )
    return {
        "modo": "CHOCH_BAJISTA_PROSPECTIVO_SOMBRA",
        "corte_historico_inclusivo": CORTE_EXCLUSIVO,
        "patron_congelado": PATRON_OBJETIVO,
        "dias_posteriores_con_choch": dias,
        "operaciones_nuevas_todas_familias": len(nuevas),
        "choch_bajista": resumen_objetivo,
        "choch_bajista_pa_alineada": resumen_pa,
        "ventanas_20_choch": {
            "total": control["ventanas_moviles"],
            "bajo_objetivo": control["ventanas_moviles_bajo_objetivo"],
        },
        "ventanas_20_pa_alineada": {
            "total": control_pa["ventanas_moviles"],
            "bajo_objetivo": control_pa["ventanas_moviles_bajo_objetivo"],
        },
        "descartes": dict(sorted(descartes.items())),
        "muestra_minima_descriptiva_alcanzada": completo,
        "criterio_de_constancia_observado": criterio_observado,
        "evidencia_estadistica_suficiente_para_cambiar_live": False,
        "ordenes_autorizadas": False,
        "memoria_productiva_modificada": False,
        "nota": "Las ventanas moviles son dependientes; un resultado favorable no garantiza rentabilidad futura.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        resultado = evaluar_choch_prospectivo(csv.DictReader(f))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
