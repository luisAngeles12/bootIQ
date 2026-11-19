"""R9-15: contraste OFFLINE de historial BootIQ y exportación IQ normalizada.

NO conecta con IQ Option, no escribe datos, no reconstruye memoria ni autoriza
trading. La exportación debe ser obtenida independientemente del historial del
bot, con estas columnas exactas:
  order_id, modo_cuenta, estado, pnl, fecha_cierre_utc
Una copia del historial no es evidencia de broker independiente.
"""
import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.auditar_historial_fase9 import _cierre_explicito, _fecha_iso, _txt

CAMPOS_BROKER = {"order_id", "modo_cuenta", "estado", "pnl", "fecha_cierre_utc"}
CAMPOS_BOT = {
    "order_id", "modo_cuenta_configurado", "estado", "resultado",
    "fecha_conciliacion_local_utc",
}


def _leer(ruta, requeridos):
    with Path(ruta).open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        campos = lector.fieldnames or []
        if len(campos) != len(set(campos)):
            return None, "COLUMNAS_DUPLICADAS"
        if not requeridos.issubset(set(campos)):
            return None, "COLUMNAS_FALTANTES"
        datos = list(lector)
        if any(None in fila for fila in datos):
            return None, "CSV_MALFORMADO"
        return datos, None


def _monto(valor):
    try:
        monto = Decimal(str(valor).strip())
    except (ValueError, TypeError, InvalidOperation):
        return None
    if not monto.is_finite():
        return None
    # Un resultado con fracciones de centavo no se redondea sin prueba
    # de la unidad de origen. Comparacion estricta de centavos.
    centavos = monto * 100
    if centavos != centavos.to_integral_value():
        return None
    return monto


def _momento_utc(valor):
    iso = _fecha_iso(valor)
    if iso is None:
        return None
    marca = datetime.fromisoformat(iso)
    if marca.tzinfo is None or marca.utcoffset() is None:
        return None
    return marca.astimezone(timezone.utc)


def _indices(filas):
    ids = Counter(str(f.get("order_id") or "").strip() for f in filas)
    return {
        str(f.get("order_id") or "").strip(): f for f in filas
        if str(f.get("order_id") or "").strip()
        and ids[str(f.get("order_id") or "").strip()] == 1
    }, ids


def conciliar_exportacion(historial, exportacion):
    """Cotejo estricto: evita declarar matches ante duplicados y datos ambiguos."""
    if Path(historial).resolve() == Path(exportacion).resolve():
        return {
            "estado": "NO_APTO", "causa": "MISMO_ARCHIVO",
            "memoria_generada": False, "habilita_trading": False,
            "broker_verificado_en_linea": False,
            "origen_exportacion_verificado": False,
        }
    bot, error_bot = _leer(historial, CAMPOS_BOT)
    broker, error_broker = _leer(exportacion, CAMPOS_BROKER)
    base = {
        "estado": "NO_APTO",
        "memoria_generada": False,
        "habilita_trading": False,
        "broker_verificado_en_linea": False,
        "origen_exportacion_verificado": False,
        "nota": (
            "Comparación de CSV offline; la procedencia independiente del "
            "export de IQ debe probarse fuera de este programa."
        ),
    }
    if error_bot or error_broker:
        return {**base, "causa": "ESQUEMA_INVALIDO",
                "historial_error": error_bot, "broker_error": error_broker}
    por_id_bot, frec_bot = _indices(bot)
    por_id_broker, frec_broker = _indices(broker)
    duplicados_bot = sum(v > 1 for k, v in frec_bot.items() if k)
    duplicados_broker = sum(v > 1 for k, v in frec_broker.items() if k)
    motivos = Counter()
    conciliadas = 0
    pnl_conciliado = Decimal("0.00")
    for oid, f in por_id_bot.items():
        if _txt(f.get("modo_cuenta_configurado")) != "PRACTICE":
            motivos["BOT_MODO_NO_PRACTICE"] += 1
            continue
        if not _cierre_explicito(_txt(f.get("estado"))):
            motivos["BOT_NO_CERRADA"] += 1
            continue
        monto = _monto(f.get("resultado"))
        if monto is None:
            motivos["BOT_PNL_INVALIDO"] += 1
            continue
        b = por_id_broker.get(oid)
        if b is None:
            motivos["SIN_ID_UNICO_BROKER"] += 1
            continue
        if _txt(b.get("modo_cuenta")) != "PRACTICE":
            motivos["BROKER_MODO_NO_PRACTICE"] += 1
            continue
        if not _cierre_explicito(_txt(b.get("estado"))):
            motivos["BROKER_NO_CERRADA"] += 1
            continue
        broker_pnl = _monto(b.get("pnl"))
        if broker_pnl is None:
            motivos["BROKER_PNL_INVALIDO"] += 1
            continue
        if broker_pnl != monto:
            motivos["PNL_DIFIERE"] += 1
            continue
        cuando = _momento_utc(b.get("fecha_cierre_utc"))
        observado = _momento_utc(f.get("fecha_conciliacion_local_utc"))
        if cuando is None:
            motivos["BROKER_CIERRE_UTC_INVALIDO"] += 1
            continue
        if observado is None:
            motivos["BOT_CONCILIACION_UTC_AUSENTE"] += 1
            continue
        if cuando > observado:
            # La liquidación nunca puede ocurrir después de observar
            # localmente el resultado, salvo reloj/fuente inconsistente.
            motivos["CIERRE_BROKER_POSTERIOR_CONCILIACION_BOT"] += 1
            continue
        conciliadas += 1
        pnl_conciliado += monto

    base.update({
        "filas_bot": len(bot),
        "filas_broker": len(broker),
        "ids_bot_duplicados": duplicados_bot,
        "ids_broker_duplicados": duplicados_broker,
        "ids_sin_broker": sum(k not in frec_broker for k in frec_bot if k),
        "ids_solo_broker": sum(k not in frec_bot for k in frec_broker if k),
        "conciliadas_preliminares": conciliadas,
        "pnl_conciliado_preliminar": str(pnl_conciliado),
        "exclusiones": dict(sorted(motivos.items())),
    })
    # Incluso un 100 % de matches no acredita origen externo ni edge OOS.
    return {**base,
            "estado": "COINCIDENCIAS_OFFLINE_NO_CERTIFICADAS"
            if conciliadas else "NO_APTO",
            "causa": None if conciliadas else "SIN_COINCIDENCIAS_VALIDAS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial")
    parser.add_argument("exportacion_iq_normalizada")
    args = parser.parse_args()
    print(json.dumps(conciliar_exportacion(args.historial,
                                           args.exportacion_iq_normalizada),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
