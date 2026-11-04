"""Diagnostico de candidatas sin cierre, exclusivamente lectura.

No reconstruye velas, no asigna WIN/LOSS ni modifica CSV o memoria.
La ultima senal por activo NO prueba que el activo dejara de recibir velas.
"""
import argparse
import json
from collections import Counter, defaultdict

from experimento_alineacion_sombra_practice import leer_csv
from trazabilidad_rondas_sombra import auditar_intentos

PENDIENTE = "PENDIENTE_VELA_POSTERIOR"
SIN_BUFFER = "SIN_VELA_POSTERIOR_EN_BUFFER"
SIN_RESULTADO = frozenset((PENDIENTE, SIN_BUFFER))


def diagnosticar(filas, ledger):
    estados = ledger["ids_por_estado"]
    por_activo = defaultdict(list)
    for fila in filas:
        por_activo[fila.get("activo", "")].append(fila)

    resultados = Counter()
    conflictos = []
    activos = []
    for activo, registros in sorted(por_activo.items()):
        tiempos = []
        for fila in registros:
            try:
                tiempos.append(int(fila.get("vela_senal_from", "")))
            except (TypeError, ValueError):
                pass
        ultimo = max(tiempos) if tiempos else None
        pendientes = [f for f in registros if f.get("calidad_tiempo") == PENDIENTE
                      and not f.get("resultado_hipotetico")]
        perdidas_buffer = [f for f in registros if f.get("calidad_tiempo") == SIN_BUFFER
                           and not f.get("resultado_hipotetico")]
        for fila in registros:
            calidad = fila.get("calidad_tiempo", "")
            resultado = fila.get("resultado_hipotetico", "")
            if (calidad in SIN_RESULTADO and resultado) or (
                calidad == "HIPOTETICO_VELA_COMPLETA_SIN_FILL"
                and resultado not in ("WIN", "LOSS", "EMPATE")
            ):
                conflictos.append(fila.get("id", ""))
            if calidad in SIN_RESULTADO and not resultado:
                resultados[(estados.get(fila.get("id", ""), "SIN_TRAZABILIDAD"),
                            calidad)] += 1
        if pendientes or perdidas_buffer:
            activos.append({
                "activo": activo,
                "pendientes": len(pendientes),
                "sin_vela_en_buffer": len(perdidas_buffer),
                "ultimo_minuto_con_senal": ultimo,
                "pendientes_en_ultimo_minuto_con_senal": sum(
                    ultimo is not None
                    and f.get("vela_senal_from", "").isdigit()
                    and int(f["vela_senal_from"]) == ultimo
                    for f in pendientes
                ),
                "sin_buffer_con_senal_posterior": sum(
                    f.get("vela_senal_from", "").isdigit()
                    and any(
                        g.get("vela_senal_from", "").isdigit()
                        and int(g["vela_senal_from"]) > int(f["vela_senal_from"])
                        for g in registros
                    )
                    for f in perdidas_buffer
                ),
            })

    return {
        "tipo": "DIAGNOSTICO_CIERRE_SOMBRA_SOLO_LECTURA",
        "registros_csv": len(filas),
        "pendientes": sum(x["pendientes"] for x in activos),
        "sin_vela_en_buffer": sum(x["sin_vela_en_buffer"] for x in activos),
        "activos_con_pendientes": sum(x["pendientes"] > 0 for x in activos),
        "pendientes_en_ultimo_minuto_con_senal": sum(
            x["pendientes_en_ultimo_minuto_con_senal"] for x in activos
        ),
        "sin_buffer_con_senal_posterior": sum(
            x["sin_buffer_con_senal_posterior"] for x in activos
        ),
        "no_resueltos_por_procedencia": [
            {"estado": estado, "calidad_tiempo": calidad, "cantidad": cantidad}
            for (estado, calidad), cantidad in sorted(resultados.items())
        ],
        "inconsistencias_resultado_estado": len(conflictos),
        "activos": activos,
        "advertencias": [
            "Una senal posterior no demuestra disponibilidad de la vela requerida.",
            "Ultima senal no significa ultimo analisis ni ultima vela recibida.",
            "No se imputan WIN, LOSS, fill ni payout.",
        ],
        "autoriza_operaciones": False,
        "valida_winrate_60": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default="auditoria_candidatas_sombra_practice.csv")
    parser.add_argument("--ledger", default="trazabilidad_rondas_sombra.jsonl")
    args = parser.parse_args()
    print(json.dumps(
        diagnosticar(leer_csv(args.archivo), auditar_intentos(args.ledger)),
        ensure_ascii=False, indent=2,
    ))
