# Health Assistant API v2 - Guía de Integración Frontend

API de asistente de salud con routing inteligente usando AWS Bedrock (Claude 3), RAG y DynamoDB.

## 🚀 Quick Start

### Base URL
```
https://yjj52729vy.us-east-1.awsapprunner.com/
```

### Endpoint Principal

**POST `/agent/route`** - Endpoint único para todas las consultas

El sistema automáticamente determina si es triaje, búsqueda de doctores o talleres.

## 📡 API Reference

### Request Format

```typescript
interface Request {
  user_id: string;      // ID único del usuario (requerido)
  message: string;      // Mensaje en lenguaje natural
}
```

### Response Format

```typescript
interface Response {
  endpoint: string;           // "triage/interpret" | "doctors/interpret" | "workshops/interpret"
  confidence: number;         // 0.0 - 1.0
  reasoning: string;          // Por qué se eligió este endpoint
  message: string;            // Respuesta en lenguaje natural para mostrar al usuario
  response: object;           // Datos estructurados (varía según endpoint)
}
```

## 💬 Ejemplos de Uso

### Ejemplo 1: Triaje de Síntomas

**Request:**
```json
{
  "user_id": "user_123",
  "message": "Me duele el pecho y sudo frío"
}
```

**Response:**
```json
{
  "endpoint": "triage/interpret",
  "confidence": 0.95,
  "reasoning": "El usuario describe síntomas que requieren evaluación médica",
  "message": "EMERGENCIA - Capa 4. El dolor de pecho con sudoración fría puede indicar un infarto agudo de miocardio. Llama al 911 inmediatamente o acude al hospital más cercano.",
  "response": {
    "capa": 4,
    "razones": ["dolor de pecho intenso", "sudoración fría", "posible infarto"],
    "especialidad_sugerida": "cardiología",
    "accion_recomendada": "llamar_emergencias",
    "requiere_mas_informacion": false,
    "derivar_a": null
  }
}
```

### Ejemplo 2: Búsqueda de Doctores

**Request:**
```json
{
  "user_id": "user_123",
  "message": "Quiero una cita con un cardiólogo en Lima para mañana"
}
```

**Response:**
```json
{
  "endpoint": "doctors/interpret",
  "confidence": 0.92,
  "reasoning": "El usuario solicita agendar una cita médica",
  "message": "Encontré 3 cardiólogos disponibles en Lima para mañana. La cardiología se especializa en el diagnóstico y tratamiento de enfermedades del corazón. Aquí están tus opciones: Dr. Juan Pérez (Hospital ABC), Dra. María García (Clínica XYZ)...",
  "response": {
    "accion": "buscar",
    "criterios": {
      "especialidad": "Cardiología",
      "modalidad": null,
      "fecha": "2025-11-24",
      "departamento": "Lima",
      "distrito": null
    },
    "doctores_encontrados": [
      {
        "doctor_id": "DOC-001",
        "nombre_completo": "Dr. Juan Pérez",
        "especialidad": "Cardiología",
        "hospital": "Hospital ABC",
        "distrito": "Miraflores",
        "tipo_consulta": "presencial"
      }
    ],
    "requiere_mas_informacion": false
  }
}
```

### Ejemplo 3: Talleres de Bienestar

**Request:**
```json
{
  "user_id": "user_123",
  "message": "Busco talleres para manejar el estrés"
}
```

**Response:**
```json
{
  "endpoint": "workshops/interpret",
  "confidence": 0.88,
  "reasoning": "El usuario busca talleres de bienestar",
  "message": "Encontré 4 talleres de manejo de estrés. El estrés crónico puede afectar tu salud cardiovascular, pero técnicas como mindfulness han demostrado reducir significativamente los niveles de estrés. ¿Te gustaría ver las opciones?",
  "response": {
    "operation": "SEARCH",
    "workshops": [
      {
        "workshop_id": "ws_001",
        "title": "Manejo del Estrés con Mindfulness",
        "topic": "STRESS",
        "date": "2025-11-25",
        "start_time": "14:00",
        "end_time": "16:00",
        "modality": "VIRTUAL",
        "location": "Virtual"
      }
    ],
    "message": "Encontré 4 talleres disponibles"
  }
}
```

## 🔄 Conversaciones Multi-Turno

El sistema mantiene contexto entre mensajes del mismo `user_id`:

**Turno 1:**
```json
{
  "user_id": "user_123",
  "message": "Quiero una cita con un cardiólogo"
}
```
Response: "¿Para qué día deseas tu cita?"

**Turno 2:**
```json
{
  "user_id": "user_123",
  "message": "Para mañana"
}
```
Response: "Encontré 3 cardiólogos disponibles para mañana..." 
(El sistema recuerda que buscas cardiólogo)

## 📋 Tipos de Respuesta por Endpoint

### Triage Response

```typescript
interface TriageResponse {
  capa: 1 | 2 | 3 | 4;                    // Nivel de urgencia
  razones: string[];                       // Razones de la clasificación
  especialidad_sugerida: string | null;    // Especialidad recomendada
  accion_recomendada: string;              // "contactar_medico_virtual" | "solicitar_medico_a_domicilio" | "consulta_presencial" | "llamar_emergencias"
  requiere_mas_informacion: boolean;
  derivar_a: string | null;                // Puede derivar a "doctors/interpret"
}
```

**Capas de Atención:**
- **Capa 1**: Médico virtual (síntomas leves)
- **Capa 2**: Médico a domicilio (moderado)
- **Capa 3**: Consulta presencial/especialista
- **Capa 4**: Emergencia médica (llamar 911)

### Doctors Response

```typescript
interface DoctorsResponse {
  accion: string;                          // "buscar" | "agendar" | "ver_citas"
  criterios: {
    especialidad: string | null;
    modalidad: "virtual" | "presencial" | null;
    fecha: string | null;                  // YYYY-MM-DD
    departamento: string | null;
    distrito: string | null;
  };
  doctores_encontrados: Doctor[];
  requiere_mas_informacion: boolean;
  pregunta_pendiente: string | null;
}

interface Doctor {
  doctor_id: string;
  nombre_completo: string;
  especialidad: string;
  hospital: string;
  distrito: string;
  tipo_consulta: "presencial" | "telemedicina";
}
```

### Workshops Response

```typescript
interface WorkshopsResponse {
  operation: "SEARCH" | "LIST_MY_WORKSHOPS" | "REGISTER";
  workshops: Workshop[];
  registered_workshop?: Workshop;
  message: string;
}

interface Workshop {
  workshop_id: string;
  title: string;
  topic: "STRESS" | "SLEEP" | "NUTRITION" | "ANXIETY" | "GENERAL";
  date: string;                            // YYYY-MM-DD
  start_time: string;                      // HH:MM
  end_time: string;                        // HH:MM
  modality: "VIRTUAL" | "IN_PERSON";
  location: string;
}
```

## 🎨 UI/UX Recommendations

### Mostrar el Campo `message`

El campo `message` en la respuesta contiene texto en lenguaje natural optimizado para mostrar directamente al usuario:

```typescript
// ✅ Recomendado
<ChatBubble>
  {response.message}
</ChatBubble>

// ❌ No recomendado (no construyas el mensaje manualmente)
<ChatBubble>
  {response.response.capa === 4 ? "Emergencia" : "Normal"}
</ChatBubble>
```

### Manejo de Emergencias (Capa 4)

```typescript
if (response.response.capa === 4) {
  // Mostrar con estilo de alerta
  return (
    <Alert severity="error" icon={<EmergencyIcon />}>
      <AlertTitle>EMERGENCIA MÉDICA</AlertTitle>
      {response.message}
      <Button color="error" onClick={call911}>
        Llamar 911
      </Button>
    </Alert>
  );
}
```

### Conversaciones

```typescript
// Mantener el mismo user_id en toda la conversación
const [userId] = useState(() => generateUserId());

const sendMessage = async (message: string) => {
  const response = await fetch('/agent/route', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,  // Mismo ID para toda la sesión
      message
    })
  });
  
  const data = await response.json();
  
  // Mostrar el mensaje al usuario
  addMessageToChat({
    role: 'assistant',
    content: data.message
  });
};
```

## 🔒 CORS Configuration

La API está configurada con CORS. En producción, asegúrate de que tu dominio esté en la lista de orígenes permitidos.

```env
ALLOWED_ORIGINS=https://tu-frontend.com,https://app.tu-frontend.com
```

## ⚡ Performance Tips

1. **Reutiliza `user_id`**: Mantén el mismo ID durante toda la sesión del usuario
2. **Timeout**: Las respuestas típicamente toman 1-3 segundos
3. **Retry Logic**: Implementa reintentos con backoff exponencial
4. **Loading States**: Muestra indicadores de carga mientras esperas la respuesta

## 🐛 Error Handling

```typescript
try {
  const response = await fetch('/agent/route', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id, message })
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error en la solicitud');
  }
  
  const data = await response.json();
  return data;
  
} catch (error) {
  console.error('Error:', error);
  // Mostrar mensaje de error al usuario
  showError('No pudimos procesar tu mensaje. Por favor intenta de nuevo.');
}
```

## 📊 Response Status Codes

- **200**: Éxito
- **400**: Request inválido (falta `user_id` o `message`)
- **500**: Error interno del servidor

## 🔧 Local Development

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd v2-agent

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar .env
cp .env.example .env
# Editar .env con tus credenciales AWS

# 4. Ejecutar servidor
uvicorn main:app --reload

# API disponible en http://localhost:8000
# Docs interactivos en http://localhost:8000/docs
```

## 📚 Additional Resources

- **Swagger/OpenAPI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `GET /` (returns API info)

## 🆘 Support

Para preguntas o issues, contacta al equipo de backend o revisa la documentación técnica completa en los archivos `.md` del repositorio.
