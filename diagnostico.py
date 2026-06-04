from mercado import obtener_velas
from indicadores import *
from price_action import *
from zonas import *

def diagnosticar_activo(activo):
    data = obtener_velas(activo)

    if data is None:
        print("[DEBUG]", activo, "sin velas suficientes")
        return

    opens = data["open"]
    closes = data["close"]
    highs = data["high"]
    lows = data["low"]

    price = closes[-1]
    rsi = calcular_rsi(closes)
    vol = volatilidad(highs, lows, 14)

    if rsi is None:
        print("[DEBUG]", activo, "RSI inválido")
        return

    if vol <= 0:
        print("[DEBUG]", activo, "volatilidad inválida")
        return

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)

    tendencia = tendencia_regresion(closes, 80)
    estructura = estructura_mercado(highs, lows, 30)

    patron, nombre_patron, fuerza_patron = patron_price_action_avanzado(
        opens, closes, highs, lows
    )

    rechazo, nombre_rechazo = rechazo_real(opens, closes, highs, lows)

    soporte_zona, resistencia_zona = soporte_resistencia_zonas(
        price, highs, lows, vol
    )

    soporte = soporte_zona["precio"]
    resistencia = resistencia_zona["precio"]

    bb_superior, bb_media, bb_inferior = bollinger_bands(closes, 20, 2)

    if bb_superior is None:
        print("[DEBUG]", activo, "bandas inválidas")
        return

    cerca_soporte = abs(price - soporte) <= soporte_zona["tolerancia"] * 1.15
    cerca_resistencia = abs(resistencia - price) <= resistencia_zona["tolerancia"] * 1.15

    if cerca_soporte and cerca_resistencia:
        distancia_soporte = abs(price - soporte)
        distancia_resistencia = abs(resistencia - price)

        fuerza_soporte = soporte_zona.get("fuerza", soporte_zona.get("toques", 1))
        fuerza_resistencia = resistencia_zona.get("fuerza", resistencia_zona.get("toques", 1))

        if distancia_soporte < distancia_resistencia:
            cerca_resistencia = False
        elif distancia_resistencia < distancia_soporte:
            cerca_soporte = False
        else:
            if fuerza_soporte > fuerza_resistencia:
                cerca_resistencia = False
            elif fuerza_resistencia > fuerza_soporte:
                cerca_soporte = False
            else:
                cerca_soporte = False
                cerca_resistencia = False

    cerca_banda_inferior = price <= bb_inferior + (vol * 1.2)
    cerca_banda_superior = price >= bb_superior - (vol * 1.2)

    extension = movimiento_extendido(opens, closes, 5)
    micro = micro_tendencia(opens, closes, 6)

    print(
        "[DEBUG]",
        activo,
        "| RSI:", round(rsi, 2),
        "| Patrón:", nombre_patron,
        "| Rechazo:", nombre_rechazo,
        "| Tendencia:", tendencia,
        "| Estructura:", estructura,
        "| Micro:", micro,
        "| Soporte:", cerca_soporte,
        "| Resistencia:", cerca_resistencia,
        "| Fuerza soporte:", soporte_zona.get("fuerza", soporte_zona.get("toques", 1)),
        "| Fuerza resistencia:", resistencia_zona.get("fuerza", resistencia_zona.get("toques", 1)),
        "| Banda inf:", cerca_banda_inferior,
        "| Banda sup:", cerca_banda_superior,
        "| Extensión:", extension,
        "| EMA9>EMA21:", ema9 > ema21
    )
