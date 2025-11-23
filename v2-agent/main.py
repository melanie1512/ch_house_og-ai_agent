# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

app = FastAPI(title="Health Assistant API with Bedrock Router", version="2.0.0")
load_dotenv()

# Inicializar el router de Bedrock

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    return interpret_triage_request(req);


@app.post("/doctors/interpret", response_model=AppointmentInterpretResponse)
def doctors_interpret(req: AppointmentInterpretRequest):
    """Endpoint para búsqueda y gestión de citas médicas"""
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido.")
    
    return interpret_appointment_request(req)


@app.post("/workshops/interpret", response_model=WorkshopInterpretResponse)
def workshops_interpret(req: WorkshopInterpretRequest):
    """Endpoint para búsqueda y registro en talleres"""
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido.")
    
    return interpret_workshop_request(req)


@app.post("/agent/route")
def agent_route(req: Request):
    """
    Endpoint principal del agente router.
    Usa AWS Bedrock para determinar a qué servicio derivar la consulta.
    """

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

    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido.")
    
    # 1) Usar MAIN prompt para determinar el tipo de uso

    region = os.getenv("BEDROCK_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN") or os.getenv(
        "BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )

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

    routing_decision = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )

    response = json.loads(routing_decision["body"].read())
    routing_decision = json.loads(response["content"][0]["text"])
    endpoint = routing_decision["endpoint"]

    # TODO: add a validator for the categorization
    
    # 2) Llamar al endpoint correspondiente
    # try:
    if endpoint == "triage/interpret":
        triage_req = TriageRequest(user_id=req.user_id, message=req.message)
        response = triage_interpret(triage_req)
        return {
            "endpoint": endpoint,
            "confidence": routing_decision['confidence'],
            "reasoning": routing_decision['reasoning'],
            "response": response
        }
    
    elif endpoint == "doctors/interpret":
        doctors_req = AppointmentInterpretRequest(user_id=req.user_id, message=req.message)
        response = doctors_interpret(doctors_req)
        return {
            "endpoint": endpoint,
            "confidence": routing_decision['confidence'],
            "reasoning": routing_decision['reasoning'],
            "response": response
        }
    
    elif endpoint == "workshops/interpret":
        workshops_req = WorkshopInterpretRequest(user_id=req.user_id, message=req.message)
        response = workshops_interpret(workshops_req)
        return {
            "endpoint": endpoint,
            "confidence": routing_decision['confidence'],
            "reasoning": routing_decision['reasoning'],
            "response": response
        }
    
    else:
        raise HTTPException(status_code=400, detail=f"Endpoint desconocido: {endpoint}")
    
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Error procesando la solicitud: {str(e)}")
