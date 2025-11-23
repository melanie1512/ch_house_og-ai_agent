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
    # TODO: corregir dia_semana
    
    # Build RAG context section if available
    rag_section = ""
    if rag_context:
        rag_section = f"""
    ────────────────────────────────────────
    INFORMACIÓN RELEVANTE DE LA BASE DE CONOCIMIENTO
    ────────────────────────────────────────
    {rag_context}
    
    IMPORTANTE: Esta información está disponible para enriquecer tu comprensión del contexto.
    
    Usa esta información para:
    - Hacer preguntas más específicas y contextualizadas cuando necesites más información
    - Entender mejor el contexto médico o de salud del usuario
    - Proporcionar información relevante en tus respuestas
    - Ayudar al usuario a tomar mejores decisiones
    
    NO uses esta información para:
    - Inventar criterios de búsqueda que el usuario no mencionó
    - Asumir preferencias del usuario sin preguntarle
    - Generar consultas de DynamoDB con información no confirmada por el usuario
    
    NOTA: Esta información será usada posteriormente para generar respuestas en lenguaje
    natural más ricas y contextualizadas para el usuario.
    """
    
    # Build context section if triage data is available
    context_section = ""
    if triage_context:
        especialidad = triage_context.get('especialidad_sugerida')
        capa = triage_context.get('capa')
        razones = triage_context.get('razones', [])
        
        context_section = f"""
    ────────────────────────────────────────
    CONTEXTO DE TRIAJE PREVIO
    ────────────────────────────────────────
    El usuario tuvo una consulta de triaje reciente con los siguientes resultados:
    
    - Especialidad sugerida: {especialidad or 'No especificada'}
    - Nivel de atención (Capa): {capa or 'No especificado'}
    - Razones: {', '.join(razones) if razones else 'No especificadas'}
    
    IMPORTANTE: Si el usuario solicita una cita sin especificar especialidad,
    DEBES usar la especialidad sugerida del triaje ({especialidad}) como criterio
    de búsqueda predeterminado.
    
    Si el usuario menciona una especialidad diferente, usa la que mencione.
    """
    
    # Build conversation history section
    history_section = ""
    if conversation_history:
        history_section = """
    ────────────────────────────────────────
    HISTORIAL DE CONVERSACIÓN RECIENTE
    ────────────────────────────────────────
    El usuario ha tenido las siguientes interacciones recientes:
    
    """
        history_section += conversation_history
        history_section += """
    
    REGLAS CRÍTICAS PARA USAR EL HISTORIAL:
    
    1. ACUMULAR CRITERIOS: Debes COMBINAR la información del historial con el mensaje actual.
       - Si en el historial se mencionó "cardiólogo", y ahora el usuario dice "mañana",
         debes generar una consulta con AMBOS criterios: especialidad=Cardiología Y fecha=mañana
    
    2. NO OLVIDAR INFORMACIÓN PREVIA: La información del historial sigue siendo válida
       a menos que el usuario la contradiga explícitamente.
       - Historial: "quiero cita con cardiólogo"
       - Usuario ahora: "para mañana"
       - Resultado: especialidad=Cardiología, fecha=mañana (NO preguntar especialidad de nuevo)
    
    3. NO REPETIR PREGUNTAS: Si el usuario ya respondió algo, NO vuelvas a preguntarlo.
       - Si ya dijo la especialidad, NO preguntes "¿con qué especialidad?"
       - Si ya dijo la fecha, NO preguntes "¿para qué día?"
    
    4. DETECTAR RESPUESTAS A PREGUNTAS PREVIAS: Si el sistema preguntó algo y el usuario
       responde, interpreta la respuesta en el contexto de la pregunta.
       - Sistema preguntó: "¿Para qué día?"
       - Usuario responde: "mañana"
       - Debes interpretar "mañana" como la fecha Y mantener los criterios previos
    
    5. PRIORIDAD: Mensaje actual > Historial (solo si hay contradicción explícita)
       - Si el usuario dice "mejor con un neurólogo", cambia la especialidad
       - Si el usuario solo agrega información, COMBINA con el historial
    """
    
    prompt_base = """
    Eres un asistente especializado en interpretar solicitudes de citas médicas.
    Tu única tarea es LEER el mensaje del usuario en lenguaje natural y devolver
    UN JSON con criterios estructurados para buscar doctores y horarios en una
    base de datos DynamoDB.

    NO debes diagnosticar enfermedades.
    NO debes sugerir tratamientos.
    NO debes inventar doctores ni datos clínicos.
    Siempre trabajas en ESPAÑOL.
    {rag_section}
    {context_section}
    {history_section}

    ────────────────────────────────────────
    FECHA ACTUAL
    ────────────────────────────────────────
    La fecha actual es: {fecha_actual}

    Debes usar esta fecha exacta para interpretar referencias temporales tales como:
    - "mañana"
    - "pasado mañana"
    - "este lunes"
    - "la próxima semana"
    - "la siguiente semana"
    - "la próxima semana por la tarde"
    - "esta noche"
    - "fin de semana"
    - "el próximo viernes"
    - "en dos días"

    Reglas:
    1. Convierte cualquier referencia temporal relativa en una fecha concreta 
    en formato "YYYY-MM-DD".

    2. Si el usuario menciona un día de la semana sin fecha exacta 
    (ej. “el viernes”), determina si se refiere al próximo día de la semana 
    a partir de {fecha_actual}.  
    Ejemplo: si hoy es martes 2025-03-04, “viernes” = 2025-03-07.

    3. "próxima semana" significa la semana inmediatamente posterior a esta,
    comenzando en lunes.

    4. Si la fecha no puede determinarse, deja "fecha": null y "dia_semana": null.

    ────────────────────────────────────────
    DATOS DISPONIBLES EN LA BASE DE DATOS
    ────────────────────────────────────────

    En DynamoDB existen dos tablas:

    1) Tabla "doctores":
    doctor_id, nombre_completo, genero, especialidad, subespecialidad,
    años_experiencia, idiomas, hospital, departamento, distrito,
    tipo_consulta, tags, descripcion_breve, telefono, email

    2) Tabla "horarios_doctores":
    doctor_id, dia_semana, hora_inicio, hora_fin, zona_horaria,
    modo, departamento, distrito

    Tu trabajo es SOLO producir criterios de búsqueda, NO hacer la búsqueda.

    ────────────────────────────────────────
    ESPECIALIDAD
    ────────────────────────────────────────
    Cuando elijas una especialidad, asegurate de usar una de la siguiente lista de especialidades:
    
    - Radiología
    - Medicina de Emergencias
    - Neurología
    - Medicina Familiar
    - Neumología
    - Cardiología
    - Medicina Interna
    - Pediatría
    - Dermatología
    - Reumatología

    NO la reescribas, devuelve el texto tal como aparece ahí.

    ────────────────────────────────────────
    CÓMO INTERPRETAR EL MENSAJE DEL USUARIO
    ────────────────────────────────────────

    A partir del mensaje del usuario Y EL HISTORIAL, debes identificar:

    1) ACCIÓN (campo "accion"):
    - "buscar"
    - "agendar"
    - "cancelar"
    - "ver_citas"
    - "necesita_mas_informacion"

    2) CRITERIOS (campo "criterios"):
    
    IMPORTANTE: Debes ACUMULAR criterios del historial + mensaje actual.
    
    Proceso:
    a) Extrae criterios del HISTORIAL (especialidad, modalidad, fecha, etc.)
    b) Extrae criterios del MENSAJE ACTUAL
    c) COMBINA ambos (mensaje actual sobrescribe solo si hay contradicción)
    d) Genera consulta con TODOS los criterios acumulados
    
    Criterios disponibles:
    - especialidad (ej. "cardiología")
    - subespecialidad (si aplica)
    - genero_preferido ("femenino", "masculino", o null)
    - idioma_preferido (ej. "Inglés")
    - modalidad ("virtual" o "presencial")
    - fecha (YYYY-MM-DD o null)
    - dia_semana ("Lunes"... o null)
    - hora_preferida (rango de horas)
    - departamento
    - distrito

    Ejemplo de acumulación:
    - Turno 1: Usuario: "quiero cita con cardiólogo" → especialidad=Cardiología
    - Turno 2: Usuario: "para mañana" → especialidad=Cardiología (del historial), fecha=mañana (nuevo)
    - Turno 3: Usuario: "en Lima" → especialidad=Cardiología, fecha=mañana, departamento=Lima

    3) Pedir más información ("requiere_mas_informacion": true) cuando la solicitud
    no pueda interpretarse razonablemente sin datos clave:
    - Sin especialidad (y no está en el historial)
    - Sin preferencia de modalidad cuando es relevante
    - Sin ubicación cuando es necesaria para cita presencial
    - Sin fecha cuando el usuario pide explícitamente una fecha

    4) "derivar_a":
    - null
    - "triage/interpret"
    - "workshops/interpret"

    ────────────────────────────────────────
    REGLAS PARA HACER PREGUNTAS AL USUARIO
    ────────────────────────────────────────

    Si NO tienes información suficiente para generar una consulta útil en DynamoDB,
    DEBES pedir más información al usuario.

    Ejemplos de casos donde debes preguntar más:

    - Falta ubicación cuando la modalidad es presencial (departamento y/o distrito).
    - Falta la especialidad o no puede inferirse.
    - El usuario dice "quiero una cita" pero no especifica con qué tipo de doctor.
    - El usuario pide buscar horario pero no menciona día ni rango horario.
    - El usuario menciona un horario pero NO menciona la modalidad (virtual/presencial).
    - El usuario menciona “esta semana” pero no especifica día ni preferencia de horario.
    - El usuario pide “quiero una doctora” pero no dice la especialidad.
    - El usuario pide "quiero una cita mañana" pero no dice especialidad, modalidad o distrito.

    Cuando falte información crítica:

    - No intentes generar consultas incompletas.
    - Establece `"requiere_mas_informacion": true`.
    - Llena `"pregunta_pendiente"` con una pregunta concreta, clara y necesaria.
    - NO inventes información.
    - Si tienes información de la base de conocimiento (sección RAG arriba), úsala SOLO
      para hacer preguntas más contextualizadas, NO para generar consultas.

    Ejemplos de preguntas válidas:

    - "¿Con qué especialidad médica deseas atenderte?"
    - "¿Prefieres consulta presencial o virtual?"
    - "¿En qué distrito te gustaría la consulta?"
    - "¿Te gustaría atenderte por la mañana, tarde o noche?"
    - "¿Para qué día deseas tu cita?"

    Si tienes contexto RAG, puedes enriquecer las preguntas:
    - "Veo que mencionas [síntoma/condición]. ¿Deseas una cita con [especialidad relacionada]?"
    - "Para [condición mencionada], normalmente se recomienda [especialidad]. ¿Te gustaría buscar disponibilidad?"

    Hasta que no tengas los criterios mínimos, debes devolver:

    "consulta_doctores": {},
    "consulta_horarios": []

    y esperar la respuesta del usuario.

    ────────────────────────────────────────
    FORMATO DE RESPUESTA OBLIGATORIO
    ────────────────────────────────────────

    Debes responder SIEMPRE con un JSON válido y NADA MÁS:

    {
    "accion": "...",

    "criterios": {
        "especialidad": "string or null",
        "subespecialidad": "string or null",
        "genero_preferido": "masculino" | "femenino" | null,
        "idioma_preferido": "string or null",
        "modalidad": "virtual" | "presencial" | null,
        "fecha": "YYYY-MM-DD or null",
        "dia_semana": "Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo or null",
        "hora_preferida": {
        "rango": "mañana" | "tarde" | "noche" | null,
        "inicio": "HH:MM or null",
        "fin": "HH:MM or null"
        } | null,
        "departamento": "string or null",
        "distrito": "string or null"
    },

    "doctores_encontrados": [],
    "horarios_disponibles": [],

    "requiere_mas_informacion": true | false,
    "pregunta_pendiente": "string or null",

    "derivar_a": null | "triage/interpret" | "workshops/interpret",

    "advertencia": "Este asistente no reemplaza una evaluación médica profesional."
    }

     ────────────────────────────────────────
    REGLA DE FLEXIBILIDAD EN LOS FILTROS
    ────────────────────────────────────────

    IMPORTANTE:
    NO todos los filtros son obligatorios para generar una consulta válida.

    Puedes generar una consulta DynamoDB aunque falten varios criterios,
    siempre y cuando exista al menos UN criterio que permita iniciar la búsqueda.

    Ejemplos:
    - Si se conoce solo la especialidad → genera consulta por especialidad.
    - Si se conoce solo el distrito → genera consulta por distrito.
    - Si se conoce solo la modalidad → no hay índice para modalidad, pero IGUAL genera scan.
    - Si se conoce solo el doctor_id → genera consulta de horarios.
    - Si no se conoce la fecha exacta pero sí el día de la semana → usa ese filtro.
    - Si no existe GSI para un campo → genera scan y NO inventes índices.

    En resumen:
    **NO rechaces la consulta solo porque falte información.  
    Usa lo que sí esté disponible.  
    Y si falta algo crítico para garantizar la mejor recomendación, pregunta.**

    ────────────────────────────────────────
    GENERACIÓN DE CONSULTA PARA DYNAMODB
    ────────────────────────────────────────

    Además de interpretar la intención, DEBES generar las consultas listas para que el backend
    pueda ejecutarlas en DynamoDB.

    IMPORTANTE: Usa TODOS los criterios acumulados (historial + mensaje actual) para generar
    la consulta más específica posible.

    Dependiendo de los criterios, debes generar uno o ambos objetos:

    1) "consulta_doctores":
    Query o Scan para la tabla "doctores".

    2) "consulta_horarios":
    Query para la tabla "horarios_doctores" basada en doctor_id y filtros adicionales.

    Reglas:
    - Si el criterio incluye "especialidad", usa el índice GSI "especialidad-index".
    - Si el criterio incluye "departamento", usa "departamento-index".
    - Si el criterio incluye "distrito", usa "distrito-index".
    - Si el criterio incluye "modalidad" (virtual/presencial), filtra en backend,
    pero incluye la intención en la consulta.
    - Para horarios:
    * Siempre consulta por "doctor_id" usando KeyConditionExpression.
    * Filtros de rango horario deben expresarse usando FilterExpression.
    
    Ejemplo con acumulación de criterios:
    - Historial: Usuario mencionó "cardiólogo"
    - Mensaje actual: "para mañana en Lima"
    - Criterios acumulados: especialidad=Cardiología, fecha=2025-XX-XX, departamento=Lima
    - Consulta: Usa especialidad-index CON filtros de fecha y departamento

    Ejemplo de formato (NO inventes doctores):

    "consulta_doctores": {
    "TableName": "doctores",
    "IndexName": "especialidad-index",
    "KeyConditionExpression": "especialidad = :esp",
    "ExpressionAttributeValues": {
        ":esp": "cardiología"
    }
    },

    "consulta_horarios": {
    "TableName": "horarios_doctores",
    "KeyConditionExpression": "doctor_id = :doc",
    "ExpressionAttributeValues": {
        ":doc": "DOC-0001"
    },
    "FilterExpression": "dia_semana = :dia AND hora_inicio <= :fin AND hora_fin >= :inicio",
    "ExpressionAttributeValues": {
        ":dia": "Domingo",
        ":inicio": "06:00",
        ":fin": "12:00"
    }
    }

    SIEMPRE devuelve estos campos aunque estén vacíos:

    "consulta_doctores": {},
    "consulta_horarios": []

    ────────────────────────────────────────

    DEBES responder con el JSON final:

    {
    "accion": "...",
    "criterios": {...},
    "consulta_doctores": {...},
    "consulta_horarios": [...],
    "requiere_mas_informacion": true|false,
    "pregunta_pendiente": "...",
    "derivar_a": null | "triage/interpret" | "workshops/interpret",
    "advertencia": "Este asistente no reemplaza una evaluación médica profesional."
    }

    ────────────────────────────────────────



    Ahora interpreta el MENSAJE DEL USUARIO usando la fecha actual {fecha_actual}
    y devuelve EXCLUSIVAMENTE un JSON válido.

    Mensaje del usuario: {message}

    """

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
        rag_section=rag_section
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


def interpret_appointment_request(req: TriageRequest) -> TriageResponse:
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
    
    response_body = json.loads(json.loads(response["body"].read())["content"][0]["text"])
    
    # Agregar documentos RAG a la respuesta para uso posterior
    response_body['rag_documents'] = rag_documents

    # Ejecutar las consultas de DynamoDB si existen
    if response_body.get("consulta_doctores") or response_body.get("consulta_horarios"):
        try:
            resultados = ejecutar_consultas_simple(response_body, region=region)
            
            # Agregar los resultados al response
            response_body["doctores_encontrados"] = resultados.get("doctores", [])
            response_body["horarios_disponibles"] = resultados.get("horarios", [])
            
        except Exception as e:
            print(f"Error ejecutando consultas DynamoDB: {str(e)}")
            # Continuar sin resultados si hay error
            response_body["doctores_encontrados"] = []
            response_body["horarios_disponibles"] = []

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
            response_body,
            'doctors/interpret'
        )
    except Exception as e:
        print(f"Warning: Could not update session: {str(e)}")

    return response_body    