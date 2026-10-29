"""Auditoria integral de decisiones de contexto y arbitro en sombra.

Resume bloqueos reales del algoritmo; nunca implica senales ejecutables.
"""
from collections import Counter


def resumir_decisiones_sombra(decisiones):
    """Cierres: [(fin_utc, diagnostico_cierre), ...], un cierre por minuto."""
    marcas = set()
    contextos = Counter()
    motivos = Counter()
    candidatos = Counter()
    direcciones = Counter()
    for fin, diagnostico in decisiones:
        if not isinstance(fin, int) or fin in marcas:
            raise ValueError("CIERRE_DUPLICADO_O_INVALIDO")
        marcas.add(fin)
        contexto = diagnostico["contexto"]
        arbitro = diagnostico["arbitraje"]
        estrategias = diagnostico["candidatos"]
        if contexto["operable"] is not False or arbitro["operable"] is not False:
            raise RuntimeError("AUTORIZACION_INESPERADA")
        if any(x.get("operable") is not False for x in estrategias):
            raise RuntimeError("ESTRATEGIA_OPERABLE_INESPERADA")
        if len(estrategias) != 3:
            raise RuntimeError("CATALOGO_INCOMPLETO")
        estado = contexto["estado"]
        if estado in ("SUCIO", "CAOTICO", "MIXTO", "SIN_DATOS"):
            if arbitro["estado"] != "NO_OPERAR":
                raise RuntimeError("CONTEXTO_PROHIBIDO_NO_BLOQUEADO")
        contextos[estado] += 1
        motivos[arbitro["motivo"]] += 1
        for estrategia in estrategias:
            if estrategia["estado"] == "CANDIDATO_SOMBRA":
                candidatos[estrategia["estrategia"]] += 1
        if arbitro["estado"] == "CANDIDATO_SOMBRA_NO_OPERABLE":
            direcciones[arbitro["direccion"]] += 1
    return {
        "minutos_evaluados": len(marcas),
        "contextos": dict(sorted(contextos.items())),
        "motivos_arbitro": dict(sorted(motivos.items())),
        "candidatos_por_estrategia": dict(sorted(candidatos.items())),
        "coincidencias_sombra_por_direccion": dict(sorted(direcciones.items())),
        "operaciones": 0,
        "operaciones_autorizadas": False,
        "advertencia": "DIAGNOSTICO_NO_ES_WINRATE_NI_AUTORIZACION",
    }
