from fastapi import HTTPException
from models import (
    WorkshopInterpretRequest,
    WorkshopInterpretResponse,
    WorkshopOperation,
    WorkshopIntent,
    WorkshopFilters,
    WorkshopSummary,
    WorkshopTopic,
    WorkshopModality
)
from typing import List
import boto3
import json
import datetime
import csv
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rag_helper import retrieve_context, format_context_for_prompt


def load_workshops_from_csv(file_path: str = "workshops.csv") -> List[dict]:
    """Carga talleres desde el CSV"""
    workshops = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                workshops.append(row)
    except FileNotFoundError:
        pass
    return workshops


def interpret_workshop_request(req: WorkshopInterpretRequest) -> WorkshopInterpretResponse:
    """
    Interpreta la solicitud del usuario usando Bedrock y ejecuta la operación correspondiente.
    """
    
    bedrock_runtime = boto3.client(
        service_name='bedrock-runtime',
        region_name='us-east-1'
    )
    
    # SIEMPRE consultar RAG primero para obtener contexto sobre talleres y bienestar
    rag_context_str = ""
    rag_documents = []
    try:
        print(f"Consultando RAG para workshops: {req.message[:50]}...")
        rag_result = retrieve_context(
            query=req.message,
            user_id=req.user_id,
            max_results=3
        )
        if rag_result.get('documents'):
            rag_documents = rag_result['documents']
            rag_context_str = format_context_for_prompt(rag_documents)
            print(f"Retrieved {len(rag_documents)} documents from RAG for workshops")
    except Exception as e:
        print(f"Warning: Could not retrieve RAG context for workshops: {str(e)}")
        # Continuar sin RAG si falla
    
    prompt = f"""Eres un asistente que ayuda a interpretar solicitudes sobre talleres de bienestar.

Analiza el siguiente mensaje y extrae la información en formato JSON:

Mensaje: "{req.message}"

Responde con un JSON en este formato:
{{
    "operation": "SEARCH" | "LIST_MY_WORKSHOPS" | "REGISTER",
    "filters": {{
        "topic": "stress_management" | "sleep_hygiene" | "nutrition" | "anxiety_management" | "general_wellbeing" | "any",
        "date": "YYYY-MM-DD o null",
        "time_of_day": "texto libre o null",
        "modality": "virtual" | "in_person" | "any",
        "location": "ubicación o null"
    }},
    "workshop_id": "ID del taller si menciona registrarse en uno específico, o null"
}}"""

    # Usar el mismo modelo que el resto del sistema
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
    
    response = bedrock_runtime.invoke_model(
        modelId=model_id,
        body=body
    )
    
    response_body = json.loads(response['body'].read())
    content = response_body['content'][0]['text']
    
    # Extraer JSON
    start_idx = content.find('{')
    end_idx = content.rfind('}') + 1
    json_str = content[start_idx:end_idx]
    intent_data = json.loads(json_str)
    
    operation = WorkshopOperation(intent_data['operation'])
    
    # Ejecutar operación
    if operation == WorkshopOperation.SEARCH:
        workshops_data = load_workshops_from_csv()
        filters = intent_data.get('filters', {})
        
        # Filtrar talleres según criterios
        filtered_workshops = workshops_data
        if filters.get('topic') and filters['topic'] != 'any':
            topic = filters['topic'].lower()
            filtered_workshops = [w for w in filtered_workshops if topic in w.get('topic', '').lower()]
        
        # Crear workshops de ejemplo
        workshops = []
        for i, workshop in enumerate(filtered_workshops[:5]):  # Máximo 5 resultados
            workshops.append(WorkshopSummary(
                workshop_id=workshop.get('workshop_id', f'ws_{i+1}'),
                title=workshop.get('title', 'Taller de Bienestar'),
                topic=WorkshopTopic.GENERAL,
                date=datetime.date.today() + datetime.timedelta(days=i+2),
                start_time=datetime.time(14, 0),
                end_time=datetime.time(16, 0),
                modality=WorkshopModality.VIRTUAL,
                location=workshop.get('location', 'Virtual'),
                description=workshop.get('description', 'Taller de bienestar')
            ))
        
        message = f"Encontré {len(workshops)} talleres disponibles."
        if filters.get('topic') and filters['topic'] != 'any':
            message += f" Tema: {filters['topic']}."
        
        response = WorkshopInterpretResponse(
            operation=operation,
            workshops=workshops,
            message=message
        )
        # Agregar documentos RAG para uso en respuesta en lenguaje natural
        response.rag_documents = rag_documents
        return response
    
    elif operation == WorkshopOperation.LIST_MY_WORKSHOPS:
        # Listar talleres del usuario (ejemplo)
        workshops = [
            WorkshopSummary(
                workshop_id="ws_user_001",
                title="Manejo del Estrés",
                topic=WorkshopTopic.STRESS,
                date=datetime.date.today() + datetime.timedelta(days=5),
                start_time=datetime.time(15, 0),
                end_time=datetime.time(17, 0),
                modality=WorkshopModality.VIRTUAL,
                location="Virtual",
                description="Técnicas para manejar el estrés diario"
            )
        ]
        
        response = WorkshopInterpretResponse(
            operation=operation,
            workshops=workshops,
            message=f"Tienes {len(workshops)} taller(es) registrado(s)."
        )
        response.rag_documents = rag_documents
        return response
    
    elif operation == WorkshopOperation.REGISTER:
        # Registrar en taller
        workshop = WorkshopSummary(
            workshop_id=intent_data.get('workshop_id', 'ws_001'),
            title="Higiene del Sueño",
            topic=WorkshopTopic.SLEEP,
            date=datetime.date.today() + datetime.timedelta(days=7),
            start_time=datetime.time(18, 0),
            end_time=datetime.time(20, 0),
            modality=WorkshopModality.VIRTUAL,
            location="Virtual",
            description="Mejora tu calidad de sueño"
        )
        
        response = WorkshopInterpretResponse(
            operation=operation,
            registered_workshop=workshop,
            message=f"Te has registrado exitosamente en el taller '{workshop.title}'."
        )
        response.rag_documents = rag_documents
        return response
    
    response = WorkshopInterpretResponse(
        operation=operation,
        message="Operación completada."
    )
    response.rag_documents = rag_documents
    return response
