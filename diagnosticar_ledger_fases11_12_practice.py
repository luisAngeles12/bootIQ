"""F11/F12: diagnostico read-only del historial oficial frente a ledger de consistencia.

No transforma operaciones ni infiere una fecha de cierre ausente.
No importa config, credenciales, bot ni broker.
"""
import argparse
import csv
import json
from pathlib import Path

CAMPOS_LEDGER = (
    "order_id", "fecha_cierre", "resultado", "neto", "familia", "tipo_cuenta"
)
CAMPOS_HISTORIAL = ("order_id", "fecha", "estado", "resultado",
                    "modo_cuenta_configurado", "patron", "familia_setup")


def diagnosticar(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        return {"estado": "HISTORIAL_NO_DISPONIBLE", "apto_para_evaluar": False,
                "ruta": str(ruta), "faltantes": list(CAMPOS_LEDGER)}
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        campos = lector.fieldnames or []
        duplicadas = sorted({c for c in campos if campos.count(c) > 1})
        filas = list(lector)
    if duplicadas:
        return {"estado": "ENCABEZADOS_DUPLICADOS", "apto_para_evaluar": False,
                "ruta": str(ruta), "columnas_duplicadas": duplicadas}
    if any(None in fila for fila in filas):
        return {"estado": "FILAS_CON_COLUMNAS_EXTRA", "apto_para_evaluar": False,
                "ruta": str(ruta)}
    faltantes = [c for c in CAMPOS_LEDGER if c not in campos]
    cerradas = sum(str(f.get("estado") or "").upper() == "CERRADA" for f in filas)
    return {
        "estado": "COMPATIBLE_ESTRUCTURALMENTE" if not faltantes
                  else "EVIDENCIA_LEDGER_INSUFICIENTE",
        "apto_para_evaluar": not faltantes and bool(filas),
        "ruta": str(ruta),
        "filas": len(filas),
        "cerradas_marcadas": cerradas,
        "campos_presentes": [c for c in CAMPOS_LEDGER if c in campos],
        "faltantes": faltantes,
        "campos_historial_oficial_presentes": [
            c for c in CAMPOS_HISTORIAL if c in campos
        ],
        "advertencias": [
            "fecha del historial es fecha de registro; no prueba fecha de cierre",
            "resultado numerico puede ser PnL, no etiqueta WIN/LOSS",
            "modo_cuenta_configurado no demuestra por si solo cuenta broker PRACTICE",
            "patron/familia_setup no garantiza familia validada sin trazabilidad",
            "estructura compatible no confirma liquidacion ni conciliacion con broker",
        ],
        "autoriza_real": False,
        "validacion_prospectiva_confirmada": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("historial_csv", type=Path)
    args = p.parse_args()
    print(json.dumps(diagnosticar(args.historial_csv),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
