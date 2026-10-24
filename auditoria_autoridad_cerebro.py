"""Diagnóstico pasivo de autoridad V3/CORE4 sobre resultados del backtest.

No modifica señales, memoria, umbrales ni decisiones. Las canceladas
solo disponen de resultados hipotéticos; nunca se tratan como operadas.
"""

import csv
from collections import Counter


def _verdadero(valor):
    return valor is True or str(valor).strip().lower() in {"true", "1", "si", "sí"}


def _texto(valor):
    return str(valor or "").strip().upper()


def resumir_autoridad(filas):
    """Cuenta dimensiones independientes: los vetos pueden superponerse."""
    conteos = Counter()
    resultados = Counter()
    for fila in filas:
        if not isinstance(fila, dict):
            conteos["fila_invalida"] += 1
            continue
        conteos["total"] += 1
        riesgo = _texto(fila.get("cerebro_unico_riesgo")) or "SIN_DATO"
        estado = _texto(fila.get("estado_operacion"))
        decision = _texto(fila.get("cerebro_unico_decision"))
        cancelada = estado.startswith("CANCELADA_") or decision == "NO_OPERAR"
        if cancelada:
            conteos["canceladas"] += 1
            conteos[f"canceladas_riesgo_{riesgo}"] += 1
            resultado = _texto(fila.get("resultado_hipotetico"))
            if resultado in {"WIN", "LOSS"}:
                resultados[(riesgo, resultado)] += 1
        else:
            conteos["no_canceladas"] += 1

        if _verdadero(fila.get("core4_match_previo")):
            conteos["core4_match"] += 1
            if _verdadero(fila.get("core4_invalidacion_dura_previa")):
                conteos["core4_invalidacion_dura"] += 1
            if _verdadero(fila.get("core4_invalidacion_selectiva_previa")):
                conteos["core4_invalidacion_selectiva"] += 1
            if _verdadero(fila.get("core4_elegible_estructural_previo")):
                conteos["core4_elegible_estructural"] += 1
            if _verdadero(fila.get("core4_elegible_rescate_previo")):
                conteos["core4_elegible_rescate"] += 1
            motivos = str(fila.get("core4_motivos_selectivos_previos") or "")
            for motivo in {m.strip() for m in motivos.split("|") if m.strip()}:
                conteos[f"veto_selectivo_{motivo}"] += 1

        if _verdadero(fila.get("core4_rescate")):
            conteos["core4_rescate"] += 1
        sombra = _texto(fila.get("decision_sombra_origen"))
        if sombra in {"OPERAR_SOMBRA", "OPERAR_CON_PROTOCOLO_SOMBRA"} and cancelada:
            conteos["sombra_favorable_rechazada"] += 1
    return dict(conteos), dict(resultados)


def imprimir_autoridad(filas):
    conteos, resultados = resumir_autoridad(filas)
    print("===== AUDITORIA PASIVA AUTORIDAD V3 / CORE4 =====")
    print("Los vetos se superponen; NO son causas mutuamente excluyentes.")
    print("Las canceladas solo tienen resultados HIPOTETICOS.")
    for clave in sorted(conteos):
        print(clave, ":", conteos[clave])
    for (riesgo, resultado), n in sorted(resultados.items()):
        print("HIPOTETICO", riesgo, resultado, ":", n)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auditoría pasiva de CSV backtest")
    parser.add_argument("csv", help="Ruta del CSV de resultados; solo lectura")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        imprimir_autoridad(csv.DictReader(archivo))


if __name__ == "__main__":
    main()
