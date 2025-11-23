## RAG en Triage: Clasificación Médica Mejorada

## Resumen

El endpoint de **triage/interpret** ahora consulta el Lambda RAG Worker en cada request para mejorar la clasificación de síntomas y generar respuestas más educativas.

## Motivación

### Problema

El triage es el componente más crítico del sistema porque:
- Determina el nivel de urgencia (Capa 1-4)
- Puede ser la diferencia entre vida y muerte (Capa 4)
- Requiere conocimiento médico preciso
- Debe identificar signos de alarma correctamente

**Sin RAG**, el triage dependía únicamente del prompt y el modelo LLM, sin acceso a conocimiento médico actualizado.

### Solución

Integrar RAG para proporcionar:
- Información médica actualizada sobre síntomas
- Contexto sobre signos de alarma
- Guías de clasificación de urgencia
- Información sobre especialidades médicas

## Beneficios

### 1. Clasificación Más Precisa

**Antes (sin RAG)**:
```
Usuario: "Tengo fiebre alta y me duele el cuello"
Sistema: Capa 2 - Médico a domicilio
```

**Después (con RAG)**:
```
Usuario: "Tengo fiebre alta y me duele el cuello"
RAG: "Fiebre alta con rigidez de cuello puede indicar meningitis - emergencia"
Sistema: Capa 4 - Emergencia (posible meningitis)
```

### 2. Identificación de Signos de Alarma

RAG ayuda a identificar combinaciones peligrosas de síntomas:

```
Usuario: "Me duele el pecho y me falta el aire"
RAG: "Dolor de pecho + dificultad respiratoria = posible infarto o embolia pulmonar"
Sistema: Capa 4 - Emergencia inmediata
```

### 3. Respuestas Más Educativas

**Sin RAG**:
```
"Capa 4 - Emergencia. Llama al 911."
```

**Con RAG**:
```
"Capa 4 - Emergencia. El dolor de pecho con dificultad para respirar puede 
indicar un infarto o problema pulmonar grave que requiere atención inmediata. 
Llama al 911 o acude al hospital más cercano ahora."
```

### 4. Mejor Sugerencia de Especialidades

RAG proporciona contexto sobre qué especialidad es más apropiada:

```
Usuario: "Tengo mareos y me tiemblan las manos"
RAG: "Mareos + temblor pueden ser neurológicos o endocrinos"
Sistema: Capa 3 - Consulta presencial con neurología
Respuesta: "Te recomiendo una consulta con neurología. Los neurólogos se 
especializan en trastornos del sistema nervioso que pueden causar mareos y temblores."
```

## Implementación

### Cambios en `triage/interpret.py`

```python
# SIEMPRE consultar RAG primero
rag_result = retrieve_context(
    query=req.message,
    user_id=req.user_id,
    max_results=3
)

# Formatear contexto para el prompt
rag_context_str = format_context_for_prompt(rag_result['documents'])

# Incluir en el prompt de clasificación
prompt = f"""
Eres el Agente de Triaje...

INFORMACIÓN MÉDICA RELEVANTE DE LA BASE DE CONOCIMIENTO
{rag_context_str}

Usa esta información para:
- Entender mejor el contexto médico de los síntomas
- Clasificar con más precisión el nivel de atención
- Identificar signos de alarma con mayor certeza
- Sugerir la especialidad más apropiada
"""

# Agregar documentos a la respuesta
response_body['rag_documents'] = rag_documents
```

### Cambios en `main.py`

```python
# Generar respuesta en lenguaje natural con contexto RAG
if endpoint == "triage/interpret":
    rag_documents = response_data.get('rag_documents', [])
    
    if rag_documents:
        rag_context_section = "Contexto médico adicional:\n"
        for doc in rag_documents:
            rag_context_section += f"- {doc['content']}\n"
    
    prompt = f"""
    ...
    {rag_context_section}
    
    Usa el contexto médico para:
    - Explicar por qué ciertos síntomas requieren atención urgente
    - Proporcionar contexto sobre la especialidad recomendada
    - Ayudar al usuario a entender mejor su situación
    """
```

## Casos de Uso

### Caso 1: Emergencia Cardíaca

**Input**: "Me duele el pecho fuerte y sudo frío"

**RAG Context**:
- "Dolor de pecho + sudoración fría = posible infarto agudo de miocardio"
- "Infarto requiere atención en menos de 60 minutos para evitar daño permanente"

**Clasificación**: Capa 4

**Respuesta**:
```
EMERGENCIA - Capa 4

Los síntomas que describes (dolor de pecho intenso con sudoración fría) pueden 
indicar un infarto agudo de miocardio, una emergencia médica que requiere 
atención inmediata.

ACCIÓN INMEDIATA:
- Llama al 911 ahora
- No conduzcas tú mismo
- Si tienes aspirina, toma una mientras esperas la ambulancia
- Mantente en reposo

El tiempo es crítico en casos de infarto. Cada minuto cuenta.
```

### Caso 2: Síntomas Neurológicos

**Input**: "Se me durmió la mitad de la cara y no puedo hablar bien"

**RAG Context**:
- "Debilidad facial unilateral + dificultad para hablar = posible ACV (stroke)"
- "ACV requiere atención en ventana de 4.5 horas para tratamiento efectivo"

**Clasificación**: Capa 4

**Respuesta**:
```
EMERGENCIA - Capa 4

Los síntomas que describes (debilidad facial y dificultad para hablar) son 
signos de un posible accidente cerebrovascular (ACV o stroke), una emergencia 
neurológica.

ACCIÓN INMEDIATA:
- Llama al 911 inmediatamente
- Anota la hora en que comenzaron los síntomas
- No comas ni bebas nada
- Mantente en reposo

El tratamiento temprano del ACV puede prevenir daño cerebral permanente. 
Actúa rápido.
```

### Caso 3: Síntomas Leves con Contexto

**Input**: "Tengo tos y un poco de fiebre desde ayer"

**RAG Context**:
- "Tos + fiebre leve < 48 horas = probable infección respiratoria viral"
- "Síntomas leves sin dificultad respiratoria = Capa 1 (médico virtual)"

**Clasificación**: Capa 1

**Respuesta**:
```
Capa 1 - Médico Virtual

Tus síntomas (tos y fiebre leve desde ayer) sugieren una infección respiratoria 
viral común. Como los síntomas son recientes y leves, puedes iniciar con una 
consulta virtual.

RECOMENDACIÓN:
- Agenda una consulta con médico virtual
- Mantente hidratado
- Descansa
- Monitorea tu temperatura

SIGNOS DE ALARMA (acude a emergencias si presentas):
- Dificultad para respirar
- Fiebre > 39°C persistente
- Dolor de pecho
- Confusión o mareo intenso

¿Te gustaría que te ayude a agendar una consulta virtual?
```

### Caso 4: Condición Crónica

**Input**: "Tengo diabetes y últimamente me siento muy cansado"

**RAG Context**:
- "Fatiga en diabético puede indicar descontrol glucémico"
- "Requiere evaluación y ajuste de tratamiento - Capa 3"

**Clasificación**: Capa 3

**Respuesta**:
```
Capa 3 - Consulta Presencial

Como paciente con diabetes, la fatiga persistente puede indicar que tus niveles 
de glucosa necesitan ajuste. Te recomiendo una consulta presencial con medicina 
interna o endocrinología.

RECOMENDACIÓN:
- Consulta presencial para evaluación completa
- Posibles exámenes de laboratorio (glucosa, HbA1c)
- Ajuste de tratamiento si es necesario

MIENTRAS TANTO:
- Monitorea tus niveles de glucosa si tienes glucómetro
- Mantén tu dieta y medicación actual
- Anota otros síntomas que notes

¿Te gustaría buscar disponibilidad con medicina interna o endocrinología?
```

## Tipos de Información en RAG

### 1. Signos de Alarma

```
- Dolor de pecho + sudoración = posible infarto
- Fiebre alta + rigidez de cuello = posible meningitis
- Debilidad facial unilateral = posible ACV
- Dificultad respiratoria severa = emergencia respiratoria
```

### 2. Guías de Clasificación

```
- Síntomas < 7 días + leves = Capa 1
- Síntomas agudos moderados = Capa 2
- Condiciones crónicas = Capa 3
- Signos de alarma = Capa 4
```

### 3. Información de Especialidades

```
- Cardiología: corazón, presión arterial, arritmias
- Neurología: cerebro, nervios, mareos, temblores
- Neumología: pulmones, respiración, tos crónica
- Endocrinología: diabetes, tiroides, hormonas
```

### 4. Contexto Médico

```
- Infarto: tiempo crítico < 60 minutos
- ACV: ventana terapéutica 4.5 horas
- Meningitis: progresión rápida, alta mortalidad
- Apendicitis: puede perforarse en 24-48 horas
```

## Métricas de Éxito

| Métrica | Objetivo | Cómo Medir |
|---------|----------|------------|
| Precisión de clasificación | > 95% | Revisión médica de casos |
| Detección de emergencias | 100% | Ninguna emergencia clasificada < Capa 4 |
| Satisfacción usuario | > 4.5/5 | Encuestas post-triaje |
| Comprensión de urgencia | > 90% | "¿Entiendes por qué es urgente?" |
| Falsos positivos Capa 4 | < 10% | Casos Capa 4 que no eran emergencias |

## Seguridad y Responsabilidad

### Principio de Precaución

**SIEMPRE clasificar hacia arriba en caso de duda**:
- Duda entre Capa 2 y 3 → Capa 3
- Duda entre Capa 3 y 4 → Capa 4
- Cualquier posible signo de alarma → Capa 4

### Disclaimers Obligatorios

Toda respuesta de triage debe incluir:

```
"Este asistente no reemplaza una evaluación médica profesional. 
Si tus síntomas empeoran o presentas signos de alarma, acude 
de inmediato a un servicio de emergencia."
```

Para Capa 4:

```
"EMERGENCIA MÉDICA: Los síntomas que describes requieren atención 
inmediata. Llama al 911 o acude al hospital más cercano ahora. 
No esperes."
```

### Limitaciones

El sistema NO puede:
- Diagnosticar enfermedades
- Prescribir medicamentos
- Reemplazar evaluación médica profesional
- Garantizar 100% de precisión

El sistema SÍ puede:
- Clasificar nivel de urgencia
- Identificar signos de alarma
- Sugerir especialidades apropiadas
- Proporcionar información educativa
- Guiar al usuario hacia el nivel de atención correcto

## Monitoreo

### Logs Clave

```bash
# Verificar que RAG se consulta en triage
grep "Consultando RAG para triaje" logs/app.log

# Verificar documentos recuperados
grep "Retrieved .* documents from RAG for triage" logs/app.log

# Verificar clasificaciones de emergencia
grep "Capa 4" logs/app.log
```

### Alertas Críticas

Configurar alertas para:
- Tasa de Capa 4 > 20% (posibles falsos positivos)
- Tasa de Capa 4 < 1% (posibles falsos negativos)
- RAG failures > 5% (degradación del servicio)
- Latencia > 3 segundos (experiencia del usuario)

## Testing

### Tests Críticos

1. **Emergencias Cardíacas**: Dolor de pecho → Capa 4
2. **Emergencias Neurológicas**: ACV → Capa 4
3. **Emergencias Respiratorias**: Dificultad respiratoria → Capa 4
4. **Síntomas Leves**: Resfriado → Capa 1
5. **Condiciones Crónicas**: Diabetes descontrolada → Capa 3

### Casos de Prueba

```python
# Test 1: Infarto
assert classify("dolor de pecho intenso y sudo frío")['capa'] == 4

# Test 2: ACV
assert classify("se me durmió la cara y no puedo hablar")['capa'] == 4

# Test 3: Resfriado
assert classify("tengo tos y un poco de fiebre")['capa'] == 1

# Test 4: Diabetes
assert classify("soy diabético y me siento cansado")['capa'] == 3
```

## Próximos Pasos

1. **Validación Médica**: Revisar clasificaciones con médicos
2. **Expansión de RAG**: Agregar más casos médicos
3. **Feedback Loop**: Aprender de casos mal clasificados
4. **Integración con Historia Clínica**: Usar datos del paciente
5. **Multilingüe**: Soporte para otros idiomas

## Referencias

- [triage/interpret.py](./triage/interpret.py): Implementación del endpoint
- [tests/test_triage_rag_integration.py](./tests/test_triage_rag_integration.py): Tests de integración
- [RAG_INTEGRATION.md](./RAG_INTEGRATION.md): Documentación general de RAG
