from motor_confianza import evaluar_senal


def inferir_confianza(evidencia):
    """
    Motor de inferencia estadística.

    Recibe evidencia estándar y consulta el motor de confianza histórica.

    Responsabilidad:
    - conservar el resultado estadístico;
    - exponer coincidencias y niveles utilizados;
    - transportar el diagnóstico al cerebro;
    - no bloquear ni decidir operaciones.
    """

    resultado = evaluar_senal(evidencia)

    confianza = resultado.get("confianza", 50.0)
    decision_original = resultado.get("decision", "NEUTRA")
    peso_final = resultado.get("peso_final", 1.0)
    coincidencias = resultado.get("coincidencias", [])
    motivos = resultado.get("motivos", [])

    niveles_evaluados = resultado.get("niveles_evaluados", 0)
    niveles_descartados = resultado.get("niveles_descartados", 0)
    cantidad_coincidencias = resultado.get(
        "cantidad_coincidencias",
        len(coincidencias)
    )
    campos_setup_disponibles = resultado.get(
        "campos_setup_disponibles",
        {}
    )

    # Evita repetir un mismo nivel cuando aparezca más de una coincidencia.
    niveles_usados = list(dict.fromkeys(
        c.get("nivel")
        for c in coincidencias
        if c.get("nivel")
    ))

    resultado_base = {
        "confianza": confianza,
        "peso_final": peso_final,
        "decision_motor_confianza": decision_original,
        "niveles_usados": niveles_usados,
        "coincidencias": coincidencias,
        "motivos": motivos,
        "niveles_evaluados": niveles_evaluados,
        "niveles_descartados": niveles_descartados,
        "cantidad_coincidencias": cantidad_coincidencias,
        "campos_setup_disponibles": campos_setup_disponibles,
    }

    if not coincidencias:
        resultado_base["decision"] = "SIN_EVIDENCIA"
        resultado_base["niveles_usados"] = []
        resultado_base["coincidencias"] = []
        resultado_base["motivos"] = [
            "Sin coincidencias estadísticas suficientes. "
            "Se mantiene confianza base."
        ]

        return resultado_base

    resultado_base["decision"] = decision_original

    return resultado_base
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
        print(
            "Niveles evaluados:",
            resultado.get("niveles_evaluados", 0)
        )
        print(
            "Niveles descartados:",
            resultado.get("niveles_descartados", 0)
        )
        print(
            "Coincidencias:",
            resultado.get("cantidad_coincidencias", 0)
        )
        print(
            "Campos setup disponibles:",
            resultado.get("campos_setup_disponibles", {})
        )

        for motivo in resultado["motivos"]:
            print("-", motivo)


if __name__ == "__main__":
    probar_motor_inferencia()