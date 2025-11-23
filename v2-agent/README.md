# Health Assistant API v2 - Bedrock Router

Sistema de asistente de salud con routing inteligente usando AWS Bedrock Agent.

## Arquitectura

El sistema usa un **agente router principal** que analiza el mensaje del usuario y lo deriva automáticamente a uno de tres servicios:

1. **triage/interpret** - Evaluación de síntomas y riesgo médico
2. **doctors/interpret** - Búsqueda y gestión de citas médicas
3. **workshops/interpret** - Búsqueda y registro en talleres de bienestar

```
Usuario → POST /agent/route → AWS Bedrock (Claude 3) → Análisis del mensaje
                                                              ↓
                                    ┌─────────────────────────┼─────────────────────────┐
                                    ↓                         ↓                         ↓
                            triage/interpret          doctors/interpret        workshops/interpret
                                    ↓                         ↓                         ↓
                            Evaluación de riesgo      Gestión de citas         Talleres de bienestar
                                    ↓                         ↓                         ↓
                                    └─────────────────────────┴─────────────────────────┘
                                                              ↓
                                                    Respuesta al usuario
```

## Endpoints

### Endpoint Principal (Router)

```
POST /agent/route
```

**Request:**
```json
{
  "user_id": "user123",
  "message": "Me duele la cabeza desde hace 3 días"
}
```

**Response:**
```json
{
  "endpoint": "triage/interpret",
  "confidence": 0.95,
  "reasoning": "El usuario describe síntomas médicos",
  "response": {
    "risk": {...},
    "reply": "..."
  }
}
```

### Endpoints Específicos

#### Triaje
```
POST /triage/interpret
```

#### Doctores/Citas
```
POST /doctors/interpret
```

#### Talleres
```
POST /workshops/interpret
```

## Configuración

1. Copiar `.env.example` a `.env`:
```bash
cp .env.example .env
```

2. Configurar credenciales de AWS en `.env`:
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Ejecutar:
```bash
uvicorn main:app --reload
```

## Requisitos AWS

- Cuenta de AWS con acceso a Bedrock
- Modelo Claude 3 Sonnet habilitado en tu región
- Credenciales IAM con permisos para `bedrock:InvokeModel`

## Ejemplos de Uso

### Consulta de síntomas (→ triage)
```json
{
  "user_id": "user123",
  "message": "Tengo fiebre alta y tos desde ayer"
}
```

### Buscar doctor (→ doctors)
```json
{
  "user_id": "user123",
  "message": "Necesito un cardiólogo para mañana"
}
```

### Buscar taller (→ workshops)
```json
{
  "user_id": "user123",
  "message": "Quiero un taller de manejo del estrés"
}
```

## Estructura de Archivos

```
v2-agent/
├── main.py                    # FastAPI app principal
├── models.py                  # Modelos Pydantic
├── bedrock_agent.py          # Router con Bedrock
├── config.py                 # Configuración
├── doctors/
│   └── interpret.py          # Lógica de citas
├── workshops/
│   └── interpret.py          # Lógica de talleres
└── triage/
    ├── symptom_extraction.py
    ├── risk_engine.py
    ├── response_builder.py
    └── chat_history.py
```
