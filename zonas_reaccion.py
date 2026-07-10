
from price_action_profesional import contexto_price_action_profesional
def evaluar_reaccion_en_zona(
    direccion,
    opens,
    closes,
    highs,
    lows,
    soporte,
    resistencia,
    vol
):
    try:
        precio = closes[-1]

        if vol <= 0:
            vol = abs(precio) * 0.0001

        ultimas = 8

        opens_r = opens[-ultimas:]
        closes_r = closes[-ultimas:]
        highs_r = highs[-ultimas:]
        lows_r = lows[-ultimas:]

        distancia_soporte = abs(precio - soporte)
        distancia_resistencia = abs(resistencia - precio)

        cerca_soporte = distancia_soporte <= vol * 1.20
        cerca_resistencia = distancia_resistencia <= vol * 1.20

        zona_total = abs(resistencia - soporte)

        if zona_total <= 0:
            zona_total = vol * 2

        posicion_rango = distancia_soporte / zona_total

        # 0.00 = pegado al soporte
        # 1.00 = pegado a resistencia

        mechas_superiores = 0
        mechas_inferiores = 0
        velas_rojas = 0
        velas_verdes = 0
        cuerpos_fuertes_rojos = 0
        cuerpos_fuertes_verdes = 0

        for o, c, h, l in zip(opens_r, closes_r, highs_r, lows_r):
            rango = h - l

            if rango <= 0:
                continue

            cuerpo = abs(c - o)
            fuerza = cuerpo / rango

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            if mecha_sup >= rango * 0.35:
                mechas_superiores += 1

            if mecha_inf >= rango * 0.35:
                mechas_inferiores += 1

            if c < o:
                velas_rojas += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_rojos += 1

            if c > o:
                velas_verdes += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_verdes += 1

        o1 = opens[-1]
        c1 = closes[-1]
        h1 = highs[-1]
        l1 = lows[-1]

        rango1 = h1 - l1

        if rango1 <= 0:
            return False, "rango inválido en zona"

        cuerpo1 = abs(c1 - o1)
        fuerza1 = cuerpo1 / rango1

        mecha_sup_1 = h1 - max(o1, c1)
        mecha_inf_1 = min(o1, c1) - l1

        vela_roja = c1 < o1
        vela_verde = c1 > o1

        rechazo_vendedor_fuerte = (
            cerca_resistencia
            and vela_roja
            and mecha_sup_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        rechazo_comprador_fuerte = (
            cerca_soporte
            and vela_verde
            and mecha_inf_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        presion_vendedora_en_resistencia = (
            cerca_resistencia
            and mechas_superiores >= 3
            and velas_rojas >= 3
            and cuerpos_fuertes_rojos >= 1
        )

        presion_compradora_en_soporte = (
            cerca_soporte
            and mechas_inferiores >= 3
            and velas_verdes >= 3
            and cuerpos_fuertes_verdes >= 1
        )

        agotamiento_alcista = (
            cerca_resistencia
            and velas_verdes >= 4
            and mechas_superiores >= 2
            and fuerza1 < 0.55
        )

        agotamiento_bajista = (
            cerca_soporte
            and velas_rojas >= 4
            and mechas_inferiores >= 2
            and fuerza1 < 0.55
        )
        pa_profesional = contexto_price_action_profesional(
            opens,
            closes,
            highs,
            lows,
            soporte,
            resistencia,
            vol
        )
       
        # =========================
        # PUT EN RESISTENCIA
        # =========================
        if direccion == "put":
            if not cerca_resistencia:
                return False, "PUT sin cercanía real a resistencia"
            if (
                pa_profesional.get("direccion") == "PUT"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_VENDEDOR_CONFIRMADO",
                    "AGOTAMIENTO_ALCISTA_CONFIRMADO"
                ]
            ):
                return True, "PUT válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_soporte or posicion_rango <= 0.25:
                return False, "PUT rechazado: soporte demasiado cerca"

            if rechazo_vendedor_fuerte:
                return True, "PUT válido: rechazo vendedor fuerte en resistencia"

            if presion_vendedora_en_resistencia:
                return True, "PUT válido: presión vendedora en resistencia"

            if agotamiento_alcista:
                return True, "PUT válido: agotamiento alcista en resistencia"

            return False, "PUT sin reacción suficiente en resistencia"

        # =========================
        # CALL EN SOPORTE
        # =========================
        if direccion == "call":
            if not cerca_soporte:
                return False, "CALL sin cercanía real a soporte"
            if (
                pa_profesional.get("direccion") == "CALL"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_COMPRADOR_CONFIRMADO",
                    "AGOTAMIENTO_BAJISTA_CONFIRMADO"
                ]
            ):
                return True, "CALL válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_resistencia or posicion_rango >= 0.75:
                return False, "CALL rechazado: resistencia demasiado cerca"

            if rechazo_comprador_fuerte:
                return True, "CALL válido: rechazo comprador fuerte en soporte"

            if presion_compradora_en_soporte:
                return True, "CALL válido: presión compradora en soporte"

            if agotamiento_bajista:
                return True, "CALL válido: agotamiento bajista en soporte"

            return False, "CALL sin reacción suficiente en soporte"

        return False, "dirección inválida"

    except Exception as e:
        print("Error evaluando reacción en zona:", e)
        return False, "error reacción zona"
    
    
def evaluar_reaccion_en_zona(
    direccion,
    opens,
    closes,
    highs,
    lows,
    soporte,
    resistencia,
    vol
):
    try:
        precio = closes[-1]

        if vol <= 0:
            vol = abs(precio) * 0.0001

        ultimas = 8

        opens_r = opens[-ultimas:]
        closes_r = closes[-ultimas:]
        highs_r = highs[-ultimas:]
        lows_r = lows[-ultimas:]

        distancia_soporte = abs(precio - soporte)
        distancia_resistencia = abs(resistencia - precio)

        cerca_soporte = distancia_soporte <= vol * 1.20
        cerca_resistencia = distancia_resistencia <= vol * 1.20

        zona_total = abs(resistencia - soporte)

        if zona_total <= 0:
            zona_total = vol * 2

        posicion_rango = distancia_soporte / zona_total

        # 0.00 = pegado al soporte
        # 1.00 = pegado a resistencia

        mechas_superiores = 0
        mechas_inferiores = 0
        velas_rojas = 0
        velas_verdes = 0
        cuerpos_fuertes_rojos = 0
        cuerpos_fuertes_verdes = 0

        for o, c, h, l in zip(opens_r, closes_r, highs_r, lows_r):
            rango = h - l

            if rango <= 0:
                continue

            cuerpo = abs(c - o)
            fuerza = cuerpo / rango

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            if mecha_sup >= rango * 0.35:
                mechas_superiores += 1

            if mecha_inf >= rango * 0.35:
                mechas_inferiores += 1

            if c < o:
                velas_rojas += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_rojos += 1

            if c > o:
                velas_verdes += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_verdes += 1

        o1 = opens[-1]
        c1 = closes[-1]
        h1 = highs[-1]
        l1 = lows[-1]

        rango1 = h1 - l1

        if rango1 <= 0:
            return False, "rango inválido en zona"

        cuerpo1 = abs(c1 - o1)
        fuerza1 = cuerpo1 / rango1

        mecha_sup_1 = h1 - max(o1, c1)
        mecha_inf_1 = min(o1, c1) - l1

        vela_roja = c1 < o1
        vela_verde = c1 > o1

        rechazo_vendedor_fuerte = (
            cerca_resistencia
            and vela_roja
            and mecha_sup_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        rechazo_comprador_fuerte = (
            cerca_soporte
            and vela_verde
            and mecha_inf_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        presion_vendedora_en_resistencia = (
            cerca_resistencia
            and mechas_superiores >= 3
            and velas_rojas >= 3
            and cuerpos_fuertes_rojos >= 1
        )

        presion_compradora_en_soporte = (
            cerca_soporte
            and mechas_inferiores >= 3
            and velas_verdes >= 3
            and cuerpos_fuertes_verdes >= 1
        )

        agotamiento_alcista = (
            cerca_resistencia
            and velas_verdes >= 4
            and mechas_superiores >= 2
            and fuerza1 < 0.55
        )

        agotamiento_bajista = (
            cerca_soporte
            and velas_rojas >= 4
            and mechas_inferiores >= 2
            and fuerza1 < 0.55
        )
        pa_profesional = contexto_price_action_profesional(
            opens,
            closes,
            highs,
            lows,
            soporte,
            resistencia,
            vol
        )
       
        # =========================
        # PUT EN RESISTENCIA
        # =========================
        if direccion == "put":
            if not cerca_resistencia:
                return False, "PUT sin cercanía real a resistencia"
            if (
                pa_profesional.get("direccion") == "PUT"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_VENDEDOR_CONFIRMADO",
                    "AGOTAMIENTO_ALCISTA_CONFIRMADO"
                ]
            ):
                return True, "PUT válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_soporte or posicion_rango <= 0.25:
                return False, "PUT rechazado: soporte demasiado cerca"

            if rechazo_vendedor_fuerte:
                return True, "PUT válido: rechazo vendedor fuerte en resistencia"

            if presion_vendedora_en_resistencia:
                return True, "PUT válido: presión vendedora en resistencia"

            if agotamiento_alcista:
                return True, "PUT válido: agotamiento alcista en resistencia"

            return False, "PUT sin reacción suficiente en resistencia"

        # =========================
        # CALL EN SOPORTE
        # =========================
        if direccion == "call":
            if not cerca_soporte:
                return False, "CALL sin cercanía real a soporte"
            if (
                pa_profesional.get("direccion") == "CALL"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_COMPRADOR_CONFIRMADO",
                    "AGOTAMIENTO_BAJISTA_CONFIRMADO"
                ]
            ):
                return True, "CALL válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_resistencia or posicion_rango >= 0.75:
                return False, "CALL rechazado: resistencia demasiado cerca"

            if rechazo_comprador_fuerte:
                return True, "CALL válido: rechazo comprador fuerte en soporte"

            if presion_compradora_en_soporte:
                return True, "CALL válido: presión compradora en soporte"

            if agotamiento_bajista:
                return True, "CALL válido: agotamiento bajista en soporte"

            return False, "CALL sin reacción suficiente en soporte"

        return False, "dirección inválida"

    except Exception as e:
        print("Error evaluando reacción en zona:", e)
        return False, "error reacción zona"
