# Contexto de Conversación en Triage

## Resumen

El endpoint de **triage/interpret** ahora mantiene y usa el historial de conversación para acumular síntomas a través de múltiples turnos, mejorando significativamente la precisión de la clasificación.

## Problema Resuelto

### Antes (Sin Historial)

```
Turno 1:
Usuario: "Tengo fiebre alta"
Sistema: Capa 2 - Médico a domicilio

Turno 2:
Usuario: "Y me duele la cabeza"
Sistema: Capa 2 - Médico a domicilio (olvida la fiebre ❌)

Turno 3:
Usuario: "Y el cuello está rígido"
Sistema: Capa 2 - Médico a domicilio (olvida fiebre + dolor de cabeza ❌)
```

**Problema**: El sistema no reconoce la combinación peligrosa de síntomas (fiebre + dolor de cabeza + rigidez de cuello = posible meningitis).

### Después (Con Historial)

```
Turno 1:
Usuario: "Tengo fiebre alta"
Sistema: Capa 2 - Médico a domicilio
Guarda: fiebre alta

Turno 2:
Usuario: "Y me duele la cabeza"
Sistema: Lee historial → fiebre alta
Sistema: Acumula → fiebre alta + dolor de cabeza
Sistema: Capa 2 - Médico a domicilio (aún no es emergencia)
Guarda: fiebre alta, dolor de cabeza

Turno 3:
Usuario: "Y el cuello está rígido"
Sistema: Lee historial → fiebre alta + dolor de cabeza
Sistema: Acumula → fiebre alta + dolor de cabeza + rigidez de cuello
Sistema: RAG → "Esta combinación puede indicar meningitis"
Sistema: Capa 4 - EMERGENCIA ✅
```

**Solución**: El sistema reconoce patrones peligrosos acumulando síntomas.

## Implementación

### 1. Recuperación de Historial

```python
# Retrieve conversation history from session
conversation_summary = ""
try:
    session_manager = get_session_manager()
    conversation_summary = session_manager.get_conversation_summary(req.user_id)
    if conversation_summary:
        print(f"Found conversation history for user {req.user_id} in triage")
except Exception as e:
    print(f"Warning: Could not retrieve conversation history: {str(e)}")
```

### 2. Inclusión en el Prompt

```python
# Build conversation history section
history_section = ""
if conversation_summary:
    history_section = f"""
────────────────────────────────────────
HISTORIAL DE CONVERSACIÓN RECIENTE
────────────────────────────────────────
El usuario ha tenido las siguientes interacciones recientes:

{conversation_summary}

IMPORTANTE: 
- USA la información del historial para entender mejor el contexto del usuario
- Si el usuario ya mencionó síntomas previos, considéralos en tu análisis
- Acumula información de síntomas a través de los turnos de conversación
"""
```

### 3. Formato del Historial Mejorado

El `session_manager` ahora captura información clave de triage:

```python
elif 'triage/interpret' in endpoint:
    capa = response.get('capa')
    if capa:
        summary_lines.append(f"  Capa de atención: {capa}")
    
    especialidad = response.get('especialidad_sugerida')
    if especialidad:
        summary_lines.append(f"  Especialidad sugerida por triaje: {especialidad}")
    
    razones = response.get('razones', [])
    if razones:
        summary_lines.append(f"  Razones: {', '.join(razones[:3])}")
    
    accion = response.get('accion_recomendada')
    if accion:
        summary_lines.append(f"  Acción recomendada: {accion}")
```

## Casos de Uso Críticos

### Caso 1: Acumulación de Síntomas de Emergencia

**Escenario**: Meningitis (fiebre + dolor de cabeza + rigidez de cuello)

```
Turno 1: "Tengo fiebre de 39°C"
→ Capa 2 (fiebre alta, pero sin otros signos de alarma)

Turno 2: "Me duele mucho la cabeza"
→ Capa 2 (fiebre + dolor de cabeza, preocupante pero aún no emergencia)

Turno 3: "Y no puedo mover el cuello, está muy rígido"
→ Capa 4 - EMERGENCIA
→ Razones: "fiebre alta + dolor de cabeza + rigidez de cuello = posible meningitis"
→ Acción: "Llama al 911 inmediatamente"
```

### Caso 2: Evolución de Síntomas Cardíacos

**Escenario**: Infarto progresivo

```
Turno 1: "Me duele un poco el pecho"
→ Capa 3 (dolor de pecho leve, consulta presencial)

Turno 2: "Ahora el dolor es más fuerte"
→ Capa 4 (dolor de pecho que empeora = posible infarto)

Turno 3: "Y estoy sudando frío"
→ Capa 4 - EMERGENCIA CRÍTICA
→ Razones: "dolor de pecho progresivo + sudoración fría = infarto agudo"
→ Acción: "Llama al 911 AHORA. No conduzcas."
```

### Caso 3: Síntomas Crónicos con Contexto

**Escenario**: Diabetes descontrolada

```
Turno 1: "Soy diabético y me siento muy cansado"
→ Capa 3 (fatiga en diabético, consulta presencial)

Turno 2: "También tengo mucha sed"
→ Capa 3 (fatiga + polidipsia = descontrol glucémico)

Turno 3: "Y voy mucho al baño"
→ Capa 3 (tríada clásica de hiperglucemia)
→ Razones: "fatiga + sed + poliuria = probable hiperglucemia"
→ Acción: "Consulta presencial urgente con endocrinología"
→ Recomendación: "Mide tu glucosa si tienes glucómetro"
```

### Caso 4: Respuestas a Preguntas del Sistema

**Escenario**: Sistema pide más información

```
Turno 1: "Me duele el estómago"
→ Capa 2
→ Sistema pregunta: "¿Desde cuándo tienes el dolor?"

Turno 2: "Desde ayer por la noche"
→ Sistema lee historial: dolor de estómago
→ Sistema interpreta: "desde ayer" = duración ~12-18 horas
→ Capa 2 (dolor abdominal agudo, médico a domicilio)
→ NO pregunta de nuevo sobre el dolor
```

## Beneficios

### 1. Detección de Patrones Peligrosos

El sistema puede identificar combinaciones de síntomas que individualmente no son emergencias, pero juntos sí lo son:

- Fiebre + dolor de cabeza + rigidez de cuello → Meningitis
- Dolor de pecho + sudoración + náuseas → Infarto
- Debilidad facial + dificultad para hablar → ACV
- Fiebre + tos + dificultad respiratoria → Neumonía grave

### 2. Clasificación Más Precisa

Con el historial, el sistema puede:
- Evaluar la progresión de síntomas
- Identificar empeoramiento
- Considerar duración acumulada
- Reconocer patrones de enfermedad

### 3. Mejor Experiencia del Usuario

- No se repiten preguntas
- El usuario no tiene que repetir información
- Conversación más natural y fluida
- Mayor confianza en el sistema

### 4. Seguridad Mejorada

- Menor riesgo de perder emergencias
- Detección temprana de deterioro
- Clasificación más conservadora cuando hay duda
- Mejor identificación de signos de alarma

## Formato del Historial

### Ejemplo de Historial Formateado

```
Turno 1:
  Usuario dijo: tengo fiebre alta
  Capa de atención: 2
  Razones: fiebre alta
  Acción recomendada: solicitar_medico_a_domicilio

Turno 2:
  Usuario dijo: y me duele la cabeza
  Capa de atención: 2
  Especialidad sugerida por triaje: medicina_interna
  Razones: fiebre alta, dolor de cabeza
  Acción recomendada: solicitar_medico_a_domicilio

Turno 3:
  Usuario dijo: y el cuello está rígido
  Capa de atención: 4
  Especialidad sugerida por triaje: neurología
  Razones: fiebre alta, dolor de cabeza, rigidez de cuello, posible meningitis
  Acción recomendada: llamar_emergencias
```

Este formato permite al LLM:
- Ver la evolución de los síntomas
- Identificar patrones de empeoramiento
- Considerar toda la información acumulada
- Tomar decisiones más informadas

## Integración con RAG

El historial de conversación se combina con RAG para máxima efectividad:

```
Historial: fiebre alta + dolor de cabeza + rigidez de cuello
    +
RAG: "Esta combinación puede indicar meningitis, una emergencia médica"
    =
Clasificación: Capa 4 - Emergencia
Respuesta: "Los síntomas que describes (fiebre alta, dolor de cabeza y 
rigidez de cuello) pueden indicar meningitis, una infección grave que 
requiere atención inmediata. Llama al 911 ahora."
```

## Testing

### Tests Implementados

1. **test_triage_uses_conversation_history**: Verifica que se recupera el historial
2. **test_triage_accumulates_symptoms**: Verifica acumulación de síntomas
3. **test_triage_no_repeated_questions**: Verifica que no se repiten preguntas
4. **test_triage_history_includes_key_info**: Verifica formato del historial

Ejecutar tests:
```bash
cd v2-agent
pytest tests/test_triage_conversation_context.py -v
```

## Métricas de Éxito

| Métrica | Objetivo | Cómo Medir |
|---------|----------|------------|
| Detección de emergencias | 100% | Ninguna emergencia real clasificada < Capa 4 |
| Acumulación de síntomas | > 95% | % de casos donde se consideran síntomas previos |
| Preguntas repetidas | < 5% | % de veces que se pregunta lo mismo |
| Satisfacción usuario | > 4.5/5 | Encuestas post-triaje |
| Tiempo de clasificación | < 3 turnos | Promedio de turnos hasta clasificación final |

## Seguridad

### Principio de Precaución

Incluso con historial, el sistema SIEMPRE:
- Clasifica hacia arriba en caso de duda
- Prioriza la seguridad del paciente
- Identifica signos de alarma inmediatamente
- No espera a acumular síntomas si hay emergencia obvia

### Ejemplo de Seguridad

```
Turno 1: "Tengo un poco de tos"
→ Capa 1 (tos leve)

Turno 2: "Ahora no puedo respirar bien"
→ Capa 4 INMEDIATA (dificultad respiratoria = emergencia)
→ NO espera más información
→ NO considera que la tos era leve
→ Acción: "Llama al 911 ahora"
```

## Monitoreo

### Logs Clave

```bash
# Verificar que se recupera historial
grep "Found conversation history for user" logs/app.log

# Verificar acumulación de síntomas
grep "Razones:" logs/app.log | grep -c ","

# Verificar upgrades de capa
grep "Capa de atención: 4" logs/app.log
```

### Alertas

Configurar alertas para:
- Casos donde Capa sube de 1/2 a 4 (posible emergencia progresiva)
- Casos con > 5 turnos sin clasificación final (posible confusión)
- Tasa de Capa 4 > 20% (posibles falsos positivos)

## Próximos Pasos

1. **Análisis de Patrones**: Identificar combinaciones comunes de síntomas
2. **Machine Learning**: Entrenar modelo para detectar patrones de emergencia
3. **Feedback Médico**: Validar clasificaciones con profesionales
4. **Optimización**: Reducir número de turnos necesarios
5. **Multilingüe**: Soporte para otros idiomas

## Referencias

- [triage/interpret.py](./triage/interpret.py): Implementación del endpoint
- [session_manager.py](./session_manager.py): Gestión de historial
- [tests/test_triage_conversation_context.py](./tests/test_triage_conversation_context.py): Tests
- [CONVERSATION_CONTEXT_FIX.md](./CONVERSATION_CONTEXT_FIX.md): Fix general de contexto
