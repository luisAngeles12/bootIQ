"""Diagnostico descriptivo de la muestra posterior al corte congelado.

Solo lectura. Los porcentajes no son prueba causal, ni validacion de
trading, ni autorizacion para cambiar el Cerebro.
"""
import argparse
import json
from collections import Counter, defaultdict

from experimento_alineacion_sombra_practice import leer_csv, depurar, estadistica
from validacion_prospectiva_alineacion import CORTE_SENAL_UTC

CATEGORIAS = ("alineacion", "direccion", "tendencia", "accion_precio", "activo")


def _segmentos(oportunidades, campo):
    por_valor = defaultdict(list)
    for oportunidad in oportunidades:
        por_valor[oportunidad[campo]].append(oportunidad)
    return {
        clave: estadistica(eventos)
        for clave, eventos in sorted(por_valor.items())
    }


def _patrones_sin_ambiguedad(oportunidades):
    por_patron = defaultdict(list)
    multis = 0
    for oportunidad in oportunidades:
        patrones = oportunidad["patrones"]
        if len(patrones) != 1:
            multis += 1
            continue
        por_patron[patrones[0]].append(oportunidad)
    return {
        "atribucion_excluida_multi_patron": multis,
        "resultados": {
            clave: estadistica(eventos)
            for clave, eventos in sorted(por_patron.items())
        },
    }


def diagnosticar(filas):
    antes = []
    despues = []
    fechas_invalidas = 0
    for fila in filas:
        try:
            instante = int(fila["vela_senal_from"])
        except (KeyError, TypeError, ValueError):
            fechas_invalidas += 1
            continue
        (antes if instante <= CORTE_SENAL_UTC else despues).append(fila)

    oportunidades, descartes = depurar(despues)
    estados = Counter(
        f.get("resultado_hipotetico") or "PENDIENTE"
        for f in despues
    )
    salida = {
        "tipo": "DIAGNOSTICO_DESCRIPTIVO_POST_CORTE_NO_OPERATIVO",
        "corte_senal_utc_inclusivo": CORTE_SENAL_UTC,
        "registros_totales": len(filas),
        "registros_desarrollo_excluidos": len(antes),
        "registros_posteriores": len(despues),
        "fechas_invalidas": fechas_invalidas,
        "estados_filas_posteriores": dict(sorted(estados.items())),
        "descartes": descartes,
        "resumen": estadistica(oportunidades),
        "por_patron_exclusivo": _patrones_sin_ambiguedad(oportunidades),
        "cruces": {campo: _segmentos(oportunidades, campo)
                   for campo in CATEGORIAS},
        "comparacion_pareada_por_minuto": _comparacion_por_minuto(oportunidades),
        "advertencias": [
            "Muestra posterior al corte, pero originada en el mismo dia.",
            "Un activo/minuto es una oportunidad; distintos activos pueden estar correlacionados.",
            "La atribucion por patron exige un unico patron dentro del activo/minuto.",
            "Sin precio real de entrada, fill, payout ni expiracion verificada.",
            "No inferir causa, certeza estadistica, permiso de operar ni mejora validada.",
        ],
        "validacion_60": "NO_VALIDADA",
        "ordenes_autorizadas": False,
    }
    return salida


def _comparacion_por_minuto(oportunidades):
    """Comparar CALL/PUT por minuto sin tratar activos como independientes."""
    por_minuto = defaultdict(list)
    for evento in oportunidades:
        por_minuto[evento["minuto"]].append(evento)
    return {
        "minutos_observados": len(por_minuto),
        "minutos_con_multiples_activos": sum(
            len(grupo) > 1 for grupo in por_minuto.values()
        ),
        "minutos_con_resultados_mixtos": sum(
            len({evento["resultado"] for evento in grupo}) > 1
            for grupo in por_minuto.values()
        ),
        "minutos_con_ambas_direcciones": sum(
            len({evento["direccion"] for evento in grupo}) > 1
            for grupo in por_minuto.values()
        ),
        "nota": "Agrupacion descriptiva; sin estimacion de independencia entre activos",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default="auditoria_candidatas_sombra_practice.csv")
    args = parser.parse_args()
    print(json.dumps(diagnosticar(leer_csv(args.archivo)),
                     ensure_ascii=False, indent=2))
