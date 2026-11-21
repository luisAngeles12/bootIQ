"""Audita resultados de velas de candidatas bloqueadas sin autorizar trading.

Los WIN/LOSS son hipoteticos: no contienen fill, payout ni PnL del broker.
"""
import argparse
import csv
import json
import math
from collections import Counter
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ESTADO_VALIDO = "HIPOTETICO_VELA_COMPLETA_SIN_FILL"


def _resumen(eventos):
    n = len(eventos)
    wins = sum(x["resultado"] == "WIN" for x in eventos)
    # Wilson 95%: un 60% observado con poca muestra no implica 60% estable.
    p = wins / n if n else 0.0
    z = 1.96
    den = 1 + z * z / n if n else 1
    inferior = ((p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den) if n else None
    return {
        "wilson_inferior_95_pct": round(100 * inferior, 2) if inferior is not None else None,
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "winrate_pct": round(wins * 100 / n, 2) if n else None,
        "cumple_60_pct": n > 0 and wins * 5 >= n * 3,
    }


def evaluar(filas):
    """Devuelve cobertura y metricas, sin promover reglas ni atribuir PnL."""
    filas = list(filas)
    ocurrencias = Counter(str(f.get("id") or "").strip() for f in filas
                          if str(f.get("decision") or "").strip().upper() == "NO_OPERAR")
    validos = []
    descartes = defaultdict(int)
    pendientes = 0
    for fila in filas:
        if str(fila.get("decision") or "").strip().upper() != "NO_OPERAR":
            descartes["NO_RECHAZADA"] += 1
            continue
        clave = str(fila.get("id") or "").strip()
        if not clave or ocurrencias[clave] > 1:
            descartes["ID_DUPLICADO_O_VACIO"] += 1
            continue
        resultado = str(fila.get("resultado_hipotetico") or "").strip().upper()
        if not resultado:
            pendientes += 1
            continue
        if resultado == "EMPATE":
            descartes["EMPATE"] += 1
            continue
        if resultado not in ("WIN", "LOSS") or fila.get("calidad_tiempo") != ESTADO_VALIDO:
            descartes["CALIDAD_O_RESULTADO_INVALIDO"] += 1
            continue
        try:
            ts = int(str(fila.get("vela_entrada_from") or ""))
            if ts <= 0:
                raise ValueError("TIMESTAMP")
            fecha = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            descartes["FECHA_INVALIDA"] += 1
            continue
        direccion = str(fila.get("direccion") or "").strip().lower()
        if direccion not in ("call", "put"):
            descartes["DIRECCION_INVALIDA"] += 1
            continue
        validos.append({"id": clave, "ts": ts, "dia_utc": fecha,
                        "direccion": direccion, "resultado": resultado})
    validos.sort(key=lambda x: (x["ts"], x["id"]))
    dias = defaultdict(list)
    direcciones = defaultdict(list)
    for x in validos:
        dias[x["dia_utc"]].append(x)
        direcciones[x["direccion"]].append(x)
    bloques = []
    for inicio in range(0, len(validos), 20):
        items = validos[inicio:inicio + 20]
        if len(items) != 20:
            break
        bloques.append({"bloque": len(bloques) + 1, **_resumen(items)})
    # Ademas del total cronologico, separar bloques por dia evita mezclar
    # jornadas para crear una falsa apariencia de 60% consistente.
    bloques_por_dia = []
    dias_con_bloque = set()
    for dia, registros in sorted(dias.items()):
        for inicio in range(0, len(registros), 20):
            grupo = registros[inicio:inicio + 20]
            if len(grupo) < 20:
                continue
            dias_con_bloque.add(dia)
            bloques_por_dia.append({
                "dia_utc": dia,
                "bloque_dia": inicio // 20 + 1,
                **_resumen(grupo),
            })
    # 12/20 cumple. Los bloques siguen siendo simulaciones sin ejecucion
    # broker y NO validan ventaja OOS, aunque todos sean favorables.
    jornadas = len(dias)
    evidencia_minima = len(bloques) >= 3 and jornadas >= 5
    # No declarar constancia si solo tres dias tienen un bloque completo:
    # las jornadas cortas tambien son evidencia, no deben desaparecer.
    cobertura_multijornada = len(dias_con_bloque) == jornadas and jornadas >= 5
    resumen_jornadas = [
        {"dia_utc": dia, **_resumen(x)}
        for dia, x in sorted(dias.items())
    ]
    return {
        "tipo": "AUDITORIA_HIPOTETICA_SOMBRA_PRACTICE",
        "filas": len(filas), "resueltas_validas": len(validos),
        "pendientes_sin_resultado": pendientes,
        "descartes": dict(sorted(descartes.items())),
        "global": _resumen(validos),
        "por_dia_utc": resumen_jornadas,
        "por_direccion": {d: _resumen(x) for d, x in sorted(direcciones.items())},
        "bloques_completos_20": bloques,
        "tipo_bloque": "HIPOTETICO_CRONOLOGICO_NO_SESION_BROKER",
        "jornadas_utc": jornadas,
        "bloques_completos_20_por_dia_utc": bloques_por_dia,
        "jornadas_con_bloque_20": len(dias_con_bloque),
        "cobertura_multijornada": cobertura_multijornada,
        "evidencia_minima_constancia": evidencia_minima and cobertura_multijornada,
        "constancia_sombra_60_observada": (
            evidencia_minima and cobertura_multijornada
            and all(x["cumple_60_pct"] for x in bloques)
            and all(x["cumple_60_pct"] for x in bloques_por_dia)
            and all(x["cumple_60_pct"] for x in resumen_jornadas)
        ),
        "bloques_20_cumplen_60": sum(x["cumple_60_pct"] for x in bloques),
        "todos_bloques_20_cumplen_60": bool(bloques) and all(x["cumple_60_pct"] for x in bloques),
        "pnl_broker": None,
        "rentabilidad_demostrada": False,
        "autoriza_operaciones": False,
        "nota": "Aciertos hipoteticos de vela completa. Bloques no representan sesiones ni validacion OOS; sin fill, payout ni PnL.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", nargs="?", default="auditoria_candidatas_sombra_practice.csv")
    args = p.parse_args()
    with Path(args.csv).open(encoding="utf-8-sig", newline="") as f:
        resultado = evaluar(csv.DictReader(f))
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
