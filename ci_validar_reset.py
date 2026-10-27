"""Validaciones sin bróker para la rama de reinicio BootIQ."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def validar():
    archivos = [p for p in RAIZ.rglob("*") if p.is_file()
                and ".git" not in p.parts and "__pycache__" not in p.parts]
    datos = [p for p in archivos
             if p.suffix.lower() in (".csv", ".json", ".log", ".d55tmp")]
    assert not datos, "Datos antiguos presentes: " + repr(datos[:10])

    backtests = sorted(p.name for p in RAIZ.glob("backtest*.py"))
    assert backtests == ["backtest_bot_real.py"], backtests

    codigo = sorted(p for p in archivos if p.suffix == ".py")
    for ruta in codigo:
        ast.parse(ruta.read_text(encoding="utf-8-sig"), filename=str(ruta))

    cfg = ast.parse((RAIZ / "config.py").read_text(encoding="utf-8"))
    modos = [n.value.value for n in cfg.body
             if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "MODO_CUENTA"
                     for t in n.targets)
             and isinstance(n.value, ast.Constant)]
    assert modos == ["PRACTICE"], modos

    print("RESET_VALIDADO", "python:", len(codigo),
          "backtests:", backtests, "csv/json/log:", len(datos),
          "modo:", modos[0])


if __name__ == "__main__":
    validar()
