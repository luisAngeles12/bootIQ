"""Validacion prospectiva CONGELADA de hipotesis formuladas el 2026-11-03.

No altera estrategias, reglas de seguridad, memoria ni ordenes.
El corte se fijo como MAX(vela_senal_from) de las 64 candidatas usadas
para formular las hipotesis. Los registros de ese momento NO son OOS.
"""
import argparse
import json

from experimento_alineacion_sombra_practice import leer_csv, comparar

# Congelado despues de inspeccionar 64 candidatas del 2026-11-03.
CORTE_SENAL_UTC = 1793732820
HIPOTESIS_CONGELADAS = (
    "BASE_SIN_FILTRO_NUEVO",
    "SOLO_A_FAVOR_TENDENCIA",
    "A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA",
)
BASELINE_DESARROLLO = {
    "BASE_SIN_FILTRO_NUEVO": (23, 22),
    "SOLO_A_FAVOR_TENDENCIA": (20, 11),
    "A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA": (17, 7),
}


def validar_prospectivamente(filas):
    antiguas = []
    futuras = []
    invalidas = 0
    for fila in filas:
        try:
            t = int(fila["vela_senal_from"])
        except (KeyError, TypeError, ValueError):
            invalidas += 1
            continue
        if t <= CORTE_SENAL_UTC:
            antiguas.append(fila)
        else:
            futuras.append(fila)

    evaluacion = comparar(futuras)
    escenarios = {k: evaluacion["escenarios"][k] for k in HIPOTESIS_CONGELADAS}
    base = escenarios["BASE_SIN_FILTRO_NUEVO"]
    alternativa = escenarios["A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA"]
    diferencias = {}
    for nombre in HIPOTESIS_CONGELADAS:
        actual = escenarios[nombre]["winrate_proxy_pct"]
        inicial_wins, inicial_losses = BASELINE_DESARROLLO[nombre]
        inicial = round(100 * inicial_wins / (inicial_wins + inicial_losses), 2)
        diferencias[nombre] = {
            "desarrollo_pct": inicial,
            "futuro_pct": actual,
            "cambio_puntos": round(actual - inicial, 2) if actual is not None else None,
        }

    # Nunca convierte resultados sombra en rendimiento real, aunque
    # aparezca una mejora. Sin fill/payout no hay validacion economica.
    mejora_exploratoria = (
        alternativa["winrate_proxy_pct"] is not None
        and base["winrate_proxy_pct"] is not None
        and alternativa["winrate_proxy_pct"] > base["winrate_proxy_pct"]
    )
    return {
        "tipo": "VALIDACION_PROSPECTIVA_SOMBRA_NO_OPERATIVA",
        "corte_senal_utc_inclusivo": CORTE_SENAL_UTC,
        "registros_desarrollo_excluidos": len(antiguas),
        "registros_posteriores_al_corte": len(futuras),
        "registros_con_fecha_invalida": invalidas,
        "escenarios_congelados": escenarios,
        "deriva_respecto_desarrollo": diferencias,
        "mejora_sombra_exploratoria": mejora_exploratoria,
        "minutos_posteriores_distintos": base["minutos_distintos"],
        "dias_posteriores_distintos": base["sesiones_utc_dias"],
        "pendiente": (
            "SIN_MUESTRA_POSTERIOR" if base["oportunidades"] == 0
            else "EVIDENCIA_SOMBRA_NO_EQUIVALE_A_EJECUCIONES"
        ),
        "validacion_winrate_60": "NO_VALIDADA",
        "validacion_economica": "SIN_FILL_NI_PAYOUT_PREENTRADA",
        "cerebro_modificado": False,
        "ordenes_autorizadas": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archivo", default="auditoria_candidatas_sombra_practice.csv"
    )
    args = parser.parse_args()
    print(json.dumps(
        validar_prospectivamente(leer_csv(args.archivo)),
        ensure_ascii=False, indent=2
    ))
