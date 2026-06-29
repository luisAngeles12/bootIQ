from motor_confianza import evaluar_senal


def inferir_confianza(evidencia):
    """
    Motor de inferencia estadística.

    Recibe evidencia estándar y busca conocimiento en varios niveles.
    No bloquea directamente.
    Solo estima confianza y explica por qué.
    """

    resultado = evaluar_senal(evidencia)

    confianza = resultado.get("confianza", 50.0)
    decision = resultado.get("decision", "NEUTRA")
    peso_final = resultado.get("peso_final", 1.0)
    coincidencias = resultado.get("coincidencias", [])
    motivos = resultado.get("motivos", [])

    niveles_usados = [
        c.get("nivel")
        for c in coincidencias
        if c.get("nivel")
    ]

    if not coincidencias:
        return {
            "confianza": confianza,
            "decision": "SIN_EVIDENCIA",
            "peso_final": peso_final,
            "niveles_usados": [],
            "coincidencias": [],
            "motivos": [
                "Sin coincidencias estadísticas suficientes. Se mantiene confianza base."
            ]
        }

    return {
        "confianza": confianza,
        "decision": decision,
        "peso_final": peso_final,
        "niveles_usados": niveles_usados,
        "coincidencias": coincidencias,
        "motivos": motivos
    }


def probar_motor_inferencia():
    ejemplos = [
        {
            "activo": "BIDU-OTC",
            "direccion": "put",
            "patron": "CHOCH bajista",
            "tipo_mercado": "TENDENCIA_BAJISTA",
            "estado_tendencia": "BAJISTA_NORMAL",
            "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
            "pa_direccion": "PUT",
            "calidad_mercado": "NORMAL",
        },
        {
            "activo": "COCOA-OTC",
            "direccion": "put",
            "patron": "liquidity sweep bajista",
            "tipo_mercado": "TENDENCIA_ALCISTA",
            "estado_tendencia": "ALCISTA_NORMAL",
            "pa_tipo": "SIN_CONTEXTO_CLARO",
            "pa_direccion": "NEUTRA",
            "calidad_mercado": "NORMAL",
        }
    ]

    print("\n===== PRUEBA MOTOR INFERENCIA BOOTIQ =====")

    for i, evidencia in enumerate(ejemplos, start=1):
        resultado = inferir_confianza(evidencia)

        print(f"\n--- EJEMPLO {i} ---")
        print("Patrón:", evidencia["patron"])
        print("Dirección:", evidencia["direccion"])
        print("Confianza:", resultado["confianza"])
        print("Decisión inferida:", resultado["decision"])
        print("Peso final:", resultado["peso_final"])
        print("Niveles usados:", resultado["niveles_usados"])

        for motivo in resultado["motivos"]:
            print("-", motivo)


if __name__ == "__main__":
    probar_motor_inferencia()