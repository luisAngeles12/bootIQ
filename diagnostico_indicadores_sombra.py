"""Diagnostico causal de indicadores, solo SHADOW y sin señales de trading.

Interpreta valores de la ultima vela CERRADA, no recalcula indicadores,
no consulta futuro, no concede puntaje y no introduce vetos operativos.
"""
import math


def _finito(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    return numero if math.isfinite(numero) else None


def diagnosticar_indicadores_sombra(evidencia):
    evidencia = evidencia if isinstance(evidencia, dict) else {}
    valores = evidencia.get("indicadores_tecnicos")
    valores = valores if isinstance(valores, dict) else {}
    ema9 = _finito(valores.get("ema9"))
    ema21 = _finito(valores.get("ema21"))
    superior = _finito(valores.get("bb_superior"))
    media = _finito(valores.get("bb_media"))
    inferior = _finito(valores.get("bb_inferior"))
    # El campo legacy ultima_close puede tener cero por defecto;
    # usar solo el snapshot opcional que no inventa ese valor.
    precio = _finito(evidencia.get("precio_cierre_indicadores"))
    rsi = _finito(evidencia.get("rsi_indicador"))
    direccion = str(evidencia.get("direccion") or "").lower().strip()

    diagnostico = {
        "modo": "SHADOW_SIN_AUTORIDAD",
        "autoriza": False,
        "bloquea": False,
        "alineacion_ema": "SIN_DATOS",
        "posicion_bollinger": "SIN_DATOS",
        "estado_rsi": "SIN_DATOS",
        "direccion": direccion,
        "alertas_calidad": [],
    }

    if ema9 is not None and ema21 is not None:
        if ema9 > ema21:
            tendencia = "ALCISTA"
        elif ema9 < ema21:
            tendencia = "BAJISTA"
        else:
            tendencia = "NEUTRA"
        if direccion not in ("call", "put"):
            diagnostico["alineacion_ema"] = "SIN_DIRECCION"
        elif tendencia == "NEUTRA":
            diagnostico["alineacion_ema"] = "CRUCE_NEUTRO"
        else:
            favorable = (direccion == "call" and tendencia == "ALCISTA") or (
                direccion == "put" and tendencia == "BAJISTA"
            )
            diagnostico["alineacion_ema"] = (
                "A_FAVOR" if favorable else "EN_CONTRA"
            )

        for nombre, esperado in (
            ("ema_alcista", ema9 > ema21),
            ("ema_bajista", ema9 < ema21),
        ):
            if nombre in evidencia and isinstance(evidencia[nombre], bool):
                if evidencia[nombre] != esperado:
                    diagnostico["alertas_calidad"].append(
                        "INCONSISTENCIA_" + nombre.upper()
                    )

    if (
        superior is not None and media is not None and inferior is not None
    ):
        if not inferior <= media <= superior:
            diagnostico["alertas_calidad"].append("BOLLINGER_ORDEN_INVALIDO")
        elif superior == inferior:
            # Bandas colapsadas: no existe rango util para interpretar posicion.
            # Solo alerta de calidad, sin cambiar la decision operativa.
            diagnostico["alertas_calidad"].append("BOLLINGER_ANCHO_NULO")
        elif precio is not None:
            if precio > superior:
                diagnostico["posicion_bollinger"] = "SOBRE_BANDA_SUPERIOR"
            elif precio < inferior:
                diagnostico["posicion_bollinger"] = "BAJO_BANDA_INFERIOR"
            elif precio >= media:
                diagnostico["posicion_bollinger"] = "MITAD_SUPERIOR"
            else:
                diagnostico["posicion_bollinger"] = "MITAD_INFERIOR"

    # RSI calculado sobre la vela cerrada, sin interpretar cero
    # por ausencia como sobreventa. No otorga bonos ni vetos.
    if rsi is not None:
        if not 0 <= rsi <= 100:
            diagnostico["alertas_calidad"].append("RSI_FUERA_DE_RANGO")
        elif rsi > 70:
            diagnostico["estado_rsi"] = "SOBRECOMPRA"
        elif rsi < 30:
            diagnostico["estado_rsi"] = "SOBREVENTA"
        else:
            diagnostico["estado_rsi"] = "NEUTRO"

    return diagnostico
