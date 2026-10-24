"""Auditoría retrospectiva de cierres; nunca decide ni bloquea operaciones.

El historial anterior tiene columnas de contexto vacías, pero conserva las
etiquetas del diagnóstico en ``razon``. Solo se reconstruyen etiquetas
expresamente presentes y se registra si proceden de texto o campo estructurado.
No se modifica el archivo histórico.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path


PATRONES = {
    "tipo_mercado": re.compile(
        r"\bMERCADO:\s*(TENDENCIA_ALCISTA|TENDENCIA_BAJISTA|RANGO|COMPRESION|EXPANSION|INDEFINIDO)\b",
        re.I,
    ),
    "calidad_mercado": re.compile(r"\bCALIDAD MERCADO:\s*([A-Z_]+)\b", re.I),
    "estado_tendencia": re.compile(r"\bTENDENCIA AVANZADA:\s*([A-Z_]+)\b", re.I),
}

ETIQUETAS_DIAGNOSTICO = {
    "VALIDACION_MERCADO": "VALIDACIÓN MERCADO:",
    "ACCION_PRECIO": "ACCION PRECIO:",
    "ZONA_SR": "ZONA SR:",
}


def diagnosticos_historicos(fila):
    """Extrae motivos literales entre secciones, no interpreta señales futuras."""
    texto = str(fila.get("razon") or "")
    etiquetas = tuple(ETIQUETAS_DIAGNOSTICO.values()) + ("RUPTURA:",)
    salida = {}
    for nombre, etiqueta in ETIQUETAS_DIAGNOSTICO.items():
        inicio = texto.find(etiqueta)
        if inicio < 0:
            salida[nombre] = "SIN_DATOS"
            continue
        comienzo = inicio + len(etiqueta)
        finales = [texto.find(", " + otra, comienzo) for otra in etiquetas if otra != etiqueta]
        finales = [indice for indice in finales if indice >= 0]
        fin = min(finales) if finales else len(texto)
        salida[nombre] = texto[comienzo:fin].strip() or "SIN_DATOS"
    return salida


def agrupar_cierres_por_diagnostico(filas, minimo=1):
    """Analiza argumentos técnicos almacenados en cierres, sin generar vetos."""
    grupos = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
    for fila in filas:
        if not isinstance(fila, dict) or str(fila.get("estado") or "").upper() != "CERRADA":
            continue
        try:
            pnl = float(fila.get("resultado"))
        except (TypeError, ValueError):
            continue
        if pnl == 0:
            continue
        motivos = diagnosticos_historicos(fila)
        for dimension, valor in motivos.items():
            clave = (dimension, valor)
            dato = grupos[clave]
            dato["wins" if pnl > 0 else "losses"] += 1
            dato["pnl"] += pnl
    salida = []
    for (dimension, valor), dato in grupos.items():
        n = dato["wins"] + dato["losses"]
        if n >= minimo:
            salida.append({
                "dimension": dimension, "valor": valor, "total": n,
                "wins": dato["wins"], "losses": dato["losses"],
                "wr": round(100 * dato["wins"] / n, 2),
                "pnl": round(dato["pnl"], 2),
            })
    return sorted(salida, key=lambda x: (-x["total"], x["dimension"], x["valor"]))


def contexto_historico(fila):
    """Prioriza campos estructurados; fallback literal y auditable al texto."""
    razon = str(fila.get("razon") or "")
    contexto = {}
    origen = {}
    for campo, patron in PATRONES.items():
        estructurado = str(fila.get(campo) or "").strip().upper()
        coincidencia = patron.search(razon) if not estructurado else None
        contexto[campo] = estructurado or (
            coincidencia.group(1).upper() if coincidencia else "SIN_DATOS"
        )
        origen[campo] = (
            "ESTRUCTURADO" if estructurado else "TEXTO_LITERAL" if coincidencia else "AUSENTE"
        )
    return contexto, origen


def agrupar_cierres_por_contexto(filas, minimo=1):
    """Solo cierres WIN/LOSS con PNL numérico; no usa escenarios hipotéticos."""
    grupos = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0, "texto_literal": 0})
    descartadas = 0
    for fila in filas:
        if not isinstance(fila, dict) or str(fila.get("estado") or "").upper() != "CERRADA":
            descartadas += 1
            continue
        try:
            pnl = float(fila.get("resultado"))
        except (TypeError, ValueError):
            descartadas += 1
            continue
        if pnl == 0:
            descartadas += 1
            continue
        contexto, origen = contexto_historico(fila)
        clave = (
            str(fila.get("patron") or "SIN_PATRON").strip().upper(),
            str(fila.get("direccion") or "SIN_DIRECCION").strip().upper(),
            contexto["tipo_mercado"],
        )
        dato = grupos[clave]
        dato["wins" if pnl > 0 else "losses"] += 1
        dato["pnl"] += pnl
        dato["texto_literal"] += origen["tipo_mercado"] == "TEXTO_LITERAL"

    salida = []
    for (patron, direccion, mercado), valores in grupos.items():
        n = valores["wins"] + valores["losses"]
        if n >= minimo:
            salida.append({
                "patron": patron, "direccion": direccion, "mercado": mercado,
                "total": n, "wins": valores["wins"], "losses": valores["losses"],
                "wr": round(100 * valores["wins"] / n, 2),
                "pnl": round(valores["pnl"], 2),
                "contexto_recuperado_texto": valores["texto_literal"],
            })
    return sorted(salida, key=lambda x: (-x["total"], x["patron"])), descartadas


def imprimir_informe_historial(ruta="historial_bot.csv", minimo=1):
    with Path(ruta).open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    grupos, descartadas = agrupar_cierres_por_contexto(filas, minimo=minimo)
    print("===== HISTORIAL REAL CERRADO: CONTEXTO RECUPERADO =====")
    print("Muestra histórica, descriptiva; no extrapolar ni activar bloqueos.")
    print("Registros descartados (no cerrados, sin PNL o empatados):", descartadas)
    for g in grupos:
        print(
            g["patron"], "|", g["direccion"], "|", g["mercado"],
            "| n:", g["total"], "| W:", g["wins"], "| L:", g["losses"],
            "| WR:", g["wr"], "| PNL:", g["pnl"],
            "| contexto desde texto:", g["contexto_recuperado_texto"],
        )
    print("===== DIAGNOSTICOS TECNICOS PRE-ENTRADA DE LOS CIERRES =====")
    for d in agrupar_cierres_por_diagnostico(filas, minimo=max(3, minimo)):
        print(
            d["dimension"], "|", d["valor"],
            "| n:", d["total"], "| W:", d["wins"],
            "| L:", d["losses"], "| PNL:", d["pnl"],
        )


if __name__ == "__main__":
    imprimir_informe_historial()
