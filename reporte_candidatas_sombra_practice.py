"""Resumen estadístico descriptivo de candidatas rechazadas en PRACTICE.

No valida estrategias, no habilita operaciones y no escribe en memoria CC2.
"""
import argparse
import json
from collections import defaultdict
from auditoria_candidatas_sombra_practice import RUTA_EVENTOS, _leer
from validar_evidencia_practice import limite_inferior_wilson

VALIDOS = {"WIN", "LOSS", "EMPATE"}


def resumen_eventos(filas, campo="patron"):
    grupos = defaultdict(list)
    for fila in filas:
        if fila.get("decision") != "NO_OPERAR":
            continue
        grupos[str(fila.get(campo) or "SIN_DATO")].append(fila)
    salida = []
    for nombre, eventos in sorted(grupos.items()):
        terminados = [f for f in eventos if f.get("resultado_hipotetico") in VALIDOS]
        wins = sum(f["resultado_hipotetico"] == "WIN" for f in terminados)
        losses = sum(f["resultado_hipotetico"] == "LOSS" for f in terminados)
        empates = sum(f["resultado_hipotetico"] == "EMPATE" for f in terminados)
        total_binario = wins + losses
        # Los empates se conservan separados. La tasa incluye todos los
        # desenlaces en el denominador y nunca se confunde con rentabilidad.
        total_resueltos = len(terminados)
        wilson = limite_inferior_wilson(wins, total_resueltos)
        dias = {
            int(f["vela_senal_from"]) // 86400
            for f in terminados if str(f.get("vela_senal_from", "")).isdigit()
        }
        salida.append({
            campo: nombre,
            "candidatas": len(eventos),
            "pendientes": len(eventos) - total_resueltos,
            "win": wins, "loss": losses, "empates": empates,
            "evaluables": total_resueltos,
            "winrate_hipotetico_pct": (
                round(100 * wins / total_resueltos, 2)
                if total_resueltos else None
            ),
            "limite_inferior_wilson_95_pct": (
                round(100 * wilson, 2) if total_resueltos else None
            ),
            "dias_utc_con_resultados": len(dias),
            "objetivo_60_observado": (
                100 * wins / total_resueltos > 60 if total_resueltos else False
            ),
            "validacion_60": "NO_VALIDADA",
            "operaciones_autorizadas": False,
        })
    return salida




def resumen_oportunidades_independientes(filas):
    """Una oportunidad por activo y vela, sin duplicar estrategias coincidentes.

    Si existen señales CALL y PUT en el mismo activo/minuto, se excluyen
    ambas: la información no permite identificar una sola entrada.
    Varias estrategias en la misma dirección cuentan como un evento,
    sin atribuirlo arbitrariamente a una estrategia concreta.
    """
    claves = defaultdict(list)
    descartadas = 0
    for fila in filas:
        if fila.get("decision") != "NO_OPERAR":
            continue
        if str(fila.get("calidad_mercado", "")).upper() not in {"NORMAL", "LIMPIO"}:
            descartadas += 1
            continue
        if fila.get("resultado_hipotetico") not in VALIDOS:
            continue
        if fila.get("calidad_tiempo") != "HIPOTETICO_VELA_COMPLETA_SIN_FILL":
            descartadas += 1
            continue
        try:
            ts = int(fila.get("vela_senal_from", ""))
        except (TypeError, ValueError):
            descartadas += 1
            continue
        if ts <= 0 or not fila.get("activo"):
            descartadas += 1
            continue
        claves[(fila["activo"], ts)].append(fila)

    total = wins = losses = empates = conflictos = agrupadas = 0
    dias = set()
    por_estrategia = defaultdict(lambda: {"win": 0, "loss": 0, "empates": 0})
    for (activo, ts), candidatas in claves.items():
        direcciones = {str(f.get("direccion", "")).lower() for f in candidatas}
        resultados = {f.get("resultado_hipotetico") for f in candidatas}
        if len(direcciones) != 1 or not direcciones.issubset({"call", "put"}) or len(resultados) != 1:
            conflictos += 1
            continue
        resultado = next(iter(resultados))
        total += 1
        dias.add(ts // 86400)
        agrupadas += len(candidatas) - 1
        if resultado == "WIN":
            wins += 1
        elif resultado == "LOSS":
            losses += 1
        else:
            empates += 1
        patrones = {str(f.get("patron") or "") for f in candidatas}
        if len(patrones) == 1:
            por_estrategia[next(iter(patrones))][resultado.lower() if resultado != "EMPATE" else "empates"] += 1

    return {
        "oportunidades_independientes": total,
        "wins": wins, "losses": losses, "empates": empates,
        "candidatas_duplicadas_agrupadas": agrupadas,
        "oportunidades_con_conflicto_excluidas": conflictos,
        "filas_excluidas_por_calidad_o_trazabilidad": descartadas,
        "dias_utc": len(dias),
        "winrate_proxy_pct": round(100 * wins / total, 2) if total else None,
        "limite_wilson_proxy_95_pct": (
            round(100 * limite_inferior_wilson(wins, total), 2)
            if total else None
        ),
        "atribucion_estrategia_sin_ambiguedad": dict(por_estrategia),
        "resultado": "PROXY_NO_VALIDADO",
        "operaciones_autorizadas": False,
    }

def generar_reporte(ruta=RUTA_EVENTOS):
    filas = _leer(ruta)
    return {
        "tipo": "AUDITORIA_HIPOTETICA_NO_OPERATIVA",
        "archivo": str(ruta),
        "total_registros": len(filas),
        "sin_datos": not bool(filas),
        "oportunidades_sin_duplicados": resumen_oportunidades_independientes(filas),
        "por_estrategia": resumen_eventos(filas, "patron"),
        "por_mercado": resumen_eventos(filas, "tipo_mercado"),
        "por_calidad": resumen_eventos(filas, "calidad_mercado"),
        "por_accion_precio": resumen_eventos(filas, "accion_precio"),
        "por_activo": resumen_eventos(filas, "activo"),
        "por_direccion": resumen_eventos(filas, "direccion"),
        "observaciones": [
            "WIN/LOSS hipoteticos basados en apertura/cierre de la vela posterior.",
            "No se verifican precio de ejecucion, segundo de entrada, payout ni latencia.",
            "No existe validacion OOS ni permiso para operar.",
            "Los eventos simultaneos de un activo se agrupan; conflictos CALL/PUT se excluyen.",
        ],
        "operaciones_autorizadas": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default=RUTA_EVENTOS)
    args = parser.parse_args()
    print(json.dumps(generar_reporte(args.archivo), ensure_ascii=False, indent=2))
