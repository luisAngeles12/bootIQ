"""Seguimiento prospectivo de hipotesis CHOCH bajista + soporte, solo lectura.

Descubrimiento: 2026-11-04. Corte estricto: 2026-11-05 00:00 UTC.
Un resultado sombra no demuestra ejecucion, fill ni rentabilidad economica.
"""
import argparse
import json
from collections import Counter

from experimento_alineacion_sombra_practice import depurar, leer_csv
from auditoria_candidatas_sombra_practice import _id as calcular_id_sombra
from trazabilidad_rondas_sombra import auditar_intentos

CORTE_UTC = 1793836800
CONTEXTO = "PUT_SOPORTE_CERCA_SIN_RUPTURA"
PATRON = "CHOCH bajista"


def evaluar(filas, ledger):
    ids = Counter(f.get("id", "") for f in filas)
    estados = ledger["ids_por_estado"]
    excluidas = Counter()
    elegibles = []
    for fila in filas:
        candidato_id = fila.get("id", "")
        if not candidato_id or ids[candidato_id] != 1:
            excluidas["ID_FALTANTE_O_DUPLICADO"] += 1
            continue
        try:
            instante = int(fila["vela_senal_from"])
        except (KeyError, ValueError, TypeError):
            excluidas["FECHA_INVALIDA"] += 1
            continue
        try:
            id_esperado = calcular_id_sombra(
                fila["activo"], fila["patron"], fila["direccion"], instante,
            )
        except (KeyError, ValueError, TypeError):
            excluidas["IDENTIDAD_CANDIDATA_INVALIDA"] += 1
            continue
        if candidato_id != id_esperado:
            excluidas["IDENTIDAD_CANDIDATA_INVALIDA"] += 1
            continue
        if estados.get(candidato_id) != "ANALISIS_VALIDADO":
            excluidas["RONDA_NO_VALIDADA"] += 1
            continue
        if instante < CORTE_UTC:
            excluidas["DESARROLLO_ANTES_DEL_CORTE"] += 1
            continue
        elegibles.append(fila)
    eventos, descartes = depurar(elegibles)
    base = [
        e for e in eventos if e["direccion"] == "put"
        and e["accion_precio"] == CONTEXTO and len(e["patrones"]) == 1
    ]
    objetivo = [e for e in base if e["patrones"] == [PATRON]]
    comparador = [e for e in base if e["patrones"] != [PATRON]]

    def resumen(grupo):
        wins = sum(e["resultado"] == "WIN" for e in grupo)
        losses = sum(e["resultado"] == "LOSS" for e in grupo)
        empates = sum(e["resultado"] == "EMPATE" for e in grupo)
        return {
            "oportunidades": len(grupo), "wins": wins, "losses": losses,
            "empates": empates,
            "winrate_proxy_pct": round(100 * wins / len(grupo), 2) if grupo else None,
            "minutos_distintos": len({e["minuto"] for e in grupo}),
            "dias_utc": len({e["minuto"] // 86400 for e in grupo}),
        }

    return {
        "tipo": "HIPOTESIS_CONGELADA_CHOCH_SOPORTE_SOLO_LECTURA",
        "corte_utc_inclusivo": CORTE_UTC,
        "hipotesis": "CHOCH bajista PUT en soporte sin ruptura vs otros patrones PUT exclusivos del mismo contexto",
        "registros_csv": len(filas),
        "registros_post_corte_con_ronda_validada": len(elegibles),
        "exclusiones": dict(sorted(excluidas.items())),
        "descartes_depuracion": descartes,
        "objetivo_choch_bajista": resumen(objetivo),
        "comparador_otros_patrones": resumen(comparador),
        "evidencia_para_conclusion": "PENDIENTE_VALIDACION_INDEPENDIENTE",
        "winrate_60_validado": False,
        "operaciones_autorizadas": False,
        "limitaciones": [
            "La hipotesis fue elegida retrospectivamente con datos del 2026-11-04.",
            "Solo valen fechas posteriores al corte y un unico intento validado.",
            "Los eventos simultaneos y consecutivos no son independientes.",
            "No hay fill, payout ni precio de entrada ejecutado en broker.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default="auditoria_candidatas_sombra_practice.csv")
    parser.add_argument("--ledger", default="trazabilidad_rondas_sombra.jsonl")
    args = parser.parse_args()
    print(json.dumps(
        evaluar(leer_csv(args.archivo), auditar_intentos(args.ledger)),
        ensure_ascii=False, indent=2,
    ))
