# triage/response_builder.py
import json
import os

import boto3
from dotenv import load_dotenv

from .models import SymptomSummary, RiskAssessment, RiskLevel

DISCLAIMER_EN = (
    "I’m an AI system and not a medical professional. "
    "This information is general and cannot replace an in-person evaluation."
)

DISCLAIMER_ES = (
    "Soy un sistema de IA y no un profesional de la salud. "
    "Esta información es general y no reemplaza una evaluación presencial."
)


def _pick_disclaimer(lang: str) -> str:
    return DISCLAIMER_ES


def build_triage_reply(
    summary: SymptomSummary, risk: RiskAssessment, history: list = None
) -> str:

    load_dotenv()

    lang = "es"
    disclaimer = _pick_disclaimer(lang)

    # For now: basic English-only templates.
    # Later: you can send this to an LLM and say:
    # "Rewrite this message in the user's language, keep all safety content."
    if risk.risk_level == RiskLevel.EMERGENCY:
        body = (
            "Based on what you described, this *could* be a serious situation. "
            "Because of the symptoms you mentioned, it would be safest to contact "
            "your local emergency number or go to the nearest emergency department immediately. "
            "If you are alone, try to contact someone you trust who can help you get there. "
        )
    elif risk.risk_level == RiskLevel.URGENT:
        body = (
            "What you described sounds important to be checked by a doctor soon. "
            "If possible, try to get an in-person or telehealth consultation within the next 24 hours. "
            "If your symptoms get worse—for example, if the pain becomes much stronger, you "
            "have trouble breathing, or you feel very unwell—go to an emergency service."
        )
    elif risk.risk_level == RiskLevel.ROUTINE:
        body = (
            "For now, this seems like something that can probably be evaluated in a regular "
            "doctor’s appointment rather than an emergency. "
            "Consider scheduling a visit in the coming days and keep track of how your symptoms evolve."
        )
    else:  # SELF_CARE
        body = (
            "At this moment, your description does not clearly indicate an emergency. "
            "You might try simple home measures for now—rest, hydration, and avoiding things that "
            "worsen your symptoms—while you monitor how you feel. "
            "If your symptoms worsen, last longer than you expect, or new symptoms appear, "
            "contact a healthcare professional."
        )

    reasons_str = ""
    if risk.reasons:
        reasons_str = " I’m particularly cautious because of: " + "; ".join(risk.reasons) + "."

    final = f"{body}{reasons_str} {disclaimer}"

    region = os.getenv("BEDROCK_REGION", "us-east-1")
    model = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN") or os.getenv(
        "BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    system_prompt = f"""
        You are a medical triage assistant. Rewrite the following text as safe, empathetic guidance for the user about their symptoms. 
        Adhere to the following STRICT rules:

        1) Safety & Boundaries  
        - Do NOT diagnose or name any specific condition, disease, or cause.  
        - Do NOT confirm or deny whether the situation is medically serious; instead, use cautious language.  
        - Do NOT prescribe or recommend medications, dosages, or treatment plans.  
        - Do NOT provide instructions that require medical training or professional judgment.

        2) What you ARE allowed to do  
        - Provide general advice (e.g., rest, hydration, monitoring symptoms).  
        - Advise seeking medical care (routine, urgent, or emergency) based on the seriousness of the described symptoms.  
        - Highlight warning signs that should prompt urgent evaluation.  
        - Keep the tone supportive, clear, and non-judgmental.

        3) Style  
        - Be concise and easy to understand.  
        - Use conditional language: “you might consider…”, “it could be helpful to…”, “if X happens, you should seek medical care…”.  
        - Do not alarm the user unnecessarily, but do encourage appropriate action.

        Write the final answer in this language: {lang}.
        """

    client = boto3.client("bedrock-runtime", region_name=region)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "temperature": 0,
        "system": [{"type": "text", "text": system_prompt}],
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": final}]}
        ],
    }
    response = client.invoke_model(
        modelId=model,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )

    payload = json.loads(response["body"].read())
    print(payload)
    text_parts = [
        part.get("text", "")
        for part in payload.get("content", [])
        if part.get("type") == "text"
    ]
    text = "".join(text_parts).strip()

    return text
