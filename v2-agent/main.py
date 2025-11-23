# main.py
from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

from models import (
    TriageRequest, 
    TriageResponse,
    AppointmentInterpretRequest,
    AppointmentInterpretResponse,
    WorkshopInterpretRequest,
    WorkshopInterpretResponse,
    Request
)
from triage.interpret import interpret_triage_request
from doctors.interpret import interpret_appointment_request
from workshops.interpret import interpret_workshop_request
from dotenv import load_dotenv
import os
import json
import boto3

# Import logging configuration
from logging_config import (
    setup_logging,
    get_logger,
    get_request_logger,
    log_error,
    log_request_start,
    log_request_end
)

# Initialize logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Health Assistant API with Bedrock Router", version="2.0.0")
load_dotenv()

logger.info("Health Assistant API starting up")

# Configure CORS based on environment
def get_cors_origins():
    """
    Get allowed CORS origins from environment variable.
    In production, wildcard is not allowed.
    """
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    logger.info(f"Configuring CORS for environment: {environment}")
    
    if allowed_origins_env:
        # Parse comma-separated origins
        origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
        
        # In production, ensure wildcard is not used
        if environment == "production" and "*" in origins:
            error_msg = "Wildcard '*' is not allowed in ALLOWED_ORIGINS for production environment"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"CORS origins configured: {origins}")
        return origins
    else:
        # Default behavior: wildcard only in development
        if environment == "production":
            error_msg = "ALLOWED_ORIGINS must be explicitly set in production environment"
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.info("CORS origins: wildcard (development mode)")
        return ["*"]

cors_origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: FastAPIRequest, call_next):
    """
    Middleware to log all HTTP requests with timing information.
    
    Requirements: 9.1, 9.3
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Extract user_id if present in request body (for POST requests)
    user_id = None
    
    # Log request start
    log_request_start(
        logger,
        endpoint=request.url.path,
        extra={
            'request_id': request_id,
            'method': request.method,
            'client_host': request.client.host if request.client else None
        }
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log request completion
        log_request_end(
            logger,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            extra={
                'request_id': request_id,
                'method': request.method
            }
        )
        
        return response
        
    except Exception as e:
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log error
        log_error(
            logger,
            e,
            f"Request failed: {request.url.path}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'duration_ms': duration_ms
            }
        )
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )


@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest):
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido para mantener el historial.")

    history = get_history(req.user_id)
    append_message(req.user_id, "user", req.message)

    # 1) Extract structured symptoms via LLM
    summary = extract_symptoms_with_llm(req.message, history)

    if (summary.language or "").lower().split("-")[0] != "es":
        raise HTTPException(status_code=400, detail="Solo se aceptan mensajes en español.")


    # 2) Assess risk via rule engine
    risk = assess_risk(summary)

    print(risk.model_dump_json(indent=2))

    # 3) Build natural language reply
    reply = build_triage_reply(summary, risk, history)

    append_message(req.user_id, "assistant", reply)

    # 4) (optional) log to DB here (user_id, message, summary, risk, etc.)

    return TriageResponse(
        risk=risk,
        reply=reply,
    )

@app.post("/triage/interpret", response_model=TriageResponse)
def triage_interpret(req: TriageRequest):
    """Endpoint específico para triaje de síntomas"""
    request_logger = get_request_logger(__name__, user_id=req.user_id, endpoint="/triage/interpret")
    
    try:
        request_logger.info("Processing triage request")
        result = interpret_triage_request(req)
        request_logger.info("Triage request completed successfully", extra={
            'extra_fields': {'capa': result.get('capa'), 'accion': result.get('accion_recomendada')}
        })
        return result
    except Exception as e:
        log_error(request_logger, e, "Failed to process triage request", {'user_id': req.user_id})
        raise HTTPException(status_code=500, detail=f"Error procesando triaje: {str(e)}")


@app.post("/doctors/interpret", response_model=AppointmentInterpretResponse)
def doctors_interpret(req: AppointmentInterpretRequest):
    """Endpoint para búsqueda y gestión de citas médicas"""
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido.")
    
    request_logger = get_request_logger(__name__, user_id=req.user_id, endpoint="/doctors/interpret")
    
    try:
        request_logger.info("Processing appointment request")
        result = interpret_appointment_request(req)
        request_logger.info("Appointment request completed successfully", extra={
            'extra_fields': {
                'accion': result.get('accion'),
                'doctores_encontrados': len(result.get('doctores_encontrados', []))
            }
        })
        return result
    except Exception as e:
        log_error(request_logger, e, "Failed to process appointment request", {'user_id': req.user_id})
        raise HTTPException(status_code=500, detail=f"Error procesando cita: {str(e)}")


@app.post("/workshops/interpret", response_model=WorkshopInterpretResponse)
def workshops_interpret(req: WorkshopInterpretRequest):
    """Endpoint para búsqueda y registro en talleres"""
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido.")
    
    request_logger = get_request_logger(__name__, user_id=req.user_id, endpoint="/workshops/interpret")
    
    try:
        request_logger.info("Processing workshop request")
        result = interpret_workshop_request(req)
        request_logger.info("Workshop request completed successfully", extra={
            'extra_fields': {
                'operation': result.operation.value if hasattr(result, 'operation') else None,
                'workshops_found': len(result.workshops) if hasattr(result, 'workshops') else 0
            }
        })
        return result
    except Exception as e:
        log_error(request_logger, e, "Failed to process workshop request", {'user_id': req.user_id})
        raise HTTPException(status_code=500, detail=f"Error procesando taller: {str(e)}")

def build_doctors_reply_prompt(response_json: dict) -> str:
    """
    response_json = lo que te devolvió el agente doctors/interpret
    (la clave 'response' del JSON que pegaste).
    """
    import json

    # Extraer documentos RAG si están disponibles
    rag_documents = response_json.get('rag_documents', [])
    rag_context_section = ""
    
    if rag_documents:
        rag_context_section = "\n\n────────────────────────────────────\n"
        rag_context_section += "CONTEXTO ADICIONAL DE LA BASE DE CONOCIMIENTO\n"
        rag_context_section += "────────────────────────────────────\n"
        rag_context_section += "Tienes acceso a la siguiente información relevante que puedes usar para enriquecer tu respuesta:\n\n"
        
        for i, doc in enumerate(rag_documents[:2], 1):  # Máximo 2 documentos
            content = doc.get('content', '')
            source = doc.get('source', 'Base de conocimiento')
            rag_context_section += f"{i}. {content}\n   (Fuente: {source})\n\n"
        
        rag_context_section += "Usa esta información para:\n"
        rag_context_section += "- Proporcionar contexto médico relevante si aplica\n"
        rag_context_section += "- Explicar por qué una especialidad es apropiada\n"
        rag_context_section += "- Dar recomendaciones más informadas\n"
        rag_context_section += "- Hacer que tu respuesta sea más útil y educativa\n"

    prompt = f"""
    Eres un asistente de atención al paciente.

    Recibirás un JSON llamado `response` que contiene el resultado estructurado de un
    agente previo que ya interpretó la intención del usuario y buscó doctores.

    Tu ÚNICA tarea es escribir un MENSAJE EN TEXTO NATURAL para el usuario,
    en ESPAÑOL latino neutro, usando un tono cercano, claro y profesional.

    No devuelvas JSON, solo texto.

    ────────────────────────────────────
    JSON DE ENTRADA (response)
    ────────────────────────────────────
    {json.dumps(response_json, ensure_ascii=False, indent=2)}
    {rag_context_section}

    ────────────────────────────────────
    REGLAS PARA GENERAR EL MENSAJE
    ────────────────────────────────────

    1. Si `doctores_encontrados` tiene elementos:
    - Indica cuántos doctores se encontraron (usa len(doctores_encontrados)).
    - Menciona de 2 a 4 doctores como máximo, en forma de lista o frases cortas.
        De cada uno, incluye SOLO:
        - nombre_completo
        - hospital
        - distrito
        - tipo_consulta (presencial / telemedicina)
    - No inventes datos nuevos.

    2. Si `doctores_encontrados` está vacío:
    - Explica que por ahora no se encontraron doctores que cumplan todos los criterios.
    - Propón relajar algún filtro (por ejemplo distrito, horario, modalidad).

    3. Si `requiere_mas_informacion` es true:
    - Incluye SIEMPRE una o varias preguntas claras basadas en `pregunta_pendiente`.
    - Puedes reformularla para que suene natural, pero sin cambiar su sentido.
    - Si hay contexto de la base de conocimiento, úsalo para hacer preguntas más contextualizadas
    - Ejemplo: "¿Prefieres consulta presencial o virtual? ¿En qué distrito te gustaría la consulta? ¿Para qué día deseas tu cita?"

    4. Si `requiere_mas_informacion` es false:
    - No pidas más datos, enfócate en ofrecer opciones concretas o el siguiente paso.
    - Si hay contexto de la base de conocimiento, úsalo para enriquecer tu respuesta con información relevante

    5. Mantén el mensaje corto y accionable:
    - 1–2 párrafos máximo, más una lista con 2–4 doctores si aplica.
    - Si incluyes información del contexto RAG, hazlo de forma natural y breve (1 oración)
    - No menciones palabras técnicas como "DynamoDB", "consulta_doctores", "criterios", etc.

    6. Termina siempre con una invitación amable a elegir una opción o responder a las preguntas.

    7. Incluye una breve advertencia al final, por ejemplo:
    "Recuerda que este asistente no reemplaza una evaluación médica profesional."

    8. Si hay contexto de la base de conocimiento:
    - Úsalo para proporcionar información adicional relevante
    - Explica brevemente por qué una especialidad es apropiada si aplica
    - Ayuda al usuario a entender mejor su situación
    - Mantén la información médica simple y accesible

    Ahora genera el MENSAJE para el usuario, en texto plano.
    """
    return prompt

def generate_natural_language_response(endpoint: str, response_data: dict, user_message: str) -> str:
    """
    Genera un mensaje en lenguaje natural basado en la respuesta estructurada del agente.
    """
    func_logger = get_logger(__name__)
    func_logger.info(f"Generating natural language response for endpoint: {endpoint}")
    
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN") or os.getenv(
        "BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    
    # Construir el prompt según el tipo de endpoint
    if endpoint == "triage/interpret":
        capa = response_data.get('capa')
        especialidad = response_data.get('especialidad_sugerida')
        razones = response_data.get('razones', [])
        accion = response_data.get('accion_recomendada')
        derivar_a = response_data.get('derivar_a')
        rag_documents = response_data.get('rag_documents', [])
        
        # Formatear contexto RAG si está disponible
        rag_context_section = ""
        if rag_documents:
            rag_context_section = "\n\nContexto médico adicional de la base de conocimiento:\n"
            for i, doc in enumerate(rag_documents[:2], 1):  # Usar máximo 2 documentos
                content = doc.get('content', '')[:300]  # Limitar a 300 caracteres
                rag_context_section += f"- {content}...\n"
        
        prompt = f"""Eres un asistente de salud empático y profesional. Genera una respuesta en lenguaje natural 
        para el usuario basándote en el siguiente análisis de triaje:

        Mensaje del usuario: "{user_message}"

        Análisis de triaje:
        - Nivel de atención (Capa): {capa}
        - Especialidad sugerida: {especialidad or 'No especificada'}
        - Razones: {', '.join(razones) if razones else 'No especificadas'}
        - Acción recomendada: {accion}
        - Derivar a: {derivar_a or 'Ninguno'}
        {rag_context_section}

        Genera una respuesta que:
        1. Sea empática y tranquilizadora
        2. Explique el nivel de atención recomendado de forma clara
        3. Si hay especialidad sugerida, menciónala y explica brevemente por qué es apropiada
        4. Si hay contexto médico de la base de conocimiento, úsalo para:
           - Explicar por qué ciertos síntomas requieren atención urgente
           - Proporcionar contexto sobre la especialidad recomendada
           - Ayudar al usuario a entender mejor su situación
           - Mantener la información médica simple y accesible
        5. Indique los próximos pasos de forma clara
        6. Si se recomienda agendar cita, ofrece ayuda para hacerlo
        7. Sea concisa (máximo 4-5 oraciones)
        8. Use un tono profesional pero cercano
        9. Si es Capa 4 (emergencia), enfatiza la urgencia de forma clara pero sin alarmar innecesariamente

        Responde SOLO con el mensaje para el usuario, sin formato adicional."""

    elif endpoint == "doctors/interpret":
        prompt = build_doctors_reply_prompt(response_data)

    elif endpoint == "workshops/interpret":
        operation = response_data.get('operation')
        workshops = response_data.get('workshops', [])
        registered = response_data.get('registered_workshop')
        rag_documents = response_data.get('rag_documents', [])
        
        # Formatear contexto RAG si está disponible
        rag_context_section = ""
        if rag_documents:
            rag_context_section = "\n\nContexto sobre bienestar de la base de conocimiento:\n"
            for i, doc in enumerate(rag_documents[:2], 1):  # Usar máximo 2 documentos
                content = doc.get('content', '')[:300]  # Limitar a 300 caracteres
                rag_context_section += f"- {content}...\n"
        
        prompt = f"""Eres un asistente de salud que ayuda con talleres de bienestar. Genera una respuesta en lenguaje natural 
        para el usuario basándote en el siguiente análisis:

        Mensaje del usuario: "{user_message}"

        Análisis:
        - Operación: {operation}
        - Talleres encontrados: {len(workshops)}
        - Taller registrado: {registered.get('title') if registered else 'Ninguno'}
        {rag_context_section}

        Genera una respuesta que:
        1. Si encontró talleres, menciona cuántos y el tema
        2. Si registró en un taller, confirma la inscripción con entusiasmo
        3. Si listó talleres del usuario, resume la información
        4. Si hay contexto de la base de conocimiento, úsalo para:
           - Explicar los beneficios del taller o tema
           - Proporcionar información sobre por qué es importante
           - Motivar al usuario con datos relevantes
           - Hacer la respuesta más educativa y valiosa
        5. Sea motivadora y positiva
        6. Sea concisa (máximo 4-5 oraciones)
        7. Use un tono amigable y alentador

        Responde SOLO con el mensaje para el usuario, sin formato adicional."""
    
    else:
        return "Gracias por tu mensaje. Estoy procesando tu solicitud."
    
    # Llamar a Bedrock para generar el mensaje
    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "temperature": 0.7,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ],
        }
        
        start_time = time.time()
        llm_response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
        duration_ms = (time.time() - start_time) * 1000
        
        response_json = json.loads(llm_response["body"].read())
        natural_message = response_json["content"][0]["text"].strip()
        
        func_logger.info(f"Natural language response generated in {duration_ms:.2f}ms")
        return natural_message
        
    except Exception as e:
        log_error(func_logger, e, "Error generating natural language response", {'endpoint': endpoint})
        # Fallback message
        return "Gracias por tu mensaje. He procesado tu solicitud y aquí está la información que necesitas."


@app.post("/agent/route")
def agent_route(req: Request):
    """
    Endpoint principal del agente router.
    Usa AWS Bedrock para determinar a qué servicio derivar la consulta.
    """
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido.")
    
    request_logger = get_request_logger(__name__, user_id=req.user_id, endpoint="/agent/route")
    request_logger.info("Processing agent routing request")

    user_message = req.message

    system_prompt = """Eres un asistente de salud cuya función es CLASIFICAR el mensaje del usuario y decidir
    a cuál de los siguientes servicios debe ser DERIVADO. NO debes hacer triaje clínico,
    NO debes interpretar síntomas a nivel médico y NO debes dar recomendaciones de salud.
    Tu única tarea es la clasificación.

    Servicios disponibles:

    1. triage/interpret
    - Cuando el usuario describe síntomas, malestares, dolor, molestias físicas o emocionales.
    - Cuando pregunta si algo es grave, urgente o “qué hacer”.
    - Cuando menciona duración de síntomas (horas/días).
    - Cuando su mensaje sugiere riesgo, enfermedad, empeoramiento o señales de alarma.
    - Cuando pide orientación médica general o evaluación de urgencia.

    2. doctors/interpret
    - Cuando el usuario desea agendar/cancelar/modificar una cita médica.
    - Cuando solicita ver sus citas.
    - Cuando pregunta a qué DOCTOR o ESPECIALISTA debe ir.
    - Cuando busca disponibilidad, horarios o modalidad (virtual/presencial) de médicos.

    3. workshops/interpret
    - Cuando busca talleres de bienestar: estrés, sueño, ansiedad leve, nutrición, hábitos saludables.
    - Cuando desea registrarse en un taller o saber los horarios disponibles.
    - Cuando pide recomendaciones de actividades preventivas o de autocuidado.

    REGLAS IMPORTANTES:
    - Siempre responde en ESPAÑOL.
    - NO inventes información clínica. NO diagnostiques. NO evalúes severidad.
    - Tu salida debe ser EXCLUSIVAMENTE un JSON. No agregues texto adicional.
    - Incluye siempre un campo "confidence" entre 0.0 y 1.0.
    - Incluye "reasoning" con una explicación breve.

    FORMATO DE RESPUESTA OBLIGATORIO:
    {
        "endpoint": "triage/interpret" | "doctors/interpret" | "workshops/interpret",
        "confidence": float,
        "reasoning": "breve explicación en español"
    }

    Ahora analiza el siguiente mensaje del usuario y determina el endpoint correcto:

    Mensaje del usuario: "{user_message}"
    """
    
    # 1) Usar MAIN prompt para determinar el tipo de uso
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN") or os.getenv(
        "BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "temperature": 0,
            "system": [{"type": "text", "text": system_prompt}],
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": user_message}]}
            ],
        }

        request_logger.info("Calling Bedrock for routing decision")
        start_time = time.time()
        
        routing_decision = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
        
        duration_ms = (time.time() - start_time) * 1000
        request_logger.info(f"Bedrock routing call completed in {duration_ms:.2f}ms")

        response = json.loads(routing_decision["body"].read())
        routing_decision = json.loads(response["content"][0]["text"])
        endpoint = routing_decision["endpoint"]
        
        request_logger.info(f"Routing decision: {endpoint}", extra={
            'extra_fields': {
                'endpoint': endpoint,
                'confidence': routing_decision.get('confidence')
            }
        })

    except Exception as e:
        log_error(request_logger, e, "Failed to get routing decision from Bedrock", {'user_id': req.user_id})
        raise HTTPException(status_code=500, detail=f"Error en routing: {str(e)}")

    # TODO: add a validator for the categorization
    
    # 2) Llamar al endpoint correspondiente
    try:
        if endpoint == "triage/interpret":
            triage_req = TriageRequest(user_id=req.user_id, message=req.message)
            response = triage_interpret(triage_req)
            
            # Generar mensaje en lenguaje natural
            natural_message = generate_natural_language_response(endpoint, response, user_message)
            
            request_logger.info("Agent routing completed successfully", extra={
                'extra_fields': {'routed_to': endpoint}
            })
            
            return {
                "endpoint": endpoint,
                "confidence": routing_decision['confidence'],
                "reasoning": routing_decision['reasoning'],
                "message": natural_message,
                "response": response
            }
        
        elif endpoint == "doctors/interpret":
            doctors_req = AppointmentInterpretRequest(user_id=req.user_id, message=req.message)
            response = doctors_interpret(doctors_req)
            
            # Generar mensaje en lenguaje natural
            natural_message = generate_natural_language_response(endpoint, response, user_message)
            
            request_logger.info("Agent routing completed successfully", extra={
                'extra_fields': {'routed_to': endpoint}
            })
            
            return {
                "endpoint": endpoint,
                "confidence": routing_decision['confidence'],
                "reasoning": routing_decision['reasoning'],
                "message": natural_message,
                "response": response
            }
        
        elif endpoint == "workshops/interpret":
            workshops_req = WorkshopInterpretRequest(user_id=req.user_id, message=req.message)
            response = workshops_interpret(workshops_req)
            
            # Convertir respuesta Pydantic a diccionario para generate_natural_language_response
            response_dict = response.dict() if hasattr(response, 'dict') else response.model_dump()
            
            # Generar mensaje en lenguaje natural
            natural_message = generate_natural_language_response(endpoint, response_dict, user_message)
            
            request_logger.info("Agent routing completed successfully", extra={
                'extra_fields': {'routed_to': endpoint}
            })
            
            return {
                "endpoint": endpoint,
                "confidence": routing_decision['confidence'],
                "reasoning": routing_decision['reasoning'],
                "message": natural_message,
                "response": response
            }
        
        else:
            request_logger.error(f"Unknown endpoint: {endpoint}")
            raise HTTPException(status_code=400, detail=f"Endpoint desconocido: {endpoint}")
    
    except HTTPException:
        raise
    except Exception as e:
        log_error(request_logger, e, "Error processing routed request", {'user_id': req.user_id, 'endpoint': endpoint})
        raise HTTPException(status_code=500, detail=f"Error procesando la solicitud: {str(e)}")
