import re
import unicodedata


def quitar_acentos(texto):
    texto = str(texto)
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )
    return texto


def normalizar_texto(valor, defecto="sin_dato"):
    if valor is None:
        return defecto

    texto = str(valor).strip()

    if not texto:
        return defecto

    texto = quitar_acentos(texto)
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = re.sub(r"_+", "_", texto)
    texto = texto.strip("_")

    return texto if texto else defecto


def normalizar_direccion(valor):
    texto = normalizar_texto(valor)

    if texto in ["call", "compra", "alcista", "buy"]:
        return "call"

    if texto in ["put", "venta", "bajista", "sell"]:
        return "put"

    return texto


def normalizar_evidencia(evidencia):
    evidencia = evidencia.copy()

    campos_texto = [
        "activo",
        "direccion",
        "patron",
        "tipo_mercado",
        "calidad_mercado",
        "estado_tendencia",
        "direccion_tendencia",
        "accion_precio",
        "pa_tipo",
        "pa_direccion",
        "nivel_consenso",
        "base_estrategia",
        "tipo_ruptura",
    ]

    for campo in campos_texto:
        evidencia[campo] = normalizar_texto(evidencia.get(campo))

    evidencia["direccion"] = normalizar_direccion(evidencia.get("direccion"))

    return evidencia


def construir_clave_normalizada(datos, campos):
    partes = []

    for campo in campos:
        valor = normalizar_texto(datos.get(campo))
        if campo == "direccion":
            valor = normalizar_direccion(valor)

        partes.append(f"{campo}:{valor}")

    return " + ".join(partes)


if __name__ == "__main__":
    pruebas = [
        "CHOCH bajista",
        " Choch   Bajista ",
        "reacción vendedora en resistencia",
        "TENDENCIA_BAJISTA",
        "PUT",
        "CALL",
    ]

    print("\n===== PRUEBA NORMALIZADOR =====")
    for p in pruebas:
        print(p, "=>", normalizar_texto(p))