# Flujo de Integración RAG

## Diagrama de Flujo Detallado

```mermaid
flowchart TD
    A[Usuario envía mensaje] --> B[doctors/interpret endpoint]
    B --> C[Obtener contexto de sesión]
    C --> D[Primera llamada a Bedrock SIN RAG]
    D --> E{¿Requiere más información?}
    
    E -->|No| F[Generar consulta DynamoDB]
    F --> G[Ejecutar consulta]
    G --> H[Devolver resultados al usuario]
    
    E -->|Sí| I[Invocar Lambda RAG]
    I --> J{¿RAG exitoso?}
    
    J -->|Sí| K[Formatear documentos RAG]
    K --> L[Segunda llamada a Bedrock CON RAG]
    L --> M[Generar pregunta contextualizada]
    M --> N[Devolver pregunta al usuario]
    
    J -->|No| O[Log warning]
    O --> P[Usar pregunta original sin RAG]
    P --> N
    
    style I fill:#90EE90
    style L fill:#90EE90
    style M fill:#FFD700
    style F fill:#87CEEB
    style G fill:#87CEEB
```

## Flujo de Decisión: ¿Cuándo usar RAG?

```mermaid
flowchart TD
    A[Analizar mensaje del usuario] --> B{¿Tiene especialidad?}
    B -->|No| C[requiere_mas_informacion = true]
    B -->|Sí| D{¿Tiene modalidad o ubicación?}
    
    D -->|No| E{¿Es necesario para la búsqueda?}
    E -->|Sí| C
    E -->|No| F[Generar consulta con lo disponible]
    
    D -->|Sí| F
    
    C --> G[USAR RAG para mejorar pregunta]
    F --> H[NO usar RAG, ejecutar consulta]
    
    style G fill:#90EE90
    style H fill:#87CEEB
```

## Comparación: Con RAG vs Sin RAG

### Escenario 1: Usuario con información completa

| Aspecto | Sin RAG | Con RAG |
|---------|---------|---------|
| **Mensaje** | "Quiero cita con cardiólogo en Lima mañana" | "Quiero cita con cardiólogo en Lima mañana" |
| **RAG invocado** | ❌ No | ❌ No |
| **Llamadas Bedrock** | 1 | 1 |
| **Resultado** | Consulta DynamoDB ejecutada | Consulta DynamoDB ejecutada |
| **Latencia** | ~500ms | ~500ms |

### Escenario 2: Usuario con información incompleta

| Aspecto | Sin RAG | Con RAG |
|---------|---------|---------|
| **Mensaje** | "Necesito una cita" | "Me duele el pecho, necesito ayuda" |
| **RAG invocado** | ❌ No | ✅ Sí |
| **Llamadas Bedrock** | 1 | 2 |
| **Pregunta generada** | "¿Con qué especialidad médica deseas atenderte?" | "Veo que mencionas dolor de pecho. ¿Deseas una cita con cardiología?" |
| **Latencia** | ~500ms | ~1200ms (incluye Lambda) |
| **Experiencia usuario** | Genérica | Contextualizada ⭐ |

## Arquitectura de Componentes

```mermaid
graph LR
    A[FastAPI] --> B[doctors/interpret.py]
    B --> C[session_manager]
    B --> D[build_prompt]
    D --> E[Bedrock Claude]
    
    B --> F{¿Requiere info?}
    F -->|Sí| G[rag_helper.py]
    G --> H[lambda_client.py]
    H --> I[Lambda RAG Worker]
    I --> J[Knowledge Base]
    
    F -->|No| K[dynamodb_query.py]
    K --> L[DynamoDB]
    
    style G fill:#90EE90
    style I fill:#90EE90
    style J fill:#FFD700
```

## Secuencia de Llamadas

### Caso A: Sin necesidad de RAG

```
Usuario → FastAPI → doctors/interpret
                         ↓
                    Bedrock (1 llamada)
                         ↓
                    DynamoDB Query
                         ↓
                    Respuesta con doctores
```

**Tiempo total**: ~500-700ms

### Caso B: Con necesidad de RAG

```
Usuario → FastAPI → doctors/interpret
                         ↓
                    Bedrock (1ª llamada)
                         ↓
                    ¿Requiere info? → Sí
                         ↓
                    Lambda RAG (~300ms)
                         ↓
                    Bedrock (2ª llamada)
                         ↓
                    Pregunta contextualizada
```

**Tiempo total**: ~1000-1500ms

## Optimizaciones Futuras

### 1. Caché de RAG
```mermaid
graph LR
    A[Query] --> B{¿En caché?}
    B -->|Sí| C[Devolver desde caché]
    B -->|No| D[Llamar Lambda RAG]
    D --> E[Guardar en caché]
    E --> F[Devolver resultado]
```

### 2. RAG Paralelo (Especulativo)
```mermaid
graph LR
    A[Mensaje usuario] --> B[Bedrock]
    A --> C[Lambda RAG en paralelo]
    B --> D{¿Requiere info?}
    D -->|Sí| E[Usar RAG ya disponible]
    D -->|No| F[Ignorar RAG]
    C --> E
```

### 3. RAG Adaptativo
```mermaid
graph TD
    A[Analizar mensaje] --> B{¿Complejidad?}
    B -->|Alta| C[max_results=5]
    B -->|Media| D[max_results=3]
    B -->|Baja| E[max_results=1]
    
    C --> F[Lambda RAG]
    D --> F
    E --> F
```

## Métricas de Éxito

| Métrica | Objetivo | Actual |
|---------|----------|--------|
| Tasa de uso RAG | 20-30% de requests | TBD |
| Latencia p95 con RAG | < 2000ms | TBD |
| Tasa de error RAG | < 1% | TBD |
| Satisfacción usuario | > 4.5/5 | TBD |
| Reducción de preguntas repetidas | > 30% | TBD |

## Monitoreo en CloudWatch

### Logs a buscar

```
# RAG invocado exitosamente
"Retrieved X documents from RAG"

# RAG falló (degradación elegante)
"Warning: Could not retrieve RAG context"

# Segunda llamada con RAG
"Pregunta mejorada con contexto RAG"
```

### Métricas custom

- `rag.invocations.count`: Número de veces que se invoca RAG
- `rag.latency.ms`: Latencia de llamadas RAG
- `rag.errors.count`: Errores en RAG
- `rag.documents.retrieved`: Promedio de documentos obtenidos
