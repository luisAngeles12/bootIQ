def _txt(v):
    return str(v or "").lower().strip()


def _num(v, defecto=0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return defecto


PESOS_EVIDENCIA = {
    # ========================================================
    # FORTALEZAS CON RESULTADOS FAVORABLES
    # ========================================================

    "pa_a_favor_put_media": 3,
    
    # Estas fortalezas continúan registrándose, pero el backtest
    # actual no demuestra una ventaja positiva.
    "choch_con_pa_valido": 0,
    "rechazo_comprador_confirmado": 0,
    "reaccion_confirmada": 0,
    "impulso_bajista_fuerte": 0,

    # ========================================================
    # FORTALEZAS SIN VENTAJA DEMOSTRADA
    # Se conservan como evidencia, pero no modifican confianza.
    # ========================================================

    "pa_a_favor_put_alta": 0,
    "pa_a_favor_call_media": 0,
    "pa_a_favor_call_alta": 0,
    "pullback_con_pa_y_tendencia": 0,
    "sweep_con_pa_valido": 0,
    "continuacion_con_pa_valido": 0,

    # ========================================================
    # RIESGOS QUE EL BACKTEST NO DEMUESTRA COMO NEGATIVOS
    # No deben castigar hasta validar fuera de muestra.
    # ========================================================

    "call_resistencia_sin_ruptura": 0,
    "put_soporte_sin_ruptura": 0,
    "sin_contexto_claro": 0,
    "contra_tendencia": 0,
    "sweep_sin_confirmacion_pa": 0,
    "sweep_con_confirmacion_pa_debil": 0,
    "vela_contraria_reciente": 0,
    "mercado_no_validado": 0,
    "fuerza_tendencia_baja": 0,
    "ubicacion_fatiga_no_validada": 0,
    "continuacion_tendencia_insuficiente": 0,
    "zona_sr_no_validada": 0,

    # ========================================================
    # RIESGOS CON DESEMPEÑO DÉBIL OBSERVADO
    # Penalizaciones pequeñas y limitadas.
    # ========================================================

    "accion_precio_no_validada": -1,
    "choch_sin_pa_valido": -1,
    "pa_a_favor_put_debil": -1,
    "pa_a_favor_call_debil": -1,
    "pa_contra_put": -1,
    "pa_contra_call": -1,
    "pullback_tendencia_insuficiente": -1,
    "tendencia_fuerte_no_confiable": -1,
    "rechazo_vendedor_confirmado_debil_historico": -1,

    # Riesgo más débil entre los grupos con muestra relevante.
    "reaccion_sin_confirmacion_fuerte": -2,
}

# Compatibilidad temporal.
# Estos pesos deben revisarse posteriormente con la base estadística,
# porque un peso fijo por activo puede provocar sobreajuste.
PESOS_ACTIVOS = {}


def _registrar_ajuste(
    clave,
    peso,
    pesos,
    motivos,
    claves_aplicadas,
    motivo,
):
    """
    Registra un ajuste una sola vez.

    La clave interna permite evitar que una misma evidencia se aplique
    por varias rutas del motor.
    """

    clave_normalizada = _txt(clave)

    if not clave_normalizada:
        return 0

    if clave_normalizada in claves_aplicadas:
        return 0

    claves_aplicadas.add(clave_normalizada)
    pesos.append(peso)
    motivos.append(motivo)

    return peso


def _aplicar_peso(
    nombre,
    pesos,
    motivos,
    origen,
    claves_aplicadas,
    forzar_no_positivo=False,
):
    """
    Aplica el peso asociado a una evidencia una sola vez.

    Cuando la evidencia proviene de riesgos_base, nunca se permite
    que genere un ajuste positivo.
    """

    clave = _txt(nombre)

    if not clave:
        return 0

    if clave in claves_aplicadas:
        return 0

    peso = PESOS_EVIDENCIA.get(clave)

    if peso is None:
        return 0

    if forzar_no_positivo and peso > 0:
        peso = -abs(peso)

    claves_aplicadas.add(clave)
    pesos.append(peso)
    motivos.append(
        f"Ponderación {origen}: {nombre} ({peso:+})"
    )

    return peso


def calcular_ponderacion_estadistica(evidencia):
    """
    Calcula un ajuste probabilístico basado en evidencias históricas.

    Responsabilidad:
    - no decide;
    - no bloquea;
    - no aplica protocolos;
    - no ejecuta operaciones;
    - evita aplicar dos veces una misma evidencia;
    - impide que los riesgos aumenten la confianza.

    Retorna el mismo contrato utilizado por el cerebro único.
    """

    evidencia = evidencia or {}

    pesos = []
    motivos = []
    claves_aplicadas = set()

    activo = _txt(evidencia.get("activo"))
    nivel_consenso = _txt(evidencia.get("nivel_consenso"))
    accion_precio = _txt(evidencia.get("accion_precio"))
    pa_tipo = _txt(evidencia.get("pa_tipo"))
    pa_direccion = _txt(evidencia.get("pa_direccion"))
    direccion = _txt(evidencia.get("direccion"))
    tipo_setup = _txt(evidencia.get("tipo_setup"))
    subtipo_setup = _txt(evidencia.get("subtipo_setup"))
    protocolo = _txt(evidencia.get("protocolo_sugerido"))
    riesgos_base = _txt(evidencia.get("riesgos_base"))
    fortalezas_base = _txt(evidencia.get("fortalezas_base"))

    score_final = _num(
        evidencia.get("score_final"),
        defecto=0,
    )
    indice_confirmacion = _num(
        evidencia.get("indice_confirmacion_ia"),
        defecto=0,
    )

    # =========================
    # ACTIVO
    # =========================
    if activo in PESOS_ACTIVOS:
        peso = PESOS_ACTIVOS[activo]

        _registrar_ajuste(
            clave=f"activo:{activo}",
            peso=peso,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo=f"Ponderación activo: {activo} ({peso:+})",
        )

    # El consenso se conserva para auditoría, pero temporalmente
    # no modifica la confianza.
    #
    # El backtest actual muestra una relación inversa:
    # MEDIO/BAJO superan a ALTO/BUENO/PREMIUM.
    # Hasta recalibrar motor_consenso.py con datos fuera de muestra,
    # aplicar puntos aquí introduciría selección inversa.
    if nivel_consenso:
        motivos.append(
            f"Consenso observado sin ajuste estadístico: "
            f"{nivel_consenso.upper()} (+0)"
        )
    # =========================
    # SCORE FINAL
    # =========================
    # score_final se conserva para trazabilidad.
    # No se usa todavía como ajuste porque mezcla puntaje,
    # prioridad y consenso en escalas diferentes.
    if score_final:
        motivos.append(
            f"Score final observado sin ajuste: {score_final:.2f} (+0)"
        )
    
    # =========================
    # CONFIRMACIÓN IA
    # =========================
    # La confirmación IA pertenece al protocolo de entrada.
    # Se conserva para auditoría, pero no modifica la confianza.
    if indice_confirmacion:
        motivos.append(
            f"Índice de confirmación IA observado: "
            f"{indice_confirmacion:.2f} (+0)"
        )
    # =========================
    # PRICE ACTION
    # =========================
    _aplicar_peso(
        nombre=accion_precio,
        pesos=pesos,
        motivos=motivos,
        origen="acción precio",
        claves_aplicadas=claves_aplicadas,
    )

    _aplicar_peso(
        nombre=pa_tipo,
        pesos=pesos,
        motivos=motivos,
        origen="PA profesional",
        claves_aplicadas=claves_aplicadas,
    )

    if (
        pa_direccion in {"call", "put"}
        and direccion in {"call", "put"}
    ):
        if pa_direccion == direccion:
            _registrar_ajuste(
                clave="pa:alineado_direccion",
                peso=2,
                pesos=pesos,
                motivos=motivos,
                claves_aplicadas=claves_aplicadas,
                motivo=(
                    "Ponderación PA alineado "
                    "con dirección (+2)"
                ),
            )

        else:
            clave_pa_contra = f"pa_contra_{direccion}"

            _aplicar_peso(
                nombre=clave_pa_contra,
                pesos=pesos,
                motivos=motivos,
                origen="PA contra dirección",
                claves_aplicadas=claves_aplicadas,
            )

    # =========================
    # SETUP
    # =========================
    # Setup y protocolo se mantienen en trazabilidad.
    # No reciben puntos manuales porque varias categorías tienen
    # muestras pequeñas o resultados contradictorios.
    if tipo_setup:
        motivos.append(
            f"Tipo de setup observado: {tipo_setup.upper()} (+0)"
        )
    
    if subtipo_setup:
        motivos.append(
            f"Subtipo de setup observado: {subtipo_setup.upper()} (+0)"
        )
    
    if protocolo:
        motivos.append(
            f"Protocolo sugerido observado: {protocolo.upper()} (+0)"
        )

    # =========================
    # PROTOCOLO
    # =========================
    # Los protocolos fueron retirados de la ponderación.
    # Un protocolo describe cómo ejecutar una operación;
    # no constituye evidencia predictiva.

    # =========================
    # RIESGOS
    # =========================
    for item in riesgos_base.split("|"):
        item = item.strip()

        if not item:
            continue

        _aplicar_peso(
            nombre=item,
            pesos=pesos,
            motivos=motivos,
            origen="riesgo",
            claves_aplicadas=claves_aplicadas,
            forzar_no_positivo=True,
        )

    # =========================
    # FORTALEZAS
    # =========================
    for item in fortalezas_base.split("|"):
        item = item.strip()

        if not item:
            continue

        _aplicar_peso(
            nombre=item,
            pesos=pesos,
            motivos=motivos,
            origen="fortaleza",
            claves_aplicadas=claves_aplicadas,
        )

    ajuste_total = sum(pesos)

    # Límite temporal de seguridad.
    # Evita que la ponderación domine por completo la confianza base.
    ajuste_total = max(-6, min(6, ajuste_total))

    return {
        "ajuste_ponderacion": round(ajuste_total, 2),
        "motivos_ponderacion": motivos,
        "pesos_aplicados": pesos,
        "cantidad_pesos_aplicados": len(pesos),
        "limite_ajuste": 6,
        "version_ponderacion": "BOOTIQ_PONDERACION_2.0_CONTROLADA",
    }


def probar_motor_ponderacion():
    """
    Pruebas mínimas de seguridad de la primera refactorización.
    """

    pruebas = [
        {
            "nombre": "PA contrario a PUT",
            "evidencia": {
                "direccion": "put",
                "pa_direccion": "call",
                "riesgos_base": "pa_contra_put",
                "score_final": 150,
            },
        },
        {
            "nombre": "Evidencia repetida",
            "evidencia": {
                "direccion": "call",
                "pa_direccion": "put",
                "accion_precio": "pa_contra_call",
                "riesgos_base": "pa_contra_call|pa_contra_call",
                "score_final": 150,
            },
        },
        {
            "nombre": "Protocolo no pondera",
            "evidencia": {
                "direccion": "call",
                "pa_direccion": "call",
                "protocolo_sugerido":
                    "protocolo_ruptura_resistencia",
                "score_final": 150,
            },
        },
    ]

    print("\n===== PRUEBA MOTOR PONDERACIÓN BOOTIQ =====")

    for prueba in pruebas:
        resultado = calcular_ponderacion_estadistica(
            prueba["evidencia"]
        )

        print(f"\n--- {prueba['nombre']} ---")
        print(
            "Ajuste:",
            resultado["ajuste_ponderacion"],
        )
        print(
            "Pesos:",
            resultado["pesos_aplicados"],
        )

        for motivo in resultado["motivos_ponderacion"]:
            print("-", motivo)


if __name__ == "__main__":
    probar_motor_ponderacion()