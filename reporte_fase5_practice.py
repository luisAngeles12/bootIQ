"""Informe integrado fase 5 PRACTICE (historial cerrado, solo lectura).

Unifica consistencia de 20, comparacion temporal y Price Action/riesgo.
No entrena el cerebro ni altera ningun criterio de entrada o salida.
"""
import argparse
import csv
import json
from pathlib import Path

from auditar_consistencia_20_practice import evaluar_filas
from experimentos_fase5_practice import evaluar_separacion_temporal
from diagnostico_pa_riesgo_practice import analizar_pa_riesgo


def generar_informe(filas):
    # Lista unica para que los tres diagnosticos usen el mismo universo.
    registros = list(filas)
    consistencia = evaluar_filas(registros)
    temporal = evaluar_separacion_temporal(registros)
    pa = analizar_pa_riesgo(registros)

    # Los diagnosticos tienen criterios de exclusion equivalentes en el
    # historial canonico. Si divergen, no emitir comparaciones concluyentes.
    total_consistencia = consistencia["total_filas_validas_win_loss"]
    total_pa = sum(g["n"] for g in pa["grupos"])
    universos_coinciden = total_consistencia == total_pa
    candidatos = [
        e for e in temporal.get("experimentos", [])
        if e.get("seleccion_train")
    ]
    test_suficientes = [
        e for e in candidatos if e.get("test_muestra_suficiente")
    ]
    aprobados_test = [
        e for e in test_suficientes if e.get("test_cumple_objetivo")
    ]
    return {
        "modo": "REPORTE_PRACTICE_SOLO_LECTURA",
        "objetivo_winrate_pct": 60.0,
        "ventana": 20,
        "universos_diagnosticos_coinciden": universos_coinciden,
        "operaciones_evaluables": total_consistencia,
        "winrate_global_pct": consistencia["global"]["winrate_pct"],
        "pnl_neto_global": consistencia["global"]["neto"],
        "bloques_completos": consistencia["bloques_completos"],
        "bloques_bajo_objetivo": consistencia["bloques_completos_bajo_objetivo"],
        "ventanas_moviles": consistencia["ventanas_moviles"],
        "ventanas_moviles_bajo_objetivo": consistencia["ventanas_moviles_bajo_objetivo"],
        "consistencia_20_observada": consistencia["consistencia_20_observada"],
        "dias": consistencia["dias"],
        "diagnostico_temporal": temporal.get("estado"),
        "estrategias_con_muestra_train_y_objetivo": len(candidatos),
        "estrategias_con_muestra_test": len(test_suficientes),
        "estrategias_con_test_favorable": len(aprobados_test),
        "familias_candidatas_solo_hipotesis": [
            e["estrategia"] for e in candidatos
        ],
        "pa_riesgo": pa["grupos"],
        "limitaciones": [
            "Datos retrospectivos; no equivalen a validacion prospectiva",
            "Los resultados no son prueba causal de una estrategia o filtro",
            "El diagnostico temporal usa el ultimo dia como test; no constituye validacion independiente repetida",
            "Un objetivo del 60 por ciento no garantiza ganancias futuras",
        ],
        "evidencia_suficiente_para_cambio_operativo": False,
        "cambios_operativos_autorizados": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        informe = generar_informe(csv.DictReader(f))
    print(json.dumps(informe, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
