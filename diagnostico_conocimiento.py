import json
from config_fase4 import RUTA_BASE_CONOCIMIENTO


def main():
    with open(RUTA_BASE_CONOCIMIENTO, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n===== DIAGNÓSTICO BASE CONOCIMIENTO =====")

    niveles = data.get("niveles", {})

    for nivel, contenido in niveles.items():
        print("\n---", nivel, "---")

        for grupo in ["fuertes", "debiles", "neutras"]:
            items = contenido.get(grupo, {})

            print(grupo.upper(), ":", len(items))

            for clave, stats in items.items():
                print(
                    clave,
                    "| total:", stats.get("total"),
                    "| winrate:", stats.get("winrate"),
                    "| peso:", stats.get("peso")
                )


if __name__ == "__main__":
    main()