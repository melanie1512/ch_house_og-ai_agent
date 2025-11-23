# Integración RAG con el Agente LLM

## Resumen

Este documento describe cómo se integró el Lambda `rimac-rag-worker-prod` con el agente LLM para mejorar la experiencia del usuario al hacer preguntas.

## Arquitectura

### Flujo de Integración

```
Usuario → FastAPI → doctors/interpret → Lambda RAG (SIEMPRE)
                                              ↓
                                    Bedrock (con contexto RAG)
                                              ↓
                                    ¿Requiere más info?
                                              ↓
                                    ┌─────────┴─────────┐
                                    ↓                   ↓
                                   Sí                  No
                                    ↓                   ↓
                        Pregunta contextualizada   Consulta DynamoDB
                                    ↓                   ↓
                            Usuario recibe         Resultados
                            pregunta enriquecida        ↓
                                                Respuesta en lenguaje natural
                                                (usando contexto RAG)
```

### Componentes

1. **rag_helper.py**: Módulo que encapsula la lógica de llamada al Lambda RAG
   - `retrieve_context()`: Invoca el Lambda y obtiene documentos relevantes
   - `format_context_for_prompt()`: Formatea los documentos para el prompt del LLM

2. **lambda_client.py**: Cliente genérico para invocar funciones Lambda
   - Maneja autenticación, errores y logging
   - Soporta invocaciones síncronas y asíncronas

3. **doctors/interpret.py**: Endpoint modificado con lógica de dos fases
   - Fase 1: Determina si se puede ejecutar consulta DynamoDB
   - Fase 2: Si se necesita más info, consulta RAG y mejora la pregunta

## Lógica de Uso del RAG

### Cuándo SE USA el RAG

El RAG se usa **SIEMPRE** en cada interacción:
- Se consulta al inicio de cada request, antes de procesar la intención del usuario
- Proporciona contexto relevante de la base de conocimiento
- Enriquece tanto las preguntas como las respuestas finales

### Propósito del RAG

El contexto RAG se usa para:
- ✅ Formular preguntas más contextualizadas al usuario
- ✅ Proporcionar información médica relevante en las respuestas
- ✅ Explicar por qué una especialidad es apropiada
- ✅ Ayudar al usuario a entender mejor su situación
- ✅ Generar respuestas en lenguaje natural más ricas y educativas
- ✅ Proporcionar contexto sobre especialidades, síntomas o condiciones

El contexto RAG **NO** se usa para:
- ❌ Generar consultas de DynamoDB con información no confirmada por el usuario
- ❌ Inventar criterios de búsqueda que el usuario no mencionó
- ❌ Asumir preferencias del usuario sin preguntarle

## Ejemplo de Uso

### Caso 1: Información Suficiente (Con RAG)

**Usuario**: "Quiero una cita con un cardiólogo en Lima mañana"

**Flujo**:
1. Se invoca Lambda RAG con el mensaje del usuario
2. Se obtiene contexto sobre cardiología
3. Llamada a Bedrock (con RAG)
4. Se detecta información suficiente
5. Se genera consulta DynamoDB
6. Se ejecuta consulta
7. Se genera respuesta en lenguaje natural usando contexto RAG
8. Se devuelven resultados enriquecidos

**RAG**: Se invoca ✅

**Ejemplo de respuesta**:
- Sin RAG: "Encontré 3 cardiólogos disponibles en Lima para mañana."
- Con RAG: "Encontré 3 cardiólogos disponibles en Lima para mañana. La cardiología se especializa en el diagnóstico y tratamiento de enfermedades del corazón y sistema circulatorio. Aquí están tus opciones..."

---

### Caso 2: Información Insuficiente (Con RAG)

**Usuario**: "Me duele el pecho, necesito ayuda"

**Flujo**:
1. Se invoca Lambda RAG con el mensaje del usuario
2. Se obtiene contexto sobre dolor de pecho y cardiología
3. Llamada a Bedrock (con RAG)
4. Se detecta información insuficiente (`requiere_mas_informacion: true`)
5. Se genera pregunta contextualizada usando RAG
6. Se devuelve pregunta al usuario

**RAG**: Se invoca ✅

**Ejemplo de mejora**:
- Sin RAG: "¿Con qué especialidad médica deseas atenderte?"
- Con RAG: "Veo que mencionas dolor de pecho. ¿Deseas una cita con cardiología? La cardiología se especializa en problemas del corazón y puede ayudarte a evaluar este síntoma."

## Configuración

### Variables de Entorno

```bash
# Lambda ARN para el worker RAG
RAG_WORKER_LAMBDA_ARN=arn:aws:lambda:us-east-1:ACCOUNT_ID:function:rimac-rag-worker-prod

# Región de AWS
AWS_REGION=us-east-1
```

### Permisos IAM Requeridos

El rol de App Runner necesita permisos para invocar el Lambda:

```json
{
  "Effect": "Allow",
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:us-east-1:*:function:rimac-rag-worker-prod"
}
```

## Payload del Lambda RAG

### Request

```json
{
  "query": "mensaje del usuario",
  "user_id": "user_123",
  "max_results": 3,
  "filters": {
    // filtros opcionales
  }
}
```

### Response

```json
{
  "documents": [
    {
      "content": "contenido del documento",
      "source": "fuente del documento",
      "score": 0.95
    }
  ],
  "metadata": {
    "total_results": 3,
    "query_time_ms": 150
  }
}
```

## Manejo de Errores

### Degradación Elegante

Si el Lambda RAG falla:
1. Se captura la excepción
2. Se registra un warning en los logs
3. Se continúa con la pregunta original (sin contexto RAG)
4. El usuario recibe una respuesta funcional

**Principio**: El sistema debe funcionar incluso si RAG no está disponible.

## Testing

Se incluyen tests en `tests/test_rag_integration.py`:

1. **test_rag_not_called_with_sufficient_info**: Verifica que RAG no se llama cuando hay info suficiente
2. **test_rag_called_when_info_needed**: Verifica que RAG se llama cuando se necesita más info
3. **test_rag_graceful_degradation_on_error**: Verifica que el sistema funciona si RAG falla

Ejecutar tests:
```bash
cd v2-agent
pytest tests/test_rag_integration.py -v
```

## Monitoreo

### Logs a Revisar

- "Retrieved X documents from RAG": Indica cuántos documentos se obtuvieron
- "Se requiere más información. Consultando RAG...": Indica que se activó la segunda fase
- "Pregunta mejorada con contexto RAG": Indica que se usó RAG exitosamente
- "Warning: Could not retrieve RAG context": Indica fallo en RAG (degradación elegante)

### Métricas Importantes

- Tasa de invocaciones RAG vs total de requests
- Latencia de llamadas RAG
- Tasa de errores en Lambda RAG
- Mejora en satisfacción del usuario (preguntas más contextualizadas)

## Próximos Pasos

1. **Optimización de Prompts**: Refinar cómo se usa el contexto RAG en las preguntas
2. **Caché**: Implementar caché para consultas RAG frecuentes
3. **Feedback Loop**: Recopilar feedback sobre la calidad de las preguntas mejoradas
4. **Expansión**: Aplicar el mismo patrón a otros endpoints (triage, workshops)

## Referencias

- [lambda_client.py](./lambda_client.py): Cliente Lambda genérico
- [rag_helper.py](./rag_helper.py): Helper para RAG
- [doctors/interpret.py](./doctors/interpret.py): Implementación del endpoint
- [tests/test_rag_integration.py](./tests/test_rag_integration.py): Tests de integración
