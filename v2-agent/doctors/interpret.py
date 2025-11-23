from fastapi import HTTPException
from models import (
    TriageRequest, 
    TriageResponse,
    AppointmentInterpretRequest,
    AppointmentInterpretResponse,
    WorkshopInterpretRequest,
    WorkshopInterpretResponse,
    Request
)
from typing import List
import boto3
import json
import datetime
import csv
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session_manager import get_session_manager
from doctors.dynamodb_query import ejecutar_consultas_simple
from rag_helper import retrieve_context, format_context_for_prompt

from datetime import date

def build_prompt(req, triage_context=None, conversation_history=None, rag_context=None):
    # Sección de RAG si existe
    rag_section = ""
    if rag_context:
        rag_section = f"""
    ────────────────────────────────────────
    INFORMACIÓN RELEVANTE DE LA BASE DE CONOCIMIENTO (RAG)
    ────────────────────────────────────────
    A continuación tienes información ya buscada en una base de conocimiento.
    Puede incluir doctores disponibles, descripciones de especialidades, talleres,
    recomendaciones generales u otra información de salud.

    CONTENIDO:
    {rag_context}

    REGLAS PARA USAR ESTE CONTEXTO:
    - Usa esta información como tu PRINCIPAL fuente para recomendar doctores,
      describir opciones y responder dudas del usuario.
    - Puedes mencionar doctores, clínicas, talleres u opciones SOLO si aparecen
      en este contexto.
    - NO inventes doctores, clínicas ni datos médicos que no estén en el RAG.
    - Si el RAG está vacío o no es suficiente, haz preguntas claras al usuario
      para entender mejor qué necesita.
    """

    # Sección de triage previo
    context_section = ""
    if triage_context:
        especialidad = triage_context.get('especialidad_sugerida')
        capa = triage_context.get('capa')
        razones = triage_context.get('razones', [])

        context_section = f"""
    ────────────────────────────────────────
    CONTEXTO DE TRIAJE PREVIO
    ────────────────────────────────────────
    El usuario tuvo una consulta de triaje reciente con estos resultados:

    - Especialidad sugerida: {especialidad or 'No especificada'}
    - Nivel de atención (Capa): {capa or 'No especificado'}
    - Razones principales: {', '.join(razones) if razones else 'No especificadas'}

    REGLAS:
    - Puedes usar esta información para entender mejor qué tipo de atención
      podría necesitar el usuario (por ejemplo, priorizar cierta especialidad).
    - Si el usuario no especifica especialidad ahora, puedes mencionar la
      especialidad sugerida por el triage como posible opción, pero SIEMPRE
      preguntando y sin imponerla.
    """

    # Sección de historial de conversación
    history_section = ""
    if conversation_history:
        history_section = f"""
    ────────────────────────────────────────
    HISTORIAL DE CONVERSACIÓN RECIENTE
    ────────────────────────────────────────
    El usuario ya ha dicho lo siguiente en turnos anteriores:

    {conversation_history}

    CÓMO USAR EL HISTORIAL:
    - ACUMULA la información del historial con el mensaje actual.
      Ejemplo:
      * Historial: "quiero cita con cardiólogo"
      * Mensaje actual: "para mañana"
      → Debes tratarlo como "cita con cardiólogo para mañana".
    - NO vuelvas a preguntar por datos que el usuario ya dio (especialidad,
      distrito, modalidad, fecha, etc.), a menos que ahora los cambie.
    - Si el usuario corrige algo ("mejor que sea neurólogo"), respeta la nueva
      preferencia y actualiza tu respuesta.
    """

    prompt_base = """
    Eres un asistente virtual especializado en ayudar a los usuarios a agendar
    o entender opciones de citas médicas.

    SIEMPRE respondes en ESPAÑOL, con un tono:
    - Claro
    - Cercano
    - Profesional
    - Empático

    Tu tarea en este agente es SÓLO redactar una RESPUESTA EN LENGUAJE NATURAL
    para el usuario, usando:

    1) El mensaje actual del usuario
    2) El historial de conversación (si existe)
    3) El contexto de triage (si existe)
    4) La información de la base de conocimiento (RAG)

    IMPORTANTE:
    - YA NO debes generar NINGUNA consulta a bases de datos.
    - NO debes mencionar ni usar tablas de DynamoDB.
    - NO debes hablar de índices, queries, ni nada técnico.
    - NO debes devolver JSON ni estructuras técnicas: solo texto para el usuario.

    {rag_section}
    {context_section}
    {history_section}

    ────────────────────────────────────────
    CÓMO DEBES RESPONDER
    ────────────────────────────────────────

    1. Usa primero el RAG:
    - Si hay doctores en el contexto, sugiere algunos (2–4 máximo), mencionando:
        * nombre_completo
        * hospital o clínica
        * distrito (si está disponible)
        * modalidad (presencial / telemedicina) si aparece
    - Si hay talleres, guías u otra información útil, puedes mencionarla brevemente.

    2. Usa el historial y el triage para PERSONALIZAR:
    - Si el historial indica ya una especialidad, una zona o modalidad preferida,
        tenlo en cuenta al elegir qué doctores mencionar.
    - Si el triage sugiere una especialidad, puedes hacer ver al usuario que
        esa especialidad podría ser adecuada, pero siempre con cuidado y sin
        diagnosticar.

    3. Si FALTA información clave:
    - Haz preguntas claras y concretas:
        * "¿Prefieres consulta presencial o virtual?"
        * "¿En qué distrito te gustaría atenderte?"
        * "¿Para qué día deseas la cita?"
    - NO repitas preguntas que ya fueron respondidas antes.

    4. NUNCA diagnostiques:
    - No des diagnósticos ni nombres de enfermedades.
    - No prescribas tratamientos ni medicamentos.
    - Puedes hablar de "evaluación médica", "control", "seguimiento", etc.

    5. Estructura de la respuesta:
    - Un primer párrafo donde:
        * Agradeces o reconoces lo que el usuario dijo.
        * Le das un resumen corto de lo que encontraste (si hay doctores/talleres).
    - Opcionalmente, una lista corta con 2–4 opciones de doctores u opciones.
    - Un último párrafo con:
        * Preguntas adicionales (solo si son necesarias).
        * Una breve advertencia, por ejemplo:
        "Recuerda que este asistente no reemplaza una evaluación médica profesional."

    6. Si el RAG no trae nada útil:
    - Explícale al usuario que no encontraste información suficiente en la base
        de conocimiento para responder bien.
    - Haz 1–3 preguntas para entender mejor lo que necesita.
    - Mantén el tono positivo y de ayuda.

    ────────────────────────────────────────
    SALIDA ESPERADA
    ────────────────────────────────────────

    Debes devolver ÚNICAMENTE el mensaje en lenguaje natural que se mostrará al usuario.
    No incluyas JSON, ni etiquetas, ni explicaciones técnicas.

    ────────────────────────────────────────

    Fecha actual: {fecha_actual}

    Mensaje del usuario: {message}
    """

    # misma lógica de escape de llaves
    safe_prompt = prompt_base.replace("{", "{{").replace("}", "}}")

    fecha_actual = date.today().strftime("%Y-%m-%d")

    safe_prompt = safe_prompt.replace("{{fecha_actual}}", "{fecha_actual}")
    safe_prompt = safe_prompt.replace("{{message}}", "{message}")
    safe_prompt = safe_prompt.replace("{{context_section}}", "{context_section}")
    safe_prompt = safe_prompt.replace("{{history_section}}", "{history_section}")
    safe_prompt = safe_prompt.replace("{{rag_section}}", "{rag_section}")

    prompt = safe_prompt.format(
        fecha_actual=fecha_actual,
        message=req.message,
        context_section=context_section,
        history_section=history_section,
        rag_section=rag_section,
    )

    return prompt


def build_doctors_reply_prompt(response_json: dict) -> str:
    """
    response_json = lo que te devolvió el agente doctors/interpret
    (la clave 'response' del JSON que pegaste).
    """
    import json

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
    - Ejemplo: "¿Prefieres consulta presencial o virtual? ¿En qué distrito te gustaría la consulta? ¿Para qué día deseas tu cita?"

    4. Si `requiere_mas_informacion` es false:
    - No pidas más datos, enfócate en ofrecer opciones concretas o el siguiente paso.

    5. Mantén el mensaje corto y accionable:
    - 1–2 párrafos máximo, más una lista con 2–4 doctores si aplica.
    - No menciones palabras técnicas como "DynamoDB", "consulta_doctores", "criterios", etc.

    6. Termina siempre con una invitación amable a elegir una opción o responder a las preguntas.

    7. Incluye una breve advertencia al final, por ejemplo:
    "Recuerda que este asistente no reemplaza una evaluación médica profesional."

    Ahora genera el MENSAJE para el usuario, en texto plano.
    """
    return prompt


def interpret_appointment_request(req: TriageRequest) -> dict:
    """
    Interpreta la solicitud del usuario usando Bedrock y ejecuta la operación correspondiente.
    """
    
    bedrock_runtime = boto3.client(
        service_name='bedrock-runtime',
        region_name='us-east-1'
    )

    # Retrieve triage context and conversation history from session
    triage_context = None
    conversation_summary = ""
    try:
        session_manager = get_session_manager()
        triage_context = session_manager.get_triage_context(req.user_id)
        if triage_context:
            print(f"Found triage context for user {req.user_id}: {triage_context.get('especialidad_sugerida')}")
        
        # Get conversation history
        conversation_summary = session_manager.get_conversation_summary(req.user_id)
        if conversation_summary:
            print(f"Found conversation history for user {req.user_id}")
    except Exception as e:
        print(f"Warning: Could not retrieve context: {str(e)}")

    # SIEMPRE consultar RAG primero para obtener contexto relevante
    rag_context_str = ""
    rag_documents = []
    try:
        print(f"Consultando RAG para el mensaje: {req.message[:50]}...")
        rag_result = retrieve_context(
            query=req.message,
            user_id=req.user_id,
            max_results=3
        )
        if rag_result.get('documents'):
            rag_documents = rag_result['documents']
            rag_context_str = format_context_for_prompt(rag_documents)
            print(f"Retrieved {len(rag_documents)} documents from RAG")
    except Exception as e:
        print(f"Warning: Could not retrieve RAG context: {str(e)}")
        # Continuar sin RAG si falla

    # Llamada a Bedrock con RAG context incluido
    prompt = build_prompt(req, triage_context, conversation_summary, rag_context_str)

    region = os.getenv("BEDROCK_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN") or os.getenv(
        "BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    })

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.invoke_model(
        modelId=model_id,
        body=body,
        accept="application/json",
        contentType="application/json",
    )

    print("IMPORTANT !!!!")
    # First parse the response body
    raw_response = response["body"].read()
    print(f"Raw response: {raw_response}")
    
    parsed_response = json.loads(raw_response)
    print(f"Parsed response: {parsed_response}")
    
    # Extract the text content (this is natural language, not JSON)
    content_text = parsed_response["content"][0]["text"]
    print(f"Content text: {content_text}")
    
    if not content_text.strip():
        raise ValueError("Empty response from Bedrock model")

    # Update session to track last endpoint and save conversation turn
    try:
        session_manager = get_session_manager()
        session_manager.update_session(req.user_id, {
            'last_endpoint': 'doctors/interpret'
        })
        
        # Save this conversation turn
        session_manager.add_conversation_turn(
            req.user_id,
            req.message,
            content_text,
            'doctors/interpret'
        )
    except Exception as e:
        print(f"Warning: Could not update session: {str(e)}")

    # Devolver en el formato esperado
    return {
        "endpoint": "doctors/interpret",
        "confidence": 0.9,
        "reasoning": "Solicitud de cita médica o consulta con doctor",
        "message": content_text,
        "response": {
            "message": content_text
        }
    }    