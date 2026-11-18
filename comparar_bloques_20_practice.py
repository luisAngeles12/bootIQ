"""Compara bloques completos de 20 PRACTICE, sin ejecutar operaciones.

Lee los JSON finales generados por control_bloques_20_practice.py.
Excluye bloques incompletos, informes duplicados e identidades repetidas.
Nunca activa estrategias, memoria productiva ni trading REAL.
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path


def _numero(valor):
    if isinstance(valor, bool):
        return None
    try:
        n = float(valor)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def _evaluar_bloque(reporte):
    if not isinstance(reporte, dict) or reporte.get("estado") != "BLOQUE_20_CERRADO":
        return None, "NO_CERRADO"
    if reporte.get("modo") != "PRACTICE":
        return None, "NO_PRACTICE"
    operaciones = reporte.get("operaciones")
    if not isinstance(operaciones, list) or len(operaciones) != 20:
        return None, "CANTIDAD_INVALIDA"
    ids = []
    pnls = []
    for fila in operaciones:
        if not isinstance(fila, dict):
            return None, "OPERACION_INVALIDA"
        oid = str(fila.get("order_id") or "").strip()
        if not oid:
            return None, "ID_INVALIDO"
        if str(fila.get("estado") or "").strip().upper() != "CERRADA":
            return None, "NO_CERRADA"
        if str(fila.get("modo_cuenta_configurado") or "").strip().upper() != "PRACTICE":
            return None, "OPERACION_NO_PRACTICE"
        if str(fila.get("estado_operacion") or "").strip().upper() not in (
            "OPERADA_DIRECTA", "OPERADA_PROTOCOLO"
        ):
            return None, "OPERACION_NO_EJECUTADA"
        pnl = _numero(fila.get("pnl_numerico"))
        if pnl is None:
            return None, "PNL_INVALIDO"
        ids.append(oid)
        pnls.append(pnl)
    if len(set(ids)) != 20:
        return None, "ID_DUPLICADO_INTERNO"
    resumen = reporte.get("resultado")
    if not isinstance(resumen, dict):
        return None, "RESUMEN_INVALIDO"
    wins = sum(x > 0 for x in pnls)
    losses = sum(x < 0 for x in pnls)
    empates = sum(x == 0 for x in pnls)
    neto = round(sum(pnls), 2)
    wr = round(100 * wins / (wins + losses), 2) if wins + losses else None
    if (resumen.get("total") != 20 or resumen.get("ganadas") != wins
            or resumen.get("perdidas") != losses or resumen.get("empates") != empates
            or _numero(resumen.get("neto")) is None
            or abs(float(resumen["neto"]) - neto) > 0.011
            or _numero(resumen.get("winrate_pct")) != wr):
        return None, "RESUMEN_NO_COINCIDE"
    return {"ids": set(ids), "wins": wins, "losses": losses,
            "empates": empates, "neto": neto, "winrate_pct": wr,
            "objetivo": wr is not None and wr >= 60 and neto > 0}, None


def comparar_bloques(documentos):
    """documentos: pares (ruta, JSON). Ninguna ruta es modificada."""
    candidatos = []
    excluidos = []
    ids_vistos = set()
    sesiones = set()
    for ruta, reporte in sorted(documentos, key=lambda x: str(x[0])):
        bloque, motivo = _evaluar_bloque(reporte)
        if motivo:
            excluidos.append({"archivo": str(ruta), "motivo": motivo})
            continue
        sesion = str(reporte.get("bloque_inicio") or "").strip()
        if not sesion or sesion in sesiones:
            excluidos.append({"archivo": str(ruta), "motivo": "SESION_DUPLICADA_O_VACIA"})
            continue
        if ids_vistos.intersection(bloque["ids"]):
            excluidos.append({"archivo": str(ruta), "motivo": "ORDER_ID_COMPARTIDO_ENTRE_BLOQUES"})
            continue
        ids_vistos.update(bloque["ids"])
        sesiones.add(sesion)
        candidatos.append({
            "archivo": str(ruta), "bloque_inicio": sesion,
            **{k: v for k, v in bloque.items() if k != "ids"}
        })
    candidatos.sort(key=lambda x: x["bloque_inicio"])
    n = len(candidatos)
    wins = sum(x["wins"] for x in candidatos)
    losses = sum(x["losses"] for x in candidatos)
    empates = sum(x["empates"] for x in candidatos)
    neto = round(sum(x["neto"] for x in candidatos), 2)
    n_ordenes = 20*n
    bloques_cumplen = sum(x["objetivo"] for x in candidatos)
    return {
        "modo": "COMPARACION_BLOQUES_20_PRACTICE_SOLO_LECTURA",
        "bloques_validos": n,
        "operaciones": n_ordenes,
        "wins": wins, "losses": losses, "empates": empates,
        "winrate_global_pct": round(100*wins/(wins+losses), 2)
        if wins+losses else None,
        "neto_acumulado": neto,
        "expectativa_por_operacion": round(neto/n_ordenes, 4)
        if n_ordenes else None,
        "bloques_cumplen_60_y_neto": bloques_cumplen,
        "bloques_no_cumplen": n-bloques_cumplen,
        "todos_los_bloques_cumplen": bool(n) and bloques_cumplen == n,
        "bloques": candidatos,
        "excluidos": excluidos,
        "nota": "El rendimiento historico observado no garantiza resultados futuros.",
        "autoriza_operaciones": False,
        "memoria_productiva_modificada": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("carpeta", nargs="?", default="reportes_bloques_20_practice")
    args = ap.parse_args()
    carpeta = Path(args.carpeta)
    documentos = []
    for ruta in sorted(carpeta.glob("bloque20_*.json")):
        try:
            documentos.append((ruta, json.loads(ruta.read_text(encoding="utf-8-sig"))))
        except (OSError, UnicodeError, json.JSONDecodeError):
            documentos.append((ruta, None))
    print(json.dumps(comparar_bloques(documentos), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
