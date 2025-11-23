# triage/risk_engine.py
import json
import os

import boto3
from dotenv import load_dotenv

from .models import SymptomSummary, RiskAssessment, RiskLevel


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


def assess_risk(summary: SymptomSummary) -> RiskAssessment:
    """
    Call an LLM via Bedrock to classify triage risk based on the extracted summary.
    """
    system_prompt = (
        "Eres un asistente de triaje médico. Evalúa el nivel de riesgo y la acción recomendada "
        "para los síntomas del usuario. Devuelve solo JSON con claves: "
        "risk_level (EMERGENCY|URGENT|ROUTINE|SELF_CARE), "
        "recommended_action (call_emergency|doctor_within_24h|doctor_when_possible|home_care_with_monitoring), "
        "reasons (lista de textos cortos en español). Usa lenguaje prudente, NO diagnostiques y NO recetes medicamentos."
    )

    user_payload = summary.model_dump_json()
    data = _invoke_bedrock_json(system_prompt, user_payload)

    risk_level_val = data.get("risk_level", RiskLevel.SELF_CARE)
    try:
        risk_level = RiskLevel(risk_level_val)
    except ValueError:
        risk_level = RiskLevel.SELF_CARE

    recommended_action = data.get("recommended_action") or "home_care_with_monitoring"
    reasons = data.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = [str(reasons)]

    return RiskAssessment(
        risk_level=risk_level,
        recommended_action=recommended_action,
        reasons=reasons,
    )
