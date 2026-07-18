def _txt(v):
    return str(v or "").lower().strip()


def _num(v, defecto=0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return defecto


PESOS_EVIDENCIA = {
    # Fortalezas históricas
    "pa_a_favor_call_alta": 8,
    "rechazo_vendedor_confirmado_debil_historico": 5,
    "choch_con_tendencia_debil": 3,
    "impulso_alcista_fuerte_debil_historico": 1,
    "reaccion_confirmada": 3,

    # Contradicciones direccionales
    # PA contrario nunca debe aumentar la confianza.
    "pa_contra_call": -5,
    "pa_contra_put": -5,

    # Riesgos que no deben castigar fuerte
    "call_resistencia_sin_ruptura": 0,
    "accion_precio_no_validada": 0,
    "ubicacion_fatiga_no_validada": 0,
    "vela_contraria_reciente": 0,

    # Riesgos moderados
    "mercado_no_validado": -4,
    "sin_contexto_claro": -3,
    "put_soporte_sin_ruptura": -3,
    "sweep_sin_confirmacion_pa": -3,
    "sweep_con_confirmacion_pa_debil": -2,

    # Riesgos fuertes
    "reaccion_sin_confirmacion_fuerte": -8,
    "pa_a_favor_put_debil": -6,
    "pa_a_favor_call_debil": -6,
}


# Compatibilidad temporal.
# Estos pesos deben revisarse posteriormente con la base estadística,
# porque un peso fijo por activo puede provocar sobreajuste.
PESOS_ACTIVOS = {
    "cocoa-otc": 4,
    "suiusd-otc": 4,
    "injusd-otc": 4,
    "ondousd-otc": 3,
    "usdvnd-otc": 3,
    "eurgbp-otc": 2,

    "fb-otc": -5,
    "eurthb-otc": -6,
    "fartcoinusd-otc": -6,
    "cardano-otc": -3,
}


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

    # =========================
    # CONSENSO
    # =========================
    if nivel_consenso == "alto":
        _registrar_ajuste(
            clave="consenso:alto",
            peso=4,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo="Ponderación consenso: ALTO (+4)",
        )

    elif nivel_consenso == "premium":
        _registrar_ajuste(
            clave="consenso:premium",
            peso=3,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo="Ponderación consenso: PREMIUM (+3)",
        )

    elif nivel_consenso == "bueno":
        _registrar_ajuste(
            clave="consenso:bueno",
            peso=-3,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo=(
                "Ponderación consenso: "
                "BUENO débil histórico (-3)"
            ),
        )

    elif nivel_consenso == "medio":
        _registrar_ajuste(
            clave="consenso:medio",
            peso=-1,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo="Ponderación consenso: MEDIO (-1)",
        )

    # =========================
    # SCORE FINAL
    # =========================
    if score_final >= 190:
        _registrar_ajuste(
            clave="score_final:alto",
            peso=1,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo="Ponderación score_final alto (+1)",
        )

    elif score_final < 120:
        _registrar_ajuste(
            clave="score_final:bajo",
            peso=-2,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo="Ponderación score_final bajo (-2)",
        )

    # =========================
    # CONFIRMACIÓN IA
    # =========================
    # Se utiliza únicamente el índice numérico para evitar contar
    # tres veces la misma evaluación mediante acción, nivel e índice.
    if 45 <= indice_confirmacion <= 59:
        _registrar_ajuste(
            clave="confirmacion_ia:45_59",
            peso=2,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo="Ponderación índice IA 45-59 (+2)",
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
    # Se conservan temporalmente hasta revisar motor_setup.py
    # y verificar qué ajustes ya están representados en su confianza.
    if "reversion_alcista" in tipo_setup:
        _registrar_ajuste(
            clave="setup:reversion_alcista",
            peso=5,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo=(
                "Ponderación setup: reversión alcista "
                "fuerte histórica (+5)"
            ),
        )

    if "rechazo_alcista" in tipo_setup:
        _registrar_ajuste(
            clave="setup:rechazo_alcista",
            peso=4,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo="Ponderación setup: rechazo alcista (+4)",
        )

    if "sweep_ruptura_confirmable" in subtipo_setup:
        _registrar_ajuste(
            clave="subtipo:sweep_ruptura_confirmable",
            peso=2,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo=(
                "Ponderación subtipo: "
                "sweep ruptura confirmable (+2)"
            ),
        )

    if "choch_con_pa_a_favor" in subtipo_setup:
        _registrar_ajuste(
            clave="subtipo:choch_con_pa_a_favor",
            peso=-2,
            pesos=pesos,
            motivos=motivos,
            claves_aplicadas=claves_aplicadas,
            motivo=(
                "Ponderación subtipo: CHOCH con PA "
                "a favor débil histórico (-2)"
            ),
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
    ajuste_total = max(-15, min(15, ajuste_total))

    return {
        "ajuste_ponderacion": round(ajuste_total, 2),
        "motivos_ponderacion": motivos,
        "pesos_aplicados": pesos,
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