"""Preflight offline de BootIQ V3: no conecta con IQ Option ni autoriza ordenes.

El modo sombra puede generar evidencia aunque la operativa permanezca bloqueada.
Este informe NO certifica rentabilidad ni reemplaza el Cerebro.
"""
import ast
import json
import os
from pathlib import Path


def _constantes_config(path):
    codigo = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    valores = {}
    for node in codigo.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        valores[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError, RecursionError):
                        pass
    return valores


def evaluar_preflight(raiz=".", *, ruta_memoria=None, config=None):
    raiz = Path(raiz)
    cfg = _constantes_config(raiz / "config.py") if config is None else dict(config)
    motivos = []
    if cfg.get("MODO_CUENTA") != "PRACTICE":
        motivos.append("MODO_CUENTA_NO_PRACTICE")
    if cfg.get("CONTROL_BLOQUES_20_PRACTICE") is not True:
        motivos.append("CONTROL_BLOQUES_20_INACTIVO")
    if cfg.get("PERMITIR_BOOTSTRAP_SIN_MEMORIA") is not False:
        motivos.append("BOOTSTRAP_SIN_MEMORIA_ACTIVO")
    if ruta_memoria is None:
        ruta_memoria = os.getenv(
            "BOOTIQ_RUTA_APRENDIZAJE",
            "aprendizaje_historico_bootiq_F4_CC2.csv",
        )
    ruta = Path(ruta_memoria)
    if not ruta.is_absolute():
        ruta = raiz / ruta
    candidata = raiz / "experimentos_fase5" / "memoria_ejecutadas_train_candidata.csv"
    if ruta.resolve() == candidata.resolve():
        motivos.append("MEMORIA_EXPERIMENTAL_COMO_OFICIAL")
    if not ruta.is_file():
        motivos.append("MEMORIA_OFICIAL_AUSENTE")
    elif ruta.stat().st_size == 0:
        motivos.append("MEMORIA_OFICIAL_VACIA")
    modo_seguro = all(c not in motivos for c in (
        "MODO_CUENTA_NO_PRACTICE",
        "CONTROL_BLOQUES_20_INACTIVO",
        "BOOTSTRAP_SIN_MEMORIA_ACTIVO",
        "MEMORIA_EXPERIMENTAL_COMO_OFICIAL",
    ))
    return {
        "tipo": "PREFLIGHT_INFORMATIVO_BOOTIQ_V3",
        "modo_cuenta": cfg.get("MODO_CUENTA"),
        "seguridad_practice": modo_seguro,
        "auditoria_sombra_posible": modo_seguro,
        "memoria_oficial_presente": ruta.is_file() and ruta.stat().st_size > 0,
        "memoria_experimental_promovida": "MEMORIA_EXPERIMENTAL_COMO_OFICIAL" in motivos,
        "operativa_autorizada": False,
        "rentabilidad_validada": False,
        "motivos": motivos,
        "nota": "No evalua calidad estadistica, paridad del broker ni PnL. No autoriza trading.",
    }


def main():
    print(json.dumps(evaluar_preflight(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
