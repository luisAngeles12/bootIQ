from motor_confianza import evaluar_senal


CONFIANZA_NEUTRA = 50.0


def _numero(valor, default=0.0):
    try:
        return float(valor if valor is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _entero(valor, default=0):
    try:
        return int(float(valor if valor is not None else default))
    except (TypeError, ValueError):
        return int(default)


def _lista(valor):
    return valor if isinstance(valor, list) else []


def _dict(valor):
    return valor if isinstance(valor, dict) else {}


def inferir_confianza(evidencia):
    """
    Adaptador estadístico entre motor_confianza.py y el Cerebro Único.

    Responsabilidad única:
    - llamar evaluar_senal();
    - conservar el resultado estadístico;
    - exponer coincidencias, niveles y diagnósticos;
    - mantener compatibilidad temporal con consumidores antiguos.

    No:
    - recalcula confianza;
    - multiplica pesos;
    - bloquea operaciones;
    - decide si operar;
    - interpreta protocolos;
    - modifica la evidencia recibida.
    """

    if not isinstance(evidencia, dict):
        evidencia = {}

    resultado = evaluar_senal(evidencia)

    if not isinstance(resultado, dict):
        resultado = {}

    confianza = _numero(
        resultado.get("confianza"),
        CONFIANZA_NEUTRA,
    )

    decision_estadistica = str(
        resultado.get(
            "decision",
            "SIN_EVIDENCIA_ESTADISTICA",
        )
        or "SIN_EVIDENCIA_ESTADISTICA"
    ).upper().strip()

    peso_final = _numero(
        resultado.get("peso_final"),
        confianza / CONFIANZA_NEUTRA if CONFIANZA_NEUTRA else 1.0,
    )

    ajuste_estadistico = _numero(
        resultado.get("ajuste_estadistico"),
        confianza - CONFIANZA_NEUTRA,
    )

    coincidencias = _lista(
        resultado.get("coincidencias")
    )

    coincidencias_descartadas = _lista(
        resultado.get("coincidencias_descartadas")
    )

    aportes_estadisticos = _lista(
        resultado.get("aportes_estadisticos")
    )

    motivos = [
        str(motivo)
        for motivo in _lista(resultado.get("motivos"))
        if str(motivo).strip()
    ]

    niveles_evaluados = _entero(
        resultado.get("niveles_evaluados"),
        0,
    )

    niveles_descartados = _entero(
        resultado.get("niveles_descartados"),
        0,
    )

    cantidad_coincidencias = _entero(
        resultado.get("cantidad_coincidencias"),
        len(coincidencias),
    )

    campos_setup_disponibles = _dict(
        resultado.get("campos_setup_disponibles")
    )

    # Evita repetir niveles en el diagnóstico.
    niveles_usados = list(
        dict.fromkeys(
            coincidencia.get("nivel")
            for coincidencia in coincidencias
            if (
                isinstance(coincidencia, dict)
                and coincidencia.get("nivel")
            )
        )
    )

    hay_evidencia_estadistica = bool(
        coincidencias
        and cantidad_coincidencias > 0
    )

    if not hay_evidencia_estadistica:
        decision_expuesta = "SIN_EVIDENCIA"

        if not motivos:
            motivos = [
                "Sin coincidencias estadísticas con muestra suficiente. "
                "Se mantiene la confianza base."
            ]
    else:
        decision_expuesta = decision_estadistica

    return {
        # Salida principal consumida por motor_decision.py
        "confianza": round(confianza, 2),
        "decision": decision_expuesta,
        "motivos": motivos,

        # Diagnóstico estadístico oficial
        "decision_motor_confianza": decision_estadistica,
        "ajuste_estadistico": round(ajuste_estadistico, 2),
        "hay_evidencia_estadistica": hay_evidencia_estadistica,

        # Compatibilidad temporal
        "peso_final": round(peso_final, 3),

        # Auditoría
        "niveles_usados": niveles_usados,
        "coincidencias": coincidencias,
        "coincidencias_descartadas": coincidencias_descartadas,
        "aportes_estadisticos": aportes_estadisticos,
        "niveles_evaluados": niveles_evaluados,
        "niveles_descartados": niveles_descartados,
        "cantidad_coincidencias": cantidad_coincidencias,
        "campos_setup_disponibles": campos_setup_disponibles,

        # Resultado íntegro para diagnóstico profundo.
        "detalle_motor_confianza": resultado,
    }


def probar_motor_inferencia():
    """
    Prueba rápida del contrato público.

    No requiere modificar archivos ni ejecutar operaciones.
    """

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
        },
    ]

    resultados = []

    for evidencia in ejemplos:
        resultado = inferir_confianza(evidencia)

        assert 0.0 <= resultado["confianza"] <= 100.0
        assert isinstance(resultado["motivos"], list)
        assert isinstance(resultado["coincidencias"], list)
        assert isinstance(resultado["niveles_usados"], list)
        assert "ajuste_estadistico" in resultado
        assert "detalle_motor_confianza" in resultado

        resultados.append(resultado)

    return resultados


if __name__ == "__main__":
    print("\n===== PRUEBA MOTOR INFERENCIA BOOTIQ =====")

    for indice, resultado in enumerate(
        probar_motor_inferencia(),
        start=1,
    ):
        print(f"\n--- EJEMPLO {indice} ---")
        print("Confianza:", resultado["confianza"])
        print("Decisión estadística:", resultado["decision"])
        print("Ajuste estadístico:", resultado["ajuste_estadistico"])
        print(
            "Hay evidencia estadística:",
            resultado["hay_evidencia_estadistica"],
        )
        print("Peso compatible:", resultado["peso_final"])
        print("Niveles usados:", resultado["niveles_usados"])
        print(
            "Niveles evaluados:",
            resultado["niveles_evaluados"],
        )
        print(
            "Niveles descartados:",
            resultado["niveles_descartados"],
        )
        print(
            "Coincidencias:",
            resultado["cantidad_coincidencias"],
        )

        for motivo in resultado["motivos"]:
            print("-", motivo)