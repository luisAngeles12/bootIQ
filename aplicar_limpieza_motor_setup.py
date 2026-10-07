from pathlib import Path
import re
import shutil

ARCHIVO = Path("motor_setup.py")
BACKUP = Path("motor_setup_backup_pre_contextual.py")

if not ARCHIVO.exists():
    raise FileNotFoundError("No encuentro motor_setup.py en esta carpeta.")

texto = ARCHIVO.read_text(encoding="utf-8")

requeridos = [
    "def calcular_confianza_setup_por_capas(",
    "def clasificar_setup(",
    "def clasificar_setup_estrategico(",
    "def construir_setup_completo(",
    "def ensamblar_setup_completo(",
]
faltantes = [x for x in requeridos if x not in texto]
if faltantes:
    raise RuntimeError(f"Faltan piezas esperadas: {faltantes}")

if not BACKUP.exists():
    shutil.copy2(ARCHIVO, BACKUP)

bandera = '''
# ============================================================
# SETUP CONTEXTUAL — MODO DIAGNÓSTICO
# ============================================================
SETUP_PUNTUACION_CONTEXTUAL_OPERATIVA = False

'''

if "SETUP_PUNTUACION_CONTEXTUAL_OPERATIVA" not in texto:
    texto = texto.replace("def _txt(v):\n", bandera + "def _txt(v):\n", 1)

patron = re.compile(
r"def clasificar_setup\(senal\):\n.*?\n\n\ndef aplicar_setup_decision",
    re.DOTALL,
)

nueva_funcion = '''def clasificar_setup(senal):
    identidad_setup = identificar_setup(senal)
    familia_setup = identidad_setup["familia_setup"]
    subtipo_setup = identidad_setup["subtipo_setup"]
    protocolo_sugerido = identidad_setup["protocolo_sugerido"]

    confianza_diagnostico, razones = calcular_confianza_setup_por_capas(
        senal,
        identidad_setup,
    )

    nivel_diagnostico, estado_diagnostico = _nivel_estado_desde_confianza(
        confianza_diagnostico
    )

    direccion = _txt(senal.get("direccion", ""))
    accion_precio = _txt(senal.get("accion_precio", ""))

    if (
        "CALL_RESISTENCIA_CERCA_SIN_RUPTURA" in accion_precio
        and direccion == "CALL"
    ):
        protocolo_sugerido = "PROTOCOLO_RUPTURA_RESISTENCIA"

    if SETUP_PUNTUACION_CONTEXTUAL_OPERATIVA:
        confianza_operativa = confianza_diagnostico
        nivel_operativo = nivel_diagnostico
        estado_operativo = estado_diagnostico
    else:
        confianza_operativa = 50.0
        nivel_operativo = "MEDIO"
        estado_operativo = "PENDIENTE_CONFIRMACION"

    return {
        "familia_setup": familia_setup,
        "subtipo_setup": subtipo_setup,
        "protocolo_sugerido": protocolo_sugerido,
        "nivel_setup": nivel_operativo,
        "estado_setup": estado_operativo,
        "confianza_setup": confianza_operativa,
        "nivel_setup_diagnostico": nivel_diagnostico,
        "estado_setup_diagnostico": estado_diagnostico,
        "confianza_setup_diagnostico": round(confianza_diagnostico, 2),
        "razones_clasificador_setup": " | ".join(razones),
        "setup_puntuacion_contextual_operativa": SETUP_PUNTUACION_CONTEXTUAL_OPERATIVA,
    }


def aplicar_setup_decision'''

texto, cantidad = patron.subn(nueva_funcion, texto, count=1)
if cantidad != 1:
    raise RuntimeError(f"No pude sustituir clasificar_setup(): {cantidad}")

for requerido in [
    "def clasificar_setup_estrategico(",
    "def construir_setup_completo(",
    "def ensamblar_setup_completo(",
    '"calidad_setup"',
    '"modo_entrada"',
    '"riesgo_estructural_critico_setup"',
    '"requiere_ruptura_setup"',
    '"requiere_confirmacion_setup"',
]:
    if requerido not in texto:
        raise RuntimeError(f"Validación final falló: {requerido}")

compile(texto, str(ARCHIVO), 'exec')
ARCHIVO.write_text(texto, encoding="utf-8")

print("motor_setup.py actualizado correctamente.")
print(f"Backup creado/conservado: {BACKUP}")
print("confianza_setup operativo = 50.0")
print("nivel_setup operativo = MEDIO")
print("estado_setup operativo = PENDIENTE_CONFIRMACION")