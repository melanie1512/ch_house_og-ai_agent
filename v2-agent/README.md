# Health Assistant API v2 - Sistema Inteligente de Salud

Sistema de asistente de salud con routing inteligente usando AWS Bedrock (Claude 3) y DynamoDB.

## Arquitectura

El sistema usa un **agente router principal** que analiza el mensaje del usuario y lo deriva automáticamente a uno de tres servicios especializados:

1. **triage/interpret** - Evaluación de síntomas y clasificación de riesgo (Capas 1-4)
2. **doctors/interpret** - Búsqueda de doctores y gestión de citas médicas con DynamoDB
3. **workshops/interpret** - Búsqueda y registro en talleres de bienestar

```
Usuario → POST /agent/route → AWS Bedrock (Claude 3) → Análisis del mensaje
                                                              ↓
                                    ┌─────────────────────────┼─────────────────────────┐
                                    ↓                         ↓                         ↓
                            triage/interpret          doctors/interpret        workshops/interpret
                                    ↓                         ↓                         ↓
                            Evaluación de riesgo      DynamoDB Query           Talleres de bienestar
                            Capas 1-4                 (doctores + horarios)    
                                    ↓                         ↓                         ↓
                                    └─────────────────────────┴─────────────────────────┘
                                                              ↓
                                                    Respuesta al usuario
```

## Componentes AWS

- **AWS Bedrock**: Claude 3 Haiku para interpretación de lenguaje natural
- **DynamoDB**: 
  - Tabla `doctores`: Información de médicos (especialidad, ubicación, experiencia)
  - Tabla `horarios_doctores`: Disponibilidad de citas por doctor
- **IAM**: Permisos para Bedrock y DynamoDB

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

## Setup Completo

### 1. Configurar Credenciales AWS

Configurar en `.env`:
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
BEDROCK_MODEL=us.anthropic.claude-3-haiku-20240307-v1:0
```
Poner "us." antes del modelos en BEDROCK_MODEL

### 2. Instalar Dependencias Python

```bash
pip install -r requirements.txt
```

### 3. Ejecutar la API

```bash
uvicorn main:app --reload
```

La API estará disponible en: `http://localhost:8000`

Documentación interactiva: `http://localhost:8000/docs`
