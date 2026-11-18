"""Control de lotes PRACTICE: 20 aperturas confirmadas, esperar sus cierres.

Una sesion de bot.py constituye un bloque nuevo. Al llegar a 20:
- se niegan nuevas ordenes, incluidas las pendientes de protocolo;
- se deja al reconciliador existente cerrar las 20 posiciones;
- se produce informe JSON atomico y se termina la sesion.
No toca memoria V3 ni estrategia, ni permite operar en REAL.
"""
import csv
import json
import math
import os
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

LIMITE = 20
_CUENTA = {"habilitado": False, "ids": [], "vistos": set(),
           "inicio": "", "reportado": False}


def iniciar(modo="PRACTICE", habilitado=True):
    global _CUENTA
    _CUENTA = {
        "habilitado": modo == "PRACTICE" and habilitado is True,
        "ids": [], "vistos": set(),
        "inicio": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "reportado": False,
    }
    return _CUENTA["habilitado"]


def admite_apertura():
    return not _CUENTA["habilitado"] or len(_CUENTA["ids"]) < LIMITE


def registrar_apertura(order_id):
    """Llamar en cuanto IQ confirme buy, ANTES de persistir la fila CSV."""
    if not _CUENTA["habilitado"]:
        return False
    oid = str(order_id or "").strip()
    if not oid:
        raise ValueError("ORDER_ID_IQ_VACIO_BLOQUE20")
    if oid in _CUENTA["vistos"]:
        raise ValueError("ORDER_ID_IQ_DUPLICADO_BLOQUE20")
    if len(_CUENTA["ids"]) >= LIMITE:
        raise RuntimeError("CUPO_BLOQUE20_EXCEDIDO")
    _CUENTA["vistos"].add(oid)
    _CUENTA["ids"].append(oid)
    return len(_CUENTA["ids"]) == LIMITE


def cupo_alcanzado():
    return _CUENTA["habilitado"] and len(_CUENTA["ids"]) >= LIMITE


def progreso():
    return {"abiertas_confirmadas_bloque": len(_CUENTA["ids"]),
            "limite": LIMITE, "cupo_alcanzado": cupo_alcanzado()}


def _numero(valor):
    try:
        valor = float(str(valor).strip())
        return valor if math.isfinite(valor) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _resumen(filas):
    pnls = [f["_pnl"] for f in filas]
    wins = sum(x > 0 for x in pnls)
    losses = sum(x < 0 for x in pnls)
    empates = sum(x == 0 for x in pnls)
    n = len(pnls)
    neto = sum(pnls)
    monto_positivo = sum(x for x in pnls if x > 0)
    monto_negativo = -sum(x for x in pnls if x < 0)
    return {
        "total": n, "ganadas": wins, "perdidas": losses, "empates": empates,
        "winrate_pct": round(100 * wins / (wins + losses), 2)
                       if wins + losses else None,
        "neto": round(neto, 2),
        "expectativa_por_operacion": round(neto / n, 4) if n else None,
        "ganancia_media": round(monto_positivo / wins, 2) if wins else None,
        "perdida_media": round(monto_negativo / losses, 2) if losses else None,
        "profit_factor": round(monto_positivo / monto_negativo, 4)
                         if monto_negativo else None,
        "positivo": neto > 0,
    }


def _segmentar(filas, campo):
    grupos = defaultdict(list)
    for fila in filas:
        valor = str(fila.get(campo) or "").strip() or "SIN_DATO"
        grupos[valor].append(fila)
    return [{"valor": clave, **_resumen(datos)}
            for clave, datos in sorted(grupos.items(),
                key=lambda x: (-sum(f["_pnl"] for f in x[1]), x[0]))]


def _indicadores(fila):
    rsi = _numero(fila.get("rsi"))
    if rsi is None:
        zona_rsi = "SIN_DATO"
    elif rsi < 30:
        zona_rsi = "MENOR_30"
    elif rsi < 40:
        zona_rsi = "30_40"
    elif rsi < 60:
        zona_rsi = "40_60"
    elif rsi <= 70:
        zona_rsi = "60_70"
    else:
        zona_rsi = "MAYOR_70"
    e9, e21 = _numero(fila.get("ema9")), _numero(fila.get("ema21"))
    ema = ("SIN_DATO" if e9 is None or e21 is None else
           "EMA9_SOBRE_EMA21" if e9 > e21 else
           "EMA9_BAJO_EMA21" if e9 < e21 else "EMAS_IGUALES")
    precio = _numero(fila.get("precio_cierre_indicadores"))
    superior = _numero(fila.get("bb_superior"))
    inferior = _numero(fila.get("bb_inferior"))
    media = _numero(fila.get("bb_media"))
    if None in (precio, superior, inferior, media):
        bollinger = "SIN_DATO"
    elif precio > superior:
        bollinger = "ENCIMA_SUPERIOR"
    elif precio < inferior:
        bollinger = "DEBAJO_INFERIOR"
    elif precio >= media:
        bollinger = "ENTRE_MEDIA_Y_SUPERIOR"
    else:
        bollinger = "ENTRE_INFERIOR_Y_MEDIA"
    return zona_rsi, ema, bollinger


def _riesgo_guardado(fila):
    dato = str(fila.get("auditoria_riesgo_compuesto_json") or "").strip()
    if not dato:
        return "SIN_SNAPSHOT"
    try:
        riesgo = json.loads(dato)
    except (TypeError, ValueError):
        return "SNAPSHOT_INVALIDO"
    if not isinstance(riesgo, dict):
        return "SNAPSHOT_INVALIDO"
    return str(riesgo.get("riesgo_nivel") or "SIN_NIVEL").strip().upper()


def _vela_guardada(fila):
    apertura = _numero(fila.get("precio_senal_open"))
    cierre = _numero(fila.get("precio_senal_close"))
    high = _numero(fila.get("precio_senal_high"))
    low = _numero(fila.get("precio_senal_low"))
    if None in (apertura, cierre, high, low):
        return "SIN_SNAPSHOT"
    rango = high - low
    if rango <= 0 or high < max(apertura, cierre) or low > min(apertura, cierre):
        return "OHLC_INVALIDO"
    proporcion = abs(cierre - apertura) / rango
    if proporcion <= 0.10:
        return "CUERPO_PEQUENO"
    tipo = "ALCISTA" if cierre > apertura else "BAJISTA"
    return tipo + ("_CUERPO_FUERTE" if proporcion >= 0.60 else "_CUERPO_MODERADO")


def preparar_informe(filas, ids, inicio):
    """Falla sin emitir resultado conclusivo si falta alguna de las 20 órdenes."""
    ids = [str(x) for x in ids]
    if len(ids) != LIMITE or len(set(ids)) != LIMITE:
        raise ValueError("BLOQUE_SIN_20_ORDENES_UNICAS")
    por_id = defaultdict(list)
    for fila in filas:
        oid = str(fila.get("order_id") or "").strip()
        if oid in ids:
            por_id[oid].append(fila)
    evaluadas = []
    errores = []
    for oid in ids:
        matches = por_id[oid]
        if len(matches) != 1:
            errores.append({"order_id": oid, "causa": "AUSENTE_O_DUPLICADA",
                            "filas": len(matches)})
            continue
        fila = dict(matches[0])
        if str(fila.get("estado") or "").strip().upper() != "CERRADA":
            errores.append({"order_id": oid, "causa": "SIN_CIERRE"})
            continue
        if str(fila.get("modo_cuenta_configurado") or "").strip().upper() != "PRACTICE":
            errores.append({"order_id": oid, "causa": "NO_PRACTICE"})
            continue
        if str(fila.get("estado_operacion") or "").strip().upper() not in (
                "OPERADA_DIRECTA", "OPERADA_PROTOCOLO"):
            errores.append({"order_id": oid, "causa": "ESTADO_OPERACION_INVALIDO"})
            continue
        pnl = _numero(fila.get("resultado"))
        if pnl is None:
            errores.append({"order_id": oid, "causa": "PNL_INVALIDO"})
            continue
        fila["_pnl"] = pnl
        fila["_riesgo_nivel"] = _riesgo_guardado(fila)
        fila["_vela_senal"] = _vela_guardada(fila)
        zona, ema, bb = _indicadores(fila)
        fila["_zona_rsi"], fila["_ema_relativa"], fila["_bb_ubicacion"] = zona, ema, bb
        evaluadas.append(fila)
    if errores:
        return {"estado": "INFORME_INCOMPLETO_NO_CONCLUYENTE",
                "bloque_inicio": inicio, "esperadas": LIMITE,
                "cerradas_validas": len(evaluadas), "errores": errores,
                "reanudacion_automatica": False}
    total = _resumen(evaluadas)
    neto_acumulado = 0.0
    trayectoria = []
    for oid, fila in zip(ids, evaluadas):
        neto_acumulado += fila["_pnl"]
        trayectoria.append({"order_id": oid, "resultado": fila["_pnl"],
                            "neto_acumulado": round(neto_acumulado, 2)})
    segmentos = {
        "estrategias": "patron", "activos": "activo",
        "mercados": "tipo_mercado", "calidad_mercado": "calidad_mercado",
        "regimen_mercado": "regimen_mercado",
        "tendencias": "estado_tendencia",
        "price_action": "pa_tipo", "accion_precio": "accion_precio",
        "setup": "tipo_setup",
        "autoridad": "origen_autoridad",
        "protocolo": "protocolo_sugerido",
        "direccion": "direccion",
        "rsi_zona": "_zona_rsi", "ema_alineacion": "_ema_relativa",
        "bollinger_ubicacion": "_bb_ubicacion",
        "riesgo_compuesto": "_riesgo_nivel",
        "vela_senal_estructura": "_vela_senal",
        "riesgos_base": "riesgos_base",
        "core4_reglas": "core4_reglas",
        "nivel_consenso": "nivel_consenso",
    }
    return {
        "estado": "BLOQUE_20_CERRADO",
        "modo": "PRACTICE",
        "bloque_inicio": inicio,
        "completado_utc": datetime.now(timezone.utc).isoformat(),
        "resultado": total,
        "objetivo_60_pct_y_neto": (
            total["winrate_pct"] is not None
            and total["winrate_pct"] >= 60 and total["neto"] > 0
        ),
        "analisis": {nombre: _segmentar(evaluadas, campo)
                     for nombre, campo in segmentos.items()},
        # Copiar cada snapshot original completo: RSI, EMA, Bollinger,
        # velas, protocolos, fuentes, mercado, autoridad y riesgos.
        # Nunca recalcular con informacion posterior al cierre.
        "operaciones": [
            {
                **{clave: valor for clave, valor in fila.items()
                   if not clave.startswith("_")},
                "pnl_numerico": fila["_pnl"],
                "rsi_zona": fila["_zona_rsi"],
                "ema_alineacion": fila["_ema_relativa"],
                "bollinger_ubicacion": fila["_bb_ubicacion"],
                "riesgo_compuesto": fila["_riesgo_nivel"],
                "vela_senal_estructura": fila["_vela_senal"],
            }
            for fila in evaluadas
        ],
        "trayectoria": trayectoria,
        "advertencias": [
            "20 operaciones no demuestran una ventaja estadistica estable.",
            "Los segmentos con pocos casos son descriptivos, no recomendaciones.",
            "Si faltan snapshots de indicadores se informa SIN_DATO.",
            "La memoria productiva y las reglas del Cerebro no fueron modificadas.",
        ],
        "reanudacion_automatica": False,
    }


def _guardar_atomico(reporte, carpeta):
    destino = Path(carpeta)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / ("bloque20_" + _CUENTA["inicio"] + ".json")
    if ruta.exists():
        raise FileExistsError("REPORTE_BLOQUE_EXISTENTE")
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=destino, prefix=".bloque20_", suffix=".tmp",
            encoding="utf-8", delete=False
        ) as file:
            temporal = Path(file.name)
            json.dump(reporte, file, ensure_ascii=False, indent=2, default=str)
            file.flush()
            os.fsync(file.fileno())
        os.link(temporal, ruta)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return str(ruta)


def finalizar_si_corresponde(historial_csv, operaciones_abiertas, carpeta="reportes_bloques_20_practice"):
    """Devuelve informe SOLO tras completar el cupo y sin órdenes pendientes."""
    if not cupo_alcanzado() or _CUENTA["reportado"]:
        return None
    if operaciones_abiertas:
        return None
    try:
        with Path(historial_csv).open(encoding="utf-8-sig", newline="") as file:
            reporte = preparar_informe(csv.DictReader(file), _CUENTA["ids"], _CUENTA["inicio"])
    except (OSError, csv.Error, UnicodeError) as exc:
        reporte = {"estado": "INFORME_INCOMPLETO_NO_CONCLUYENTE",
                   "errores": [{"causa": type(exc).__name__}],
                   "reanudacion_automatica": False}
    ruta = _guardar_atomico(reporte, carpeta)
    _CUENTA["reportado"] = True
    print("BLOQUE20 PRACTICE |", reporte["estado"], "| informe:", ruta, flush=True)
    print("BLOQUE20 RESULTADO:", json.dumps(reporte.get("resultado", {}),
                                           ensure_ascii=False), flush=True)
    return reporte
