# triage/symptom_extraction.py
import json
import os

import boto3
from dotenv import load_dotenv

from typing import List, Optional

from .models import SymptomSummary
from .chat_history import Message


def _invoke_bedrock_json(system_prompt: str, user_message: str) -> dict:
    load_dotenv()

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

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )

    payload = json.loads(response["body"].read())
    text_parts = [
        part.get("text", "")
        for part in payload.get("content", [])
        if part.get("type") == "text"
    ]
    text = "".join(text_parts).strip()
    if not text:
        raise RuntimeError("Bedrock returned no text content.")

    return json.loads(text)


def _format_history(history: Optional[List[Message]]) -> str:
    if not history:
        return ""
    rendered = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        rendered.append(f"{role}: {content}")
    return "\n".join(rendered)


def extract_symptoms_with_llm(
    user_message: str, history: Optional[List[Message]] = None
) -> SymptomSummary:
    """
    Call the LLM and parse its JSON output into SymptomSummary.
    """
    system_prompt = (
        "You are a medical triage assistant. Extract structured fields as JSON with keys: "
        "main_complaint, symptoms (list), duration, severity (mild|moderate|severe), "
        "onset, age (number or null), red_flags (list), other_context, language "
        "(iso code such as 'en' or 'es'). Respond with JSON only."
    )

    history_text = _format_history(history)
    user_payload = (
        f"Conversation so far (most recent last):\n{history_text}\n\n"
        f"Latest user message:\n{user_message}\n\n"
        "Focus on the latest user message but use previous turns for context if needed."
        if history_text
        else user_message
    )

    data = _invoke_bedrock_json(system_prompt, user_payload)

    age = data.get("age")
    try:
        age = int(age) if age is not None else None
    except (TypeError, ValueError):
        age = None

    return SymptomSummary(
        main_complaint=data.get("main_complaint"),
        symptoms=data.get("symptoms") or [],
        duration=data.get("duration"),
        severity=data.get("severity"),
        onset=data.get("onset"),
        age=age,
        red_flags=data.get("red_flags") or [],
        other_context=data.get("other_context"),
        language=data.get("language") or "en",
    )
