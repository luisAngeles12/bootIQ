import csv
import os
from collections import defaultdict

RUTA_APRENDIZAJE = "aprendizaje_historico_bootiq.csv"

# Una muestra menor no modifica la confianza.
MIN_MUESTRA = 12

# Umbrales de rendimiento histórico.
UMBRAL_BUENO = 58.0
UMBRAL_MALO = 48.0

# El aprendizaje histórico solo acompaña la decisión.
# Nunca debe dominar el análisis estructural.
AJUSTE_MAXIMO = 5.0
AJUSTE_MINIMO = -5.0

RESULTADOS_VALIDOS = {"WIN", "LOSS"}


def _txt(valor):
    return str(valor or "").upper().strip()


def _entero(valor, default=0):
    try:
        return int(float(valor if valor is not None else default))
    except (TypeError, ValueError):
        return int(default)


def _numero(valor, default=0.0):
    try:
        return float(valor if valor is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _limitar_ajuste(valor):
    valor = _numero(valor, 0.0)
    return round(max(AJUSTE_MINIMO, min(AJUSTE_MAXIMO, valor)), 2)


def _familia_setup(senal):
    """
    Obtiene una familia estable para el aprendizaje.

    Evita depender de demasiados campos específicos, porque una clave
    excesivamente detallada fragmenta la muestra y produce combinaciones
    con muy pocas operaciones.
    """

    familia = _txt(senal.get("familia_setup"))
    if familia:
        return familia

    texto = " ".join([
        _txt(senal.get("patron")),
        _txt(senal.get("tipo_setup")),
        _txt(senal.get("subtipo_setup")),
    ])

    if "CHOCH" in texto:
        return "CHOCH"

    if "PULLBACK" in texto:
        return "PULLBACK"

    if "SWEEP" in texto or "LIQUIDITY" in texto:
        return "SWEEP"

    if "RUPTURA" in texto or "BREAKOUT" in texto:
        return "RUPTURA"

    if "RECHAZO" in texto:
        return "RECHAZO"

    tipo_setup = _txt(senal.get("tipo_setup"))
    return tipo_setup or "OTRA"


def _clave(senal):
    """
    Construye una clave histórica deliberadamente compacta.

    No incluye:
    - protocolo_sugerido
    - accion_precio
    - pa_tipo
    - nivel_consenso
    - subtipo_setup

    Esos campos ya intervienen en otros motores y, además, vuelven la
    combinación demasiado específica para acumular una muestra confiable.
    """

    return "|".join([
        _txt(senal.get("activo")),
        _txt(senal.get("direccion")),
        _familia_setup(senal),
        _txt(senal.get("tipo_mercado")),
        _txt(senal.get("estado_tendencia")),
    ])


def _confiabilidad_muestra(total):
    if total < MIN_MUESTRA:
        return "INSUFICIENTE"

    if total < 20:
        return "BAJA"

    if total < 50:
        return "MEDIA"

    return "ALTA"


def _calcular_ajuste(total, winrate):
    """
    Convierte el rendimiento histórico en un ajuste moderado,
    ponderado también por la confiabilidad de la muestra.
    """

    total = _entero(total, 0)
    winrate = _numero(winrate, 0.0)

    if total < MIN_MUESTRA:
        return 0.0, "MUESTRA_INSUFICIENTE"

    # El ajuste completo solo se permite con una muestra sólida.
    if total < 15:
        factor_muestra = 0.40
    elif total < 30:
        factor_muestra = 0.65
    elif total < 50:
        factor_muestra = 0.85
    else:
        factor_muestra = 1.00

    if winrate >= UMBRAL_BUENO:
        diferencia = winrate - UMBRAL_BUENO
        ajuste_base = 2.0 + min(3.0, diferencia / 6.0)
        ajuste = ajuste_base * factor_muestra

        return _limitar_ajuste(ajuste), "FAVORABLE"

    if winrate <= UMBRAL_MALO:
        diferencia = UMBRAL_MALO - winrate
        ajuste_base = -(2.0 + min(3.0, diferencia / 6.0))
        ajuste = ajuste_base * factor_muestra

        return _limitar_ajuste(ajuste), "DEBIL"

    return 0.0, "NEUTRO"

def cargar_aprendizaje(ruta=RUTA_APRENDIZAJE):
    """
    Carga la memoria histórica desde CSV.

    Las filas inválidas no interrumpen la carga completa.
    """

    if not os.path.exists(ruta):
        return {}

    memoria = {}

    try:
        with open(ruta, "r", encoding="utf-8-sig", newline="") as archivo:
            reader = csv.DictReader(archivo)

            for row in reader:
                clave = str(row.get("clave", "") or "").strip()
                if not clave:
                    continue

                total = _entero(row.get("total"), 0)
                wins = _entero(row.get("wins"), 0)
                losses = _entero(row.get("losses"), 0)

                if total <= 0:
                    total = wins + losses

                winrate = _numero(row.get("winrate"), 0.0)

                ajuste_calculado, decision_calculada = _calcular_ajuste(
                    total=total,
                    winrate=winrate,
                )

                # Se recalcula el ajuste para impedir que un CSV antiguo
                # conserve valores excesivos como +8 o -10.
                memoria[clave] = {
                    "total": total,
                    "wins": wins,
                    "losses": losses,
                    "winrate": round(winrate, 2),
                    "ajuste_confianza": ajuste_calculado,
                    "decision_aprendizaje": decision_calculada,
                    "confiabilidad_muestra": _confiabilidad_muestra(total),
                }

    except (OSError, csv.Error):
        return {}

    return memoria


def evaluar_aprendizaje_historico(senal, memoria=None):
    """
    Consulta el rendimiento histórico de una combinación.

    Este motor:
    - no decide;
    - no bloquea;
    - no interpreta riesgo estructural;
    - no aplica protocolos;
    - solo devuelve un ajuste moderado de confianza.
    """

    if not isinstance(senal, dict):
        senal = {}

    if memoria is None:
        memoria = cargar_aprendizaje()

    if not isinstance(memoria, dict):
        memoria = {}

    clave = _clave(senal)
    data = memoria.get(clave)

    if not data:
        return {
            "aprendizaje_encontrado": False,
            "clave_aprendizaje": clave,
            "ajuste_confianza_aprendizaje": 0.0,
            "decision_aprendizaje": "SIN_DATOS",
            "motivo_aprendizaje": (
                "Sin historial suficiente para esta combinación."
            ),
            "muestra_historica": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "confiabilidad_muestra": "SIN_DATOS",
        }

    total = _entero(data.get("total"), 0)
    wins = _entero(data.get("wins"), 0)
    losses = _entero(data.get("losses"), 0)
    winrate = _numero(data.get("winrate"), 0.0)

    ajuste, decision = _calcular_ajuste(
        total=total,
        winrate=winrate,
    )

    confiabilidad = _confiabilidad_muestra(total)

    if total < MIN_MUESTRA:
        motivo = (
            f"Historial insuficiente: {total} operaciones reales; "
            f"mínimo requerido: {MIN_MUESTRA}."
        )
    else:
        motivo = (
            f"Historial real: {total} operaciones, "
            f"{wins} WIN, {losses} LOSS, winrate {winrate:.2f}%, "
            f"confiabilidad {confiabilidad.lower()}."
        )

    return {
        "aprendizaje_encontrado": True,
        "clave_aprendizaje": clave,
        "ajuste_confianza_aprendizaje": ajuste,
        "decision_aprendizaje": decision,
        "motivo_aprendizaje": motivo,
        "muestra_historica": total,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2),
        "confiabilidad_muestra": confiabilidad,
    }


def _resultado_real(registro):
    """
    Devuelve WIN o LOSS únicamente cuando el resultado es real y válido.

    Se ignoran:
    - resultados hipotéticos;
    - operaciones abiertas;
    - cancelaciones;
    - empates;
    - registros vacíos;
    - cualquier valor distinto de WIN o LOSS.
    """

    if not isinstance(registro, dict):
        return ""

    if bool(registro.get("es_hipotetico", False)):
        return ""

    estado = _txt(registro.get("estado_operacion"))
    if estado in {
        "HIPOTETICA",
        "HIPOTETICO",
        "ABIERTA",
        "PENDIENTE",
        "CANCELADA",
        "CANCELADO",
    }:
        return ""

    resultado = _txt(registro.get("resultado"))

    if resultado in RESULTADOS_VALIDOS:
        return resultado

    return ""


def generar_aprendizaje_desde_resultados(
    resultados,
    ruta=RUTA_APRENDIZAJE,
):
    """
    Genera la memoria histórica usando exclusivamente operaciones cerradas
    con resultado real WIN o LOSS.
    """

    grupos = defaultdict(
        lambda: {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "ejemplo": {},
        }
    )

    registros_validos = 0
    registros_ignorados = 0

    for registro in resultados or []:
        if not isinstance(registro, dict):
            registros_ignorados += 1
            continue

        resultado = _resultado_real(registro)

        if resultado not in RESULTADOS_VALIDOS:
            registros_ignorados += 1
            continue

        clave = _clave(registro)
        grupo = grupos[clave]

        if not grupo["ejemplo"]:
            grupo["ejemplo"] = registro

        grupo["total"] += 1
        registros_validos += 1

        if resultado == "WIN":
            grupo["wins"] += 1
        elif resultado == "LOSS":
            grupo["losses"] += 1

    filas = []

    for clave, datos in grupos.items():
        total = datos["total"]
        wins = datos["wins"]
        losses = datos["losses"]

        winrate = round(
            (wins / total) * 100,
            2,
        ) if total else 0.0

        ajuste, decision = _calcular_ajuste(
            total=total,
            winrate=winrate,
        )

        ejemplo = datos["ejemplo"]

        filas.append({
            "clave": clave,
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "ajuste_confianza": ajuste,
            "decision_aprendizaje": decision,
            "confiabilidad_muestra": _confiabilidad_muestra(total),
            "activo": ejemplo.get("activo", ""),
            "direccion": ejemplo.get("direccion", ""),
            "familia_setup": _familia_setup(ejemplo),
            "tipo_mercado": ejemplo.get("tipo_mercado", ""),
            "estado_tendencia": ejemplo.get("estado_tendencia", ""),
        })

    filas.sort(
        key=lambda fila: (
            fila["total"],
            fila["winrate"],
        ),
        reverse=True,
    )

    campos = [
        "clave",
        "total",
        "wins",
        "losses",
        "winrate",
        "ajuste_confianza",
        "decision_aprendizaje",
        "confiabilidad_muestra",
        "activo",
        "direccion",
        "familia_setup",
        "tipo_mercado",
        "estado_tendencia",
    ]

    directorio = os.path.dirname(os.path.abspath(ruta))
    if directorio:
        os.makedirs(directorio, exist_ok=True)

    with open(
        ruta,
        "w",
        newline="",
        encoding="utf-8",
    ) as archivo:
        writer = csv.DictWriter(
            archivo,
            fieldnames=campos,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(filas)

    print("Archivo de aprendizaje generado:", ruta)
    print("Combinaciones aprendidas:", len(filas))
    print("Resultados reales utilizados:", registros_validos)
    print("Registros ignorados:", registros_ignorados)

    return filas


def probar_motor_aprendizaje():
    """
    Prueba rápida sin depender del CSV oficial.
    """

    senal = {
        "activo": "EURUSD",
        "direccion": "CALL",
        "familia_setup": "PULLBACK",
        "tipo_mercado": "TENDENCIA",
        "estado_tendencia": "FUERTE",
    }

    clave = _clave(senal)

    memoria = {
        clave: {
            "total": 12,
            "wins": 8,
            "losses": 4,
            "winrate": 66.67,
        }
    }

    resultado = evaluar_aprendizaje_historico(
        senal=senal,
        memoria=memoria,
    )

    assert resultado["aprendizaje_encontrado"] is True
    assert resultado["muestra_historica"] == 12
    assert 0 < resultado["ajuste_confianza_aprendizaje"] <= AJUSTE_MAXIMO

    return resultado