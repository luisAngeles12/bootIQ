"""Experimento POST-HOC de alineacion: solo lectura, no modifica el bot.

Las politicas se comparan en la MISMA muestra, no son validacion OOS.
No sustituye fills, tiempos de ejecucion ni pagos reales.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

RESULTADOS = {"WIN", "LOSS", "EMPATE"}
CALIDAD = {"NORMAL", "LIMPIO"}
TIEMPO = "HIPOTETICO_VELA_COMPLETA_SIN_FILL"


def leer_csv(ruta):
    with Path(ruta).open("r", newline="", encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))
    necesarios = {
        "activo", "patron", "direccion", "vela_senal_from",
        "resultado_hipotetico", "calidad_tiempo", "calidad_mercado",
        "decision", "estado_tendencia", "accion_precio",
    }
    if filas and not necesarios.issubset(filas[0]):
        raise ValueError("CSV_SOMBRA_SIN_COLUMNAS_REQUERIDAS")
    return filas


def alinear(direccion, tendencia):
    direccion = str(direccion).lower()
    tendencia = str(tendencia).upper()
    if direccion not in {"call", "put"}:
        return "NO_EVALUABLE"
    if tendencia.startswith("ALCISTA_"):
        return "A_FAVOR" if direccion == "call" else "EN_CONTRA"
    if tendencia.startswith("BAJISTA_"):
        return "A_FAVOR" if direccion == "put" else "EN_CONTRA"
    return "INDEFINIDA"


def depurar(filas):
    """Deduplicar activo/minuto, excluir contradicciones y no usar pendientes."""
    grupos = defaultdict(list)
    descartes = Counter()
    for fila in filas:
        if fila.get("decision") != "NO_OPERAR":
            descartes["NO_RECHAZADA"] += 1
            continue
        if fila.get("calidad_mercado") not in CALIDAD:
            descartes["MERCADO_NO_APTO"] += 1
            continue
        if (fila.get("resultado_hipotetico") not in RESULTADOS
                or fila.get("calidad_tiempo") != TIEMPO):
            descartes["SIN_RESULTADO_TRAZABLE"] += 1
            continue
        try:
            minuto = int(fila["vela_senal_from"])
        except (KeyError, TypeError, ValueError):
            descartes["TIEMPO_INVALIDO"] += 1
            continue
        if minuto <= 0 or minuto % 60 or not fila.get("activo"):
            descartes["TIEMPO_INVALIDO"] += 1
            continue
        grupos[(fila["activo"], minuto)].append(fila)
    salida = []
    for (activo, minuto), candidatas in sorted(grupos.items()):
        direcciones = {f["direccion"].lower() for f in candidatas}
        resultados = {f["resultado_hipotetico"] for f in candidatas}
        tendencias = {f["estado_tendencia"] for f in candidatas}
        acciones = {f["accion_precio"] for f in candidatas}
        if (len(direcciones) != 1 or len(resultados) != 1
                or len(tendencias) != 1 or len(acciones) != 1):
            descartes["CONFLICTO_ACTIVO_MINUTO"] += 1
            continue
        if not direcciones.issubset({"call", "put"}):
            descartes["DIRECCION_INVALIDA"] += 1
            continue
        fila = candidatas[0]
        salida.append({
            "activo": activo, "minuto": minuto,
            "direccion": fila["direccion"].lower(),
            "tendencia": fila["estado_tendencia"],
            "accion_precio": fila["accion_precio"],
            "resultado": fila["resultado_hipotetico"],
            "alineacion": alinear(fila["direccion"], fila["estado_tendencia"]),
            "patrones": sorted(set(f["patron"] for f in candidatas)),
            "candidatas_agrupadas": len(candidatas),
        })
    return salida, dict(descartes)


def estadistica(eventos):
    total = len(eventos)
    wins = sum(e["resultado"] == "WIN" for e in eventos)
    losses = sum(e["resultado"] == "LOSS" for e in eventos)
    empates = sum(e["resultado"] == "EMPATE" for e in eventos)
    minutos = len({e["minuto"] for e in eventos})
    return {
        "oportunidades": total, "wins": wins, "losses": losses,
        "empates": empates,
        "winrate_proxy_pct": round(wins / total * 100, 2) if total else None,
        "minutos_distintos": minutos,
        "sesiones_utc_dias": len({e["minuto"] // 86400 for e in eventos}),
        "simultaneas_otro_activo": total - minutos,
        "validacion_60": "NO_VALIDADA",
        "ordenes_autorizadas": False,
    }


def comparar(filas):
    oportunidades, descartes = depurar(filas)
    escenarios = {
        "BASE_SIN_FILTRO_NUEVO": oportunidades,
        "SOLO_A_FAVOR_TENDENCIA": [
            e for e in oportunidades if e["alineacion"] == "A_FAVOR"
        ],
        "A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA": [
            e for e in oportunidades
            if e["alineacion"] == "A_FAVOR"
            and e["accion_precio"] != "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
        ],
        "EN_CONTRA_TENDENCIA": [
            e for e in oportunidades if e["alineacion"] == "EN_CONTRA"
        ],
    }
    return {
        "tipo": "EXPERIMENTO_POST_HOC_NO_OPERATIVO",
        "advertencia": (
            "Politicas examinadas con los mismos datos que motivaron su diseno; "
            "no representan mejora demostrada ni autorizan operacion."
        ),
        "datos_entrada": len(filas),
        "descartes": descartes,
        "escenarios": {k: estadistica(v) for k, v in escenarios.items()},
        "por_alineacion": {
            k: estadistica([e for e in oportunidades if e["alineacion"] == k])
            for k in ("A_FAVOR", "EN_CONTRA", "INDEFINIDA")
        },
        "observaciones_temporales_no_independientes": True,
        "requiere": [
            "validacion prospectiva con politicas congeladas",
            "verificacion de segundo de entrada, payout y fill PRACTICE",
            "muestras de varios dias y mercados",
        ],
        "ordenes_autorizadas": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archivo", default="auditoria_candidatas_sombra_practice.csv"
    )
    args = parser.parse_args()
    print(json.dumps(comparar(leer_csv(args.archivo)),
                     indent=2, ensure_ascii=False))
