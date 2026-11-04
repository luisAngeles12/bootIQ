"""Bitacora separada de intentos de ronda para auditoria en sombra.

No altera decisiones, memoria, estadisticas ni archivo historico CSV.
La pertenencia se registra al generar la candidata, NO se infiere del
minuto, porque puede haber reintentos de la misma vela.
"""
import json
from collections import defaultdict
from pathlib import Path

RUTA = "trazabilidad_rondas_sombra.jsonl"
EVENTOS = frozenset(("INICIO", "CANDIDATA", "DESCARTADA",
                     "OMITIDA_PREANALISIS", "ANALISIS_VALIDADO"))


def registrar_evento(evento, run_id, intento, vela_ronda, *, candidato_id="", ruta=RUTA):
    if evento not in EVENTOS:
        raise ValueError("EVENTO_SOMBRA_INVALIDO")
    if not str(run_id).strip() or int(intento) < 1 or int(vela_ronda) < 1:
        return False
    if evento == "CANDIDATA" and not candidato_id:
        return False
    fila = {
        "evento": evento, "run_id": str(run_id),
        "intento": int(intento), "vela_ronda": int(vela_ronda),
        "candidato_id": str(candidato_id or ""),
    }
    p = Path(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(fila, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def auditar_intentos(ruta=RUTA):
    """Conservador: solo una pertenencia y un cierre validado es confiable."""
    p = Path(ruta)
    if not p.exists():
        return {
            "intentos": 0, "candidatas_distintas": 0,
            "estados": {}, "ids_por_estado": {},
        }
    intentos = {}
    referencias = defaultdict(set)
    for numero, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        e = json.loads(linea)
        if e["evento"] not in EVENTOS:
            raise ValueError("EVENTO_DESCONOCIDO_EN_LINEA_" + str(numero))
        clave = (str(e["run_id"]), int(e["intento"]), int(e["vela_ronda"]))
        registro = intentos.setdefault(clave, {
            "comienzo": 0, "cierres": [], "ids": set(),
        })
        if e["evento"] == "INICIO":
            registro["comienzo"] += 1
        elif e["evento"] == "CANDIDATA":
            registro["ids"].add(str(e["candidato_id"]))
            referencias[str(e["candidato_id"])].add(clave)
        else:
            registro["cierres"].append(e["evento"])
    estados = {}
    for clave, item in intentos.items():
        if item["comienzo"] == 1 and len(item["cierres"]) == 1:
            estados[clave] = item["cierres"][0]
        else:
            estados[clave] = "INCOMPLETO_O_AMBIGUO"
    ids_por_estado = {}
    for candidato, claves in referencias.items():
        if len(claves) != 1:
            estado = "AMBIGUO_MULTIPLES_INTENTOS"
        else:
            estado = estados[next(iter(claves))]
        ids_por_estado[candidato] = estado
    conteo = {}
    for estado in estados.values():
        conteo[estado] = conteo.get(estado, 0) + 1
    return {
        "intentos": len(intentos),
        "candidatas_distintas": len(referencias),
        "estados": dict(sorted(conteo.items())),
        "ids_por_estado": ids_por_estado,
    }
