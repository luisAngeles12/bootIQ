"""Validacion prospectiva congelada: CHOCH bajista + absorcion compradora.

Solo lectura. Nunca genera ordenes, ni cambia estrategia o memoria.
El corte y las definiciones se cargan del registro congelado versionado.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from auditoria_candidatas_sombra_practice import _id as calcular_id
from experimento_alineacion_sombra_practice import depurar, leer_csv
from trazabilidad_rondas_sombra import auditar_intentos

REGISTRO = Path("hipotesis_choch_absorcion_congelada_20261106.json")
ARCHIVO = "auditoria_candidatas_sombra_practice.csv"
LEDGER = "trazabilidad_rondas_sombra.jsonl"
TIPO = "HIPOTESIS_PROSPECTIVA_CONGELADA_SOLO_LECTURA"
CALIDAD_TIEMPO = "HIPOTETICO_VELA_COMPLETA_SIN_FILL"


def leer_registro(ruta=REGISTRO):
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if (d.get("tipo") != TIPO or d.get("cuenta") != "PRACTICE"
            or d.get("autoriza_operaciones") is not False
            or d.get("grupo_objetivo") != "CHOCH bajista"
            or d.get("direccion") != "put"
            or d.get("accion_precio") != "ABSORCION_COMPRADORA"):
        raise ValueError("HIPOTESIS_CONGELADA_INCOMPATIBLE")
    corte = datetime.fromisoformat(d["corte_utc_inclusivo"])
    congelada = datetime.fromisoformat(d["congelada_utc"])
    if (corte.tzinfo is None or congelada.tzinfo is None
            or corte.utcoffset().total_seconds() != 0
            or congelada >= corte
            or int(corte.timestamp()) % 60):
        raise ValueError("CORTE_CONGELADO_INVALIDO")
    return d


def evaluar(filas, ledger, registro):
    corte = int(datetime.fromisoformat(registro["corte_utc_inclusivo"]).timestamp())
    ids = Counter(f.get("id", "") for f in filas)
    estados = ledger.get("ids_por_estado", {})
    excluidas = Counter()
    elegibles = []
    for f in filas:
        try:
            ts = int(f["vela_senal_from"])
        except (KeyError, ValueError, TypeError):
            excluidas["FECHA_INVALIDA"] += 1
            continue
        if ts < corte:
            excluidas["ANTES_DEL_CORTE"] += 1
            continue
        candidato = f.get("id", "")
        if not candidato or ids[candidato] != 1:
            excluidas["ID_FALTANTE_O_DUPLICADO"] += 1
            continue
        if ts <= 0 or ts % 60:
            excluidas["FECHA_INVALIDA"] += 1
            continue
        if candidato != calcular_id(
            f.get("activo", ""), f.get("patron", ""),
            f.get("direccion", ""), ts
        ):
            excluidas["IDENTIDAD_INVALIDA"] += 1
            continue
        if estados.get(candidato) != "ANALISIS_VALIDADO":
            excluidas["RONDA_NO_VALIDADA"] += 1
            continue
        elegibles.append(f)

    # Una candidata excluida invalida el ACTIVO+MINUTO completo,
    # incluso si otra candidata del evento era individualmente valida.
    elegibles_ids = {id(f) for f in elegibles}
    cuarentena = set()
    for f in filas:
        try:
            ts = int(f.get("vela_senal_from", ""))
        except (ValueError, TypeError):
            continue
        activo = f.get("activo", "")
        if ts < corte or ts <= 0 or ts % 60 or not activo:
            continue
        if (id(f) not in elegibles_ids or f.get("decision") != "NO_OPERAR"
                or f.get("calidad_mercado") not in {"NORMAL", "LIMPIO"}
                or f.get("calidad_tiempo") != CALIDAD_TIEMPO
                or f.get("resultado_hipotetico") not in {"WIN", "LOSS", "EMPATE"}):
            cuarentena.add((activo, ts))
    limpios = [f for f in elegibles
               if (f.get("activo"), int(f["vela_senal_from"])) not in cuarentena]
    excluidas["EVENTO_EN_CUARENTENA"] = len(elegibles) - len(limpios)
    eventos, descartes = depurar(limpios)
    comparables = [e for e in eventos
                   if e["direccion"] == registro["direccion"]
                   and e["accion_precio"] == registro["accion_precio"]
                   and len(e["patrones"]) == 1]
    objetivo = [e for e in comparables if e["patrones"] == [registro["grupo_objetivo"]]]
    otros = [e for e in comparables if e["patrones"] != [registro["grupo_objetivo"]]]

    def resumen(grupo):
        c = Counter(e["resultado"] for e in grupo)
        decididos = c["WIN"] + c["LOSS"]
        return {
            "eventos": len(grupo), "win": c["WIN"], "loss": c["LOSS"],
            "empate": c["EMPATE"],
            "winrate_proxy_pct": round(100 * c["WIN"] / decididos, 2)
            if decididos else None,
            "minutos_distintos": len({e["minuto"] for e in grupo}),
            "dias_utc": len({e["minuto"] // 86400 for e in grupo}),
            "activos_distintos": len({e["activo"] for e in grupo}),
        }

    a, b = resumen(objetivo), resumen(otros)
    diferencia = (round(a["winrate_proxy_pct"] - b["winrate_proxy_pct"], 2)
                  if a["winrate_proxy_pct"] is not None
                  and b["winrate_proxy_pct"] is not None else None)
    return {
        "tipo": TIPO,
        "corte_utc_inclusivo": registro["corte_utc_inclusivo"],
        "congelada_utc": registro["congelada_utc"],
        "registros_csv": len(filas),
        "candidatas_post_corte_con_ronda_validada": len(elegibles),
        "exclusiones": dict(sorted(excluidas.items())),
        "descartes_depuracion": descartes,
        "objetivo_choch_bajista": a,
        "comparador_otros_put": b,
        "diferencia_choch_menos_otros_pp": diferencia,
        "evidencia_para_conclusion": "PENDIENTE_VALIDACION_INDEPENDIENTE",
        "winrate_60_validado": False,
        "operaciones_autorizadas": False,
        "limitaciones": [
            "La hipotesis se descubrio usando datos anteriores al corte.",
            "Resultados sombra de vela completa, sin fill ni payout broker.",
            "Eventos cercanos en tiempo o activo pueden estar correlacionados.",
            "Ninguna diferencia observada autoriza cambiar estrategia.",
        ],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--archivo", default=ARCHIVO)
    p.add_argument("--ledger", default=LEDGER)
    p.add_argument("--registro", default=str(REGISTRO))
    a = p.parse_args()
    try:
        filas = leer_csv(a.archivo)
    except FileNotFoundError:
        filas = []
    print(json.dumps(evaluar(filas, auditar_intentos(a.ledger),
                             leer_registro(a.registro)),
                     indent=2, ensure_ascii=False))
