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
  - Tabla `user_sessions`: Gestión de sesiones y contexto entre agentes (TTL: 1 hora)
- **IAM**: Permisos para Bedrock y DynamoDB

## Session Management (Cross-Agent Context)

El sistema incluye **gestión de sesiones** que permite compartir contexto entre diferentes agentes. Esto es especialmente útil para el flujo:

1. **Usuario describe síntomas** → Triage agent analiza y recomienda especialidad
2. **Usuario solicita cita** → Doctors agent usa la especialidad recomendada automáticamente

### Cómo Funciona

- Cada interacción de triage guarda: `especialidad_sugerida`, `capa`, `razones`
- Las sesiones expiran automáticamente después de 1 hora (TTL)
- El doctors agent lee el contexto de triage para pre-llenar búsquedas
- Almacenamiento ligero: solo el contexto necesario, no historial completo

### Ejemplo de Flujo

```
Usuario: "Me duele el pecho y tengo fiebre"
→ Triage: Guarda {especialidad: "Cardiología", capa: 3}

Usuario: "Quiero agendar una cita"
→ Doctors: Lee especialidad "Cardiología" del contexto
→ Busca automáticamente cardiólogos disponibles
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
  "message": "Entiendo que tienes dolor de pecho y fiebre. Basándome en tus síntomas, te recomiendo una consulta presencial con un especialista en Cardiología. ¿Te gustaría que te ayude a agendar una cita?",
  "response": {
    "capa": 3,
    "especialidad_sugerida": "Cardiología",
    "razones": ["Dolor de pecho", "Fiebre"],
    "accion_recomendada": "consulta_presencial"
  }
}
```

**Nota:** El campo `message` contiene la respuesta en lenguaje natural para mostrar al usuario, mientras que `response` contiene los datos estructurados para la lógica interna.

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

### 3. Crear Tabla de Sesiones en DynamoDB

```bash
python setup_session_table.py
```

Este script crea la tabla `user_sessions` con:
- Partition key: `user_id`
- TTL habilitado en el atributo `ttl` (expiración automática después de 1 hora)
- Billing mode: PAY_PER_REQUEST

### 4. (Opcional) Probar Session Manager

```bash
python test_session_manager.py
```

Este script verifica que:
- Las sesiones se guardan correctamente
- El contexto de triage se puede recuperar
- El flujo cross-agent funciona
- Las sesiones se pueden limpiar

### 5. Ejecutar la API

```bash
uvicorn main:app --reload
```

La API estará disponible en: `http://localhost:8000`

Documentación interactiva: `http://localhost:8000/docs`

## Testing Cross-Agent Context Flow

Para probar el flujo completo de contexto entre agentes:

```bash
# Asegúrate de que la API esté corriendo
uvicorn main:app --reload

# En otra terminal, ejecuta el ejemplo
python example_cross_agent_flow.py
```

Este script demuestra:
1. Usuario describe síntomas → Triage recomienda especialidad
2. Usuario pide cita → Doctors usa la especialidad automáticamente
3. No es necesario repetir información

Ver `SESSION_MANAGEMENT.md` para documentación completa del sistema de sesiones.

## Variables de Entorno

Agregar a tu archivo `.env`:

```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key

# Bedrock Configuration
BEDROCK_REGION=us-east-1
BEDROCK_MODEL=us.anthropic.claude-3-haiku-20240307-v1:0
# O usar inference profile:
# BEDROCK_INFERENCE_PROFILE_ARN=arn:aws:bedrock:us-east-1:...

# Session Management (opcional, usa defaults si no se especifica)
SESSION_TABLE_NAME=user_sessions
```
