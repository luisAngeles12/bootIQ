"""Puerta de preparacion tecnica para el cerebro reconstruido de BootIQ V3.

No autoriza ordenes PRACTICE ni REAL; no conecta al broker.
Cada captura se evalua aisladamente, sin cargar memoria historica.
"""
from contexto_mercado_fresco import consolidar_minutos
from paridad_sombra_practice import comprobar_paridad_recepcion_1s
from comparar_estrategias_frescas import resumen_comparativa

ESTRATEGIAS = ("RUPTURA_RETEST", "RECHAZO_ZONA", "CONTINUACION_TENDENCIA")


def diagnosticar_preparacion(velas):
    motivos = []
    if not isinstance(velas, dict) or not velas:
        return {
            "estado": "NO_APTO_PARA_PRUEBA_OPERATIVA", "motivos": ["SIN_VELAS"],
            "minutos_completos": 0, "operaciones_autorizadas": False,
        }
    marcas = sorted(velas)
    if any(b - a != 1 for a, b in zip(marcas, marcas[1:])):
        motivos.append("HUECO_ENTRE_VELAS")
    minutos = consolidar_minutos(velas)
    if len(minutos) < 24:
        motivos.append("CONTEXTO_MENOR_24_MINUTOS")
    if any(b["from"] - a["from"] != 60 for a, b in zip(minutos, minutos[1:])):
        motivos.append("HUECO_ENTRE_MINUTOS")
    latencias = {t: vela.get("_latencia_primera_recepcion_s")
                 for t, vela in velas.items()}
    paridad = comprobar_paridad_recepcion_1s(velas, latencias)
    if paridad["paridad"] is not True:
        motivos.append("PARIDAD_NO_DEMOSTRADA")
    comparativa = resumen_comparativa(velas) if len(minutos) >= 24 else {}
    for estrategia in ESTRATEGIAS:
        resultado = comparativa.get(estrategia)
        # Solo WIN/LOSS hipoteticos con recepcion causal verificada cuentan
        # para el minimo. Los totales sin verificar nunca desbloquean la puerta.
        if not resultado or resultado["resultados_con_tiempo_verificado"] < 15:
            motivos.append("MUESTRA_INSUFICIENTE_" + estrategia)
        if resultado and (resultado["sin_latencia_registrada"]
                          or resultado["detecciones_tardias"]
                          or resultado["latencia_invalida"]
                          or resultado["WIN"] + resultado["LOSS"]
                          != resultado["resultados_con_tiempo_verificado"]):
            motivos.append("TIEMPOS_SIN_VALIDAR_" + estrategia)
    return {
        "estado": ("BASE_TECNICA_PARA_MAS_PRUEBAS_SOMBRA" if not motivos
                   else "NO_APTO_PARA_PRUEBA_OPERATIVA"),
        "motivos": sorted(set(motivos)),
        "velas_1s": len(velas),
        "minutos_completos": len(minutos),
        "paridad": paridad,
        "estrategias": comparativa,
        "operaciones_autorizadas": False,
        "advertencia": "NO_ES_VALIDACION_ESTADISTICA_NI_AUTORIZACION_DE_TRADING",
    }
