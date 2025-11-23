# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from triage.models import TriageRequest, TriageResponse
from triage.symptom_extraction import extract_symptoms_with_llm
from triage.risk_engine import assess_risk
from triage.response_builder import build_triage_reply
from triage.chat_history import get_history, append_message
import json

app = FastAPI(title="Triage Assistant API", version="0.1.0")

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
