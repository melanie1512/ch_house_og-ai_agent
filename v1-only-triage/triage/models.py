# triage/models.py
from enum import Enum
from pydantic import BaseModel
from typing import List, Optional

class RiskLevel(str, Enum):
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    ROUTINE = "ROUTINE"
    SELF_CARE = "SELF_CARE"


class SymptomSummary(BaseModel):
    main_complaint: Optional[str] = None
    symptoms: List[str] = []
    duration: Optional[str] = None
    severity: Optional[str] = None
    onset: Optional[str] = None
    age: Optional[int] = None
    red_flags: List[str] = []
    other_context: Optional[str] = None
    language: str = "es"  # we'll let the LLM detect this


class RiskAssessment(BaseModel):
    risk_level: RiskLevel
    recommended_action: str
    reasons: List[str]


class TriageRequest(BaseModel):
    user_id: str
    message: str


class TriageResponse(BaseModel):
    risk: RiskAssessment
    reply: str
