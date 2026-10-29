"""Arbitro de candidatos de estrategia: solo diagnostico, NUNCA ordenes.

No atribuye confianza ficticia por sumar indicadores correlacionados.
"""
ESTRATEGIAS_CONOCIDAS = frozenset({
    "RUPTURA_RETEST", "RECHAZO_ZONA", "CONTINUACION_TENDENCIA"
})


def arbitrar_candidatos(candidatos, estado_mercado):
    salida = {
        "estado": "NO_OPERAR",
        "direccion": None,
        "motivo": None,
        "estrategias": [],
        "operable": False,
    }
    if estado_mercado in ("SUCIO", "CAOTICO", "SIN_DATOS", "MIXTO"):
        salida["motivo"] = "CONTEXTO_BLOQUEADO"
        return salida
    if estado_mercado not in ("RANGO", "TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"):
        salida["motivo"] = "CONTEXTO_DESCONOCIDO"
        return salida
    if not isinstance(candidatos, (list, tuple)):
        salida["motivo"] = "CANDIDATOS_INVALIDOS"
        return salida
    if len(candidatos) != len(ESTRATEGIAS_CONOCIDAS):
        salida["motivo"] = "CATALOGO_INCOMPLETO"
        return salida
    nombres = [c.get("estrategia") for c in candidatos if isinstance(c, dict)]
    if len(nombres) != len(candidatos) or set(nombres) != ESTRATEGIAS_CONOCIDAS:
        salida["motivo"] = "CATALOGO_INVALIDO"
        return salida
    activos = []
    for candidato in candidatos:
        if candidato.get("operable") is not False:
            salida["motivo"] = "AUTORIZACION_INESPERADA"
            return salida
        if candidato.get("estado") == "CANDIDATO_SOMBRA":
            if candidato.get("direccion") not in ("call", "put"):
                salida["motivo"] = "DIRECCION_INVALIDA"
                return salida
            activos.append(candidato)
        elif candidato.get("estado") != "SIN_SENAL":
            salida["motivo"] = "ESTADO_INVALIDO"
            return salida
    if not activos:
        salida["motivo"] = "NINGUNA_ESTRATEGIA_CONFIRMADA"
        return salida
    direcciones = {x["direccion"] for x in activos}
    if len(direcciones) != 1:
        salida["motivo"] = "CONFLICTO_DE_DIRECCIONES"
        salida["estrategias"] = sorted(x["estrategia"] for x in activos)
        return salida
    salida["estado"] = "CANDIDATO_SOMBRA_NO_OPERABLE"
    salida["direccion"] = direcciones.pop()
    salida["motivo"] = ("UNA_ESTRATEGIA" if len(activos) == 1
                         else "COINCIDENCIA_NO_INDEPENDIENTE")
    salida["estrategias"] = sorted(x["estrategia"] for x in activos)
    return salida
