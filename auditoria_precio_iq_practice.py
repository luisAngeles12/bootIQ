"""Extraccion conservadora de precios de eventos IQ almacenados en memoria.

No solicita datos al broker; no infiere precios ni reescala unidades.
Se guardan SOLO eventos del order_id recibido, no el payload completo.
La ausencia de open_price/close_price no se interpreta como precio cero.
"""
import json
import math


def _numero(valor):
    if isinstance(valor, bool):
        return None
    try:
        precio = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    return precio if math.isfinite(precio) and precio > 0 else None


def extraer_precios_eventos(order_id, datos):
    """Devuelve JSON auditado o cadena vacia si no hay precios verificables."""
    if not isinstance(datos, dict):
        return ""
    oid = str(order_id or "").strip()
    if not oid:
        return ""
    precios = {}
    for nombre, campo, salida in (
        ("option-opened", "open_price", "precio_apertura_iq"),
        ("option-closed", "close_price", "precio_cierre_iq"),
    ):
        evento = datos.get(nombre)
        if not isinstance(evento, dict):
            continue
        msg = evento.get("msg")
        if not isinstance(msg, dict):
            continue
        if str(msg.get("option_id") or "").strip() != oid:
            continue
        numero = _numero(msg.get(campo))
        if numero is not None:
            precios[salida] = numero
    if not precios:
        return ""
    return json.dumps(
        {"order_id": oid, "fuente": "IQ_ORDER_ASYNC_EVENTOS_CACHE",
         "precios": precios, "unidades_confirmadas": False},
        ensure_ascii=False, sort_keys=True,
    )


def leer_cache_orden(iq, order_id):
    """Una lectura inmediata, despues del cierre; sin bucles ni red."""
    if iq is None:
        return ""
    try:
        return extraer_precios_eventos(
            order_id, iq.get_async_order(int(order_id))
        )
    except (ValueError, TypeError, KeyError, AttributeError):
        return ""
    except Exception:
        # Telemetria opcional: nunca impedir conciliacion de cierres.
        return ""
