"""Evaluacion observacional de filtros PA predefinidos (solo PRACTICE).

Los filtros se definen ANTES de leer los resultados. Solo contabilizan
operaciones historicamente ejecutadas, sin reconstruir oportunidades
perdidas ni asumir que la seleccion causaria un resultado futuro.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from auditar_consistencia_20_practice import evaluar_filas


def _normalizar(row):
    if str(row.get("estado") or "").strip().upper() != "CERRADA":
        return None
    identificador = str(row.get("order_id") or "").strip()
    if not identificador:
        return None
    try:
        pnl = float(str(row.get("resultado")).strip())
        fecha = datetime.fromisoformat(str(row.get("fecha") or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if not math.isfinite(pnl) or pnl == 0:
        return None
    direccion = str(row.get("direccion") or "").strip().upper()
    pa = str(row.get("pa_direccion") or "").strip().upper()
    if direccion not in {"CALL", "PUT"}:
        alineacion = "DESCONOCIDA"
    elif pa in {"CALL", "PUT"}:
        alineacion = "ALINEADA" if pa == direccion else "CONTRARIA"
    elif pa in {"NEUTRA", "NEUTRAL"}:
        alineacion = "NEUTRA"
    else:
        alineacion = "DESCONOCIDA"
    snapshot = str(row.get("auditoria_riesgo_compuesto_json") or "").strip()
    riesgo = "DESCONOCIDO"
    if snapshot:
        try:
            datos = json.loads(snapshot)
            if isinstance(datos, dict):
                riesgo = str(datos.get("riesgo_nivel") or "DESCONOCIDO").upper()
        except (TypeError, ValueError):
            pass
    return {
        "fecha": fecha,
        "order_id": identificador,
        "estado": "CERRADA",
        "resultado": pnl,
        "pnl": pnl,
        "alineacion": alineacion,
        "riesgo": riesgo,
        "patron": str(row.get("patron") or "SIN_PATRON").strip(),
    }


def evaluar_filtros_sombra(filas, minimo_validacion=20):
    if minimo_validacion < 1:
        raise ValueError("MINIMO_VALIDACION_INVALIDO")
    registros = []
    ids = set()
    descartados = defaultdict(int)
    for fila in filas:
        x = _normalizar(fila)
        if x is None:
            descartados["NO_EVALUABLE"] += 1
            continue
        if x["order_id"] in ids:
            descartados["ID_DUPLICADO"] += 1
            continue
        ids.add(x["order_id"])
        registros.append(x)
    zonas = {r["fecha"].tzinfo is None for r in registros}
    if len(zonas) > 1:
        raise ValueError("FECHAS_CON_ZONAS_MIXTAS")
    registros.sort(key=lambda r: r["fecha"])
    dias = sorted({r["fecha"].date().isoformat() for r in registros})
    cobertura = {
        "total_evaluables": len(registros),
        "con_snapshot_riesgo": sum(r["riesgo"] != "DESCONOCIDO" for r in registros),
        "sin_snapshot_riesgo": sum(r["riesgo"] == "DESCONOCIDO" for r in registros),
        "por_dia": {},
    }
    for dia in dias:
        dia_registros = [r for r in registros if r["fecha"].date().isoformat() == dia]
        cobertura["por_dia"][dia] = {
            "total": len(dia_registros),
            "con_snapshot_riesgo": sum(r["riesgo"] != "DESCONOCIDO" for r in dia_registros),
            "sin_snapshot_riesgo": sum(r["riesgo"] == "DESCONOCIDO" for r in dia_registros),
        }
    ultimo_dia = dias[-1] if dias else None

    # Hipotesis fijas: no se optimizan segun WIN/LOSS.
    reglas = (
        ("BASELINE_TODAS", lambda r: True),
        ("PA_ALINEADA", lambda r: r["alineacion"] == "ALINEADA"),
        ("PA_NO_CONTRARIA_CONOCIDA", lambda r: r["alineacion"] in {"ALINEADA", "NEUTRA"}),
        ("RIESGO_BAJO_CONOCIDO", lambda r: r["riesgo"] == "BAJO"),
        ("PA_ALINEADA_Y_RIESGO_BAJO", lambda r: r["alineacion"] == "ALINEADA" and r["riesgo"] == "BAJO"),
    )

    def resumen(seleccionados, universo):
        n = len(seleccionados)
        wins = sum(x["pnl"] > 0 for x in seleccionados)
        winrate = 100 * wins / n if n else None
        return {
            "universo": len(universo),
            "n": n,
            "volumen_retenido_pct": round(100 * n / len(universo), 2) if universo else None,
            "wins": wins,
            "losses": n - wins,
            "winrate_pct": round(winrate, 2) if winrate is not None else None,
            "neto": round(sum(x["pnl"] for x in seleccionados), 2),
            "cumple_muestra_20": n >= 20,
        }

    # Comparacion por patron y por dia: denominador fijo por familia;
    # nunca seleccionar una familia por el resultado del ultimo dia.
    patrones = sorted({r["patron"] for r in registros})
    por_patron_dia = []
    for patron in patrones:
        universo_patron = [r for r in registros if r["patron"] == patron]
        por_dia = {}
        for dia in dias:
            universo_dia = [
                r for r in universo_patron
                if r["fecha"].date().isoformat() == dia
            ]
            alineadas_dia = [
                r for r in universo_dia if r["alineacion"] == "ALINEADA"
            ]
            por_dia[dia] = {
                "original": resumen(universo_dia, universo_dia),
                "pa_alineada": resumen(alineadas_dia, universo_dia),
            }
        alineadas_patron = [
            r for r in universo_patron if r["alineacion"] == "ALINEADA"
        ]
        ventanas_original = evaluar_filas(universo_patron)
        ventanas_alineada = evaluar_filas(alineadas_patron)
        dias_con_20 = [
            dia for dia in dias
            if por_dia[dia]["pa_alineada"]["n"] >= 20
        ]
        por_patron_dia.append({
            "patron": patron,
            "total_original": resumen(universo_patron, universo_patron),
            "total_pa_alineada": resumen(alineadas_patron, universo_patron),
            "ventanas_20_original": {
                "total": ventanas_original["ventanas_moviles"],
                "bajo_60": ventanas_original["ventanas_moviles_bajo_objetivo"],
                "todas_cumplen": ventanas_original["consistencia_20_observada"],
            },
            "ventanas_20_pa_alineada": {
                "total": ventanas_alineada["ventanas_moviles"],
                "bajo_60": ventanas_alineada["ventanas_moviles_bajo_objetivo"],
                "todas_cumplen": ventanas_alineada["consistencia_20_observada"],
            },
            "por_dia": por_dia,
            "dias_con_al_menos_20_pa_alineadas": len(dias_con_20),
            "consistencia_60_y_neto_por_dia": (
                len(dias_con_20) >= 3
                and all(
                    por_dia[dia]["pa_alineada"]["winrate_pct"] >= 60
                    and por_dia[dia]["pa_alineada"]["neto"] > 0
                    for dia in dias_con_20
                )
                and len(dias_con_20) == len(dias)
            ),
            "evidencia_prospectiva_suficiente": False,
            "cambios_operativos_autorizados": False,
        })

    salida = []
    for nombre, regla in reglas:
        train = [x for x in registros if x["fecha"].date().isoformat() != ultimo_dia]
        valid = [x for x in registros if x["fecha"].date().isoformat() == ultimo_dia]
        elegidos_train = [x for x in train if regla(x)]
        elegidos_valid = [x for x in valid if regla(x)]
        elegidos_todos = [x for x in registros if regla(x)]
        # 20 operaciones ejecutadas por el bot original en la misma secuencia.
        ventanas = evaluar_filas(elegidos_valid)
        validacion = resumen(elegidos_valid, valid)
        salida.append({
            "hipotesis": nombre,
            "total": resumen(elegidos_todos, registros),
            "train": resumen(elegidos_train, train),
            "ultimo_dia_no_usado_para_ajustar_regla": validacion,
            "ventanas_20_ultimo_dia": ventanas["ventanas_moviles"],
            "ventanas_20_bajo_60_ultimo_dia": ventanas["ventanas_moviles_bajo_objetivo"],
            "evaluacion_con_muestra_suficiente": (
                len(dias) >= 2 and validacion["n"] >= minimo_validacion
            ),
        })
    return {
        "modo": "FILTROS_SOMBRA_NO_AUTORIZANTES",
        "dias": dias,
        "ultimo_dia": ultimo_dia,
        "descartes": dict(sorted(descartados.items())),
        "cobertura_riesgo": cobertura,
        "hipotesis_predefinidas": salida,
        "pa_alineada_por_patron_y_dia": por_patron_dia,
        "limitaciones": [
            "Solo observa operaciones ejecutadas; no evalua oportunidades nunca operadas.",
            "La prueba del ultimo dia no es una validacion prospectiva.",
            "Un filtro no puede garantizar ventanas futuras de 20 con 60 por ciento.",
            "Las comparaciones de riesgo excluyen registros sin snapshot y no representan todo el historial.",
            "Las familias se reportan completas, incluso si tienen muestras pequenas o resultados negativos.",
            "La consistencia descriptiva por dia no reemplaza validacion prospectiva.",
            "No modifica estrategia, thresholds, ordenes, ni memoria productiva.",
        ],
        "cambios_operativos_autorizados": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as archivo:
        reporte = evaluar_filtros_sombra(csv.DictReader(archivo))
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
