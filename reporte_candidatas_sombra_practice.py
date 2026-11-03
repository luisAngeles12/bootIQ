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


def generar_reporte(ruta=RUTA_EVENTOS):
    filas = _leer(ruta)
    return {
        "tipo": "AUDITORIA_HIPOTETICA_NO_OPERATIVA",
        "archivo": str(ruta),
        "total_registros": len(filas),
        "sin_datos": not bool(filas),
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
        ],
        "operaciones_autorizadas": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default=RUTA_EVENTOS)
    args = parser.parse_args()
    print(json.dumps(generar_reporte(args.archivo), ensure_ascii=False, indent=2))
