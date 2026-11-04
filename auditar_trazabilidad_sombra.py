"""Audita pertenencia y estado FINAL de candidatas SIN cambiar el CSV.

Todo ID sin unica ronda ANALISIS_VALIDADO queda fuera de la muestra
estrictamente trazable. La ausencia de ledger no implica que sea LOSS.
"""
import argparse
import json
from collections import Counter

from experimento_alineacion_sombra_practice import leer_csv
from trazabilidad_rondas_sombra import auditar_intentos


def auditar(filas, ledger):
    ids_por_estado = ledger["ids_por_estado"]
    conteo = Counter()
    ids_duplicados = Counter(f["id"] for f in filas)
    validas = []
    for f in filas:
        if ids_duplicados[f["id"]] > 1:
            estado = "ID_DUPLICADO_CSV"
        else:
            estado = ids_por_estado.get(f["id"], "SIN_TRAZABILIDAD")
        conteo[estado] += 1
        if estado == "ANALISIS_VALIDADO":
            validas.append(f)
    return {
        "tipo": "AUDITORIA_PROVENIENCIA_SOMBRA_NO_OPERATIVA",
        "registros_csv": len(filas),
        "intentos_ledger": ledger["intentos"],
        "candidatas_distintas_ledger": ledger["candidatas_distintas"],
        "filas_por_estado": dict(sorted(conteo.items())),
        "filas_con_intento_validado_unico": len(validas),
        "filas_fuera_de_muestra_estricta": len(filas) - len(validas),
        "advertencias": [
            "El CSV anterior al ledger se reporta SIN_TRAZABILIDAD, nunca se reetiqueta.",
            "Un mismo candidato vinculado a varios intentos es AMBIGUO, no validado.",
            "Una ronda validada no verifica fill, precio de entrada ni payout.",
            "Esta auditoria no genera operaciones ni alimenta memoria oficial.",
        ],
        "ordenes_autorizadas": False,
        "validacion_winrate_60": "NO_VALIDADA",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default="auditoria_candidatas_sombra_practice.csv")
    parser.add_argument("--ledger", default="trazabilidad_rondas_sombra.jsonl")
    args = parser.parse_args()
    print(json.dumps(auditar(leer_csv(args.archivo), auditar_intentos(args.ledger)),
                     ensure_ascii=False, indent=2))
