# Guía de Configuración - Bedrock Agent

## Opción 1: Script Automático (Recomendado) ⚡

El script `setup_bedrock_agent.sh` configura todo automáticamente:

```bash
cd v2-agent
./setup_bedrock_agent.sh
```

Esto creará:
- ✅ Roles IAM necesarios
- ✅ Lambda function con el handler
- ✅ Bedrock Agent con 3 action groups
- ✅ Alias del agente
- ✅ Actualizará tu archivo .env

**Requisitos:**
- AWS CLI instalado y configurado
- Permisos para crear recursos en IAM, Lambda y Bedrock
- Modelo Claude 3 Sonnet habilitado en tu región

---

## Opción 2: Configuración Manual en AWS Console 🖱️

### Paso 1: Desplegar Lambda Function

```bash
cd v2-agent
./deploy_lambda.sh
```

O manualmente:
1. Ve a AWS Lambda Console
2. Create function → Author from scratch
3. Name: `bedrock-health-agent-actions`
4. Runtime: Python 3.11
5. Copia el código de `lambda_handler.py`
6. Deploy

### Paso 2: Crear Bedrock Agent

1. Ve a **AWS Bedrock Console** → **Agents**
2. Click **Create Agent**

**Configuración básica:**
- Agent name: `health-assistant-agent`
- Model: `Claude 3 Sonnet`
- Instructions:
```
Eres un asistente de salud inteligente que ayuda a usuarios con:

1. Evaluación de síntomas y triaje médico
2. Búsqueda y agendamiento de citas con doctores
3. Búsqueda y registro en talleres de bienestar

Cuando un usuario te consulte:
- Si menciona síntomas, dolor, malestar o emergencias → usa TriageActionGroup
- Si busca doctores, citas médicas o especialistas → usa DoctorsActionGroup
- Si busca talleres, bienestar, estrés o nutrición → usa WorkshopsActionGroup

Siempre responde en español de manera amable y profesional.
```

### Paso 3: Crear Action Groups

#### Action Group 1: TriageActionGroup

1. En tu agente, ve a **Action groups** → **Add**
2. Name: `TriageActionGroup`
3. Description: `Evalúa síntomas y determina nivel de riesgo médico`
4. Action group type: **Define with API schemas**
5. Lambda function: Selecciona `bedrock-health-agent-actions`
6. API Schema: Copia el contenido de abajo

<details>
<summary>Ver OpenAPI Schema para Triage</summary>

```yaml
openapi: 3.0.0
info:
  title: Triage API
  version: 1.0.0
  description: API para evaluación de síntomas y triaje médico

paths:
  /triage/interpret:
    post:
      summary: Evalúa síntomas del usuario
      description: Analiza los síntomas reportados y determina el nivel de riesgo
      operationId: evaluateSymptoms
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - user_id
                - message
              properties:
                user_id:
                  type: string
                  description: ID del usuario
                message:
                  type: string
                  description: Descripción de síntomas del usuario
      responses:
        '200':
          description: Evaluación completada
          content:
            application/json:
              schema:
                type: object
                properties:
                  risk:
                    type: object
                    properties:
                      risk_level:
                        type: string
                        enum: [EMERGENCY, URGENT, ROUTINE, SELF_CARE]
                      recommended_action:
                        type: string
                      reasons:
                        type: array
                        items:
                          type: string
                  reply:
                    type: string
```
</details>

#### Action Group 2: DoctorsActionGroup

Repite el proceso con:
- Name: `DoctorsActionGroup`
- Description: `Busca doctores y gestiona citas médicas`
- Lambda: `bedrock-health-agent-actions`

<details>
<summary>Ver OpenAPI Schema para Doctors</summary>

```yaml
openapi: 3.0.0
info:
  title: Doctors API
  version: 1.0.0
  description: API para búsqueda de doctores y gestión de citas

paths:
  /doctors/interpret:
    post:
      summary: Busca doctores o gestiona citas
      description: Interpreta solicitudes de búsqueda de doctores o gestión de citas
      operationId: manageDoctorAppointments
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - user_id
                - message
              properties:
                user_id:
                  type: string
                message:
                  type: string
      responses:
        '200':
          description: Operación completada
          content:
            application/json:
              schema:
                type: object
                properties:
                  operation:
                    type: string
                    enum: [LIST, CREATE, CANCEL]
                  appointments:
                    type: array
                    items:
                      type: object
                  message:
                    type: string
```
</details>

#### Action Group 3: WorkshopsActionGroup

- Name: `WorkshopsActionGroup`
- Description: `Busca talleres de bienestar y gestiona inscripciones`
- Lambda: `bedrock-health-agent-actions`

<details>
<summary>Ver OpenAPI Schema para Workshops</summary>

```yaml
openapi: 3.0.0
info:
  title: Workshops API
  version: 1.0.0
  description: API para talleres de bienestar

paths:
  /workshops/interpret:
    post:
      summary: Busca talleres o gestiona inscripciones
      description: Interpreta solicitudes sobre talleres de bienestar
      operationId: manageWorkshops
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - user_id
                - message
              properties:
                user_id:
                  type: string
                message:
                  type: string
      responses:
        '200':
          description: Operación completada
          content:
            application/json:
              schema:
                type: object
                properties:
                  operation:
                    type: string
                    enum: [SEARCH, LIST_MY_WORKSHOPS, REGISTER]
                  workshops:
                    type: array
                    items:
                      type: object
                  message:
                    type: string
```
</details>

### Paso 4: Preparar y Crear Alias

1. Click **Prepare** (arriba a la derecha)
2. Espera a que termine la preparación (~1-2 minutos)
3. Ve a **Aliases** → **Create alias**
4. Name: `production`
5. Create

### Paso 5: Obtener IDs

1. En la página del agente, copia el **Agent ID** (ej: `ABCDEFGHIJ`)
2. En Aliases, copia el **Alias ID** (ej: `TSTALIASID`)

### Paso 6: Configurar .env

Actualiza tu archivo `.env`:

```bash
BEDROCK_AGENT_ID=ABCDEFGHIJ
BEDROCK_AGENT_ALIAS_ID=TSTALIASID
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
```

---

## Probar el Agente 🧪

```bash
# Iniciar servidor
uvicorn main_agent:app --reload

# En otra terminal, ejecutar tests
python test_bedrock_agent.py
```

O probar manualmente:

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "Me duele la cabeza desde hace 2 días"
  }'
```

---

## Troubleshooting 🔧

### Error: "Agent not found"
- Verifica que el AGENT_ID en .env sea correcto
- Asegúrate de que el agente esté en estado "Prepared"

### Error: "Access denied"
- Verifica que tus credenciales AWS tengan permisos para Bedrock
- Revisa que el rol del agente tenga permisos para invocar Lambda

### Error: "Model not available"
- Ve a Bedrock Console → Model access
- Solicita acceso a Claude 3 Sonnet
- Espera aprobación (puede tomar unos minutos)

### Lambda no se invoca
- Verifica que Lambda tenga permiso para ser invocada por Bedrock
- Revisa CloudWatch Logs de la Lambda para ver errores

---

## Arquitectura Final

```
Usuario
  ↓
POST /agent/chat
  ↓
FastAPI (main_agent.py)
  ↓
BedrockAgentCore
  ↓
AWS Bedrock Agent (Claude 3)
  ↓
Analiza mensaje → Decide action group
  ↓
  ├─→ TriageActionGroup
  ├─→ DoctorsActionGroup
  └─→ WorkshopsActionGroup
  ↓
Lambda (lambda_handler.py)
  ↓
Procesa y retorna resultado
  ↓
Bedrock genera respuesta natural
  ↓
Usuario recibe respuesta
```

---

## Costos Estimados 💰

- **Bedrock Agent**: ~$0.003 por 1000 tokens
- **Claude 3 Sonnet**: ~$0.003 input / $0.015 output por 1K tokens
- **Lambda**: Primeros 1M invocaciones gratis, luego $0.20 por 1M
- **Estimado por conversación**: $0.01 - $0.05

---

## Recursos Adicionales 📚

- [AWS Bedrock Agents Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Claude 3 Model Card](https://docs.anthropic.com/claude/docs/models-overview)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
