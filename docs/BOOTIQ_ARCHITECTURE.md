# BootIQ Architecture

## Objetivo

BootIQ debe evolucionar hacia una arquitectura por responsabilidades, donde cada módulo tenga una función clara y no existan múltiples motores tomando decisiones finales sobre la misma señal.

La regla principal es:

> Muchos módulos pueden aportar evidencia, pero solo un motor debe tomar la decisión final.

---

## Capas del sistema

### 1. Core

Archivos base del sistema.

Responsabilidad:

- configuración general;
- estado global;
- conexión;
- utilidades compartidas.

Archivos actuales:

- `config.py`
- `estado.py`
- `conexion.py`
- `utils.py`

Estos archivos no deben decidir operaciones.

---

### 2. Mercado

Responsabilidad:

- leer velas;
- calcular indicadores;
- detectar contexto de mercado;
- analizar soporte, resistencia, zonas y price action.

Archivos actuales:

- `mercado.py`
- `indicadores.py`
- `zonas.py`
- `price_action.py`
- `price_action_profesional.py`
- `contexto_mercado.py`
- `lector_contexto.py`

Estos módulos solo deben describir el mercado. No deben decidir si se opera o no.

---

### 3. Estrategias

Responsabilidad:

- detectar oportunidades candidatas;
- crear señales base;
- describir el patrón o setup encontrado.

Archivos actuales:

- `estrategia.py`
- `scoring_estrategia.py`
- `diagnostico_estrategia.py`

Las estrategias pueden proponer señales, pero no deben ser el punto final de decisión.

---

### 4. Motores de evidencia

Responsabilidad:

- aportar análisis complementario sobre una señal;
- enriquecer la señal;
- calcular evidencia técnica.

Archivos actuales:

- `motor_setup.py`
- `motor_consenso.py`
- `motor_confirmacion.py`
- `motor_protocolos.py`
- `normalizador.py`

Estos motores no deben bloquear definitivamente. Deben producir datos para el motor unificado.

---

### 5. Aprendizaje

Responsabilidad:

- analizar resultados históricos;
- detectar patrones buenos o malos;
- aportar memoria estadística.

Archivos actuales:

- `motor_adaptativo.py`
- `motor_aprendizaje_historico.py`
- `auditoria_estadistica.py`
- `base_conocimiento.py`

La capa de aprendizaje no debe decidir sola. Debe aportar evidencia histórica.

---

### 6. Fase 4

Responsabilidad futura:

- aportar evaluación histórica;
- aportar confianza estadística;
- señalar riesgos.

Archivos actuales:

- `config_fase4.py`
- `evaluador_fase4.py`

Fase 4 no debe ser un segundo motor final de bloqueo. Su salida debe alimentar el motor de decisión unificado.

## Conexión y reconexión

Las esperas del ciclo WebSocket deben tener límites explícitos: apertura,
cierre del hilo lector, respuesta de perfil tras enviar SSID y sincronización
de tiempo del servidor. Si el socket no se recupera dentro del límite, la
conexión debe fallar con una razón visible y permitir que el controlador de
reconexión inicie otro intento, sin dejar hilos antiguos activos.

El escáner no debe iniciarse hasta recibir una inicialización válida con
activos tanto binary como turbo. Si IQ Option no responde, el arranque conserva
el proceso y reintenta con espera creciente; no debe sustituir esos datos por
IDs estáticos o potencialmente obsoletos.
Un timeout de OPCODE por sí solo no justifica abrir una sesión nueva si el
WebSocket actual sigue conectado: la reconexión se reserva para una conexión
que realmente se haya perdido.

---

### 7. Decisión

Responsabilidad:

- recibir evidencia de todas las capas;
- producir una única decisión final.

Archivos actuales:

- `decision_bootiq.py`
- `motor_decision_unificado.py`

Esta debe ser la única capa que decida:

- `OPERAR`
- `ESPERAR`
- `NO_OPERAR`

---

## Contrato central

El contrato central será `DecisionBootIQ`.

Todas las capas deben escribir en una sección específica:

- `identidad`
- `estrategia`
- `mercado`
- `price_action`
- `setup`
- `consenso`
- `protocolo`
- `fase4`
- `decision_unificada`
- `resultado`

Ningún módulo debe escribir fuera de su responsabilidad.

---

## Regla de migración

No se moverán archivos directamente sin compatibilidad.

Orden correcto:

1. Crear estructura de carpetas.
2. Crear documentación.
3. Crear archivos `__init__.py`.
4. Mover un archivo pequeño.
5. Corregir imports.
6. Ejecutar:

```bash
python -m py_compile archivo.py
python backtest_bot_real.py
```

## Ventana temporal LIVE

Para velas de un minuto, BootIQ solo puede enviar una orden durante
los segundos 0 a 30 de la vela de entrada y reserva los últimos dos
segundos como margen para el envío a IQ. La validación final usa el
timestamp del servidor IQ y rechaza tanto las entradas fuera de ese
margen como las señales referidas a una vela ya cerrada. Una señal de
protocolo puede esperar las confirmaciones previstas por su protocolo,
pero no puede ejecutar una confirmación pasada en una vela posterior.

La precarga del universo, las consultas de balance, la reconciliación
de resultados y los reportes se programan fuera de la ventana de
entrada. El análisis LIVE usa la cache preparada y reserva los últimos
segundos para validar y enviar órdenes. Esta regla limita el momento de
entrada; no garantiza una tasa de acierto ni una cantidad determinada
de operaciones.