# models.py (or triage/models.py)
from enum import Enum
from pydantic import BaseModel
from typing import List, Optional
import datetime


# ─────────────────────────────────────────
# TRIAGE
# ─────────────────────────────────────────

class TriageRequest(BaseModel):
    """
    Mensaje de usuario genérico que cualquier servicio puede recibir.
    Lo usas en los endpoints tipo /triage/interpret, /appointments/interpret, etc.
    """
    user_id: str
    message: str 

class SymptomSummary(BaseModel):
    main_complaint: Optional[str] = None
    symptoms: List[str] = []
    duration: Optional[str] = None
    severity: Optional[str] = None
    onset: Optional[str] = None
    age: Optional[int] = None
    red_flags: List[str] = []
    other_context: Optional[str] = None
    language: str = "es"  # el LLM detecta y normaliza


class RiskLevel(str, Enum):
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    ROUTINE = "ROUTINE"
    SELF_CARE = "SELF_CARE"


class RiskAssessment(BaseModel):
    risk_level: RiskLevel
    recommended_action: str  # p.ej. "call_emergency", "doctor_24h", etc.
    reasons: List[str]


class TriageRequest(BaseModel):
    user_id: str
    message: str


class TriageResponse(BaseModel):
    """
    Respuesta que devuelve tu servicio de triaje (/triage o /triage/interpret)
    al agente o al frontend.
    """
    risk: RiskAssessment
    reply: str  # mensaje en lenguaje natural, ya en español


# ─────────────────────────────────────────
# APPOINTMENTS
# ─────────────────────────────────────────

class AppointmentOperation(str, Enum):
    LIST = "LIST"
    CREATE = "CREATE"
    CANCEL = "CANCEL"


class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    ANY = "any"


class Modality(str, Enum):
    VIRTUAL = "virtual"
    IN_PERSON = "in_person"
    ANY = "any"


class AppointmentSearchFilters(BaseModel):
    """
    Estructura que el LLM puede rellenar al interpretar el mensaje
    del usuario para buscar doctores o citas.
    """
    specialty: Optional[str] = None          # "cardiología", "dermatología", etc.
    date: Optional[datetime.date] = None     # día concreto
    time_of_day: TimeOfDay = TimeOfDay.ANY
    modality: Modality = Modality.ANY
    location: Optional[str] = None           # ciudad / distrito / clínica


class DoctorAvailabilitySlot(BaseModel):
    start: datetime.time
    end: datetime.time
    modality: Modality


class DoctorSummary(BaseModel):
    doctor_id: str
    name: str
    specialty: str
    modalities: List[Modality] = []
    locations: List[str] = []
    availability: List[DoctorAvailabilitySlot] = []


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CANCELED = "canceled"
    COMPLETED = "completed"


class AppointmentSummary(BaseModel):
    appointment_id: str
    user_id: str
    doctor_id: str
    doctor_name: str
    specialty: str
    date: datetime.date
    time: datetime.time
    modality: Modality
    location: Optional[str] = None
    status: AppointmentStatus


class AppointmentIntent(BaseModel):
    """
    Estructura interna que tu servicio de citas puede usar después de
    parsear el mensaje con LLM.
    """
    operation: AppointmentOperation
    filters: Optional[AppointmentSearchFilters] = None
    appointment_id: Optional[str] = None  # para cancelar o ver algo específico


class AppointmentInterpretRequest(BaseModel):
    """
    Request específico para /appointments/interpret (extiende el genérico).
    """
    user_id: str
    message: str


class AppointmentInterpretResponse(BaseModel):
    """
    Respuesta que tu API de citas devolverá al agente.
    Según la operación, algunos campos se usan y otros no.
    """
    operation: AppointmentOperation
    appointments: List[AppointmentSummary] = []      # LIST
    created_appointment: Optional[AppointmentSummary] = None  # CREATE
    cancelled_appointment: Optional[AppointmentSummary] = None  # CANCEL
    message: str  # texto en español para el usuario

# ─────────────────────────────────────────
#   WORKSHOPS (TALLERES)
# ─────────────────────────────────────────

class WorkshopOperation(str, Enum):
    SEARCH = "SEARCH"               # Buscar talleres según tema/fecha
    LIST_MY_WORKSHOPS = "LIST_MY_WORKSHOPS"  # Ver talleres del usuario
    REGISTER = "REGISTER"           # Registrar al usuario en un taller


class WorkshopTopic(str, Enum):
    STRESS = "stress_management"
    SLEEP = "sleep_hygiene"
    NUTRITION = "nutrition"
    ANXIETY = "anxiety_management"
    GENERAL = "general_wellbeing"
    ANY = "any"


class WorkshopModality(str, Enum):
    VIRTUAL = "virtual"
    IN_PERSON = "in_person"
    ANY = "any"


class WorkshopFilters(BaseModel):
    """
    Estructura que el LLM completará al interpretar el mensaje:
    - "recomiéndame talleres de sueño"
    - "quiero talleres el sábado por la mañana"
    """
    topic: WorkshopTopic = WorkshopTopic.ANY
    date: Optional[datetime.date] = None
    time_of_day: Optional[str] = None   # "mañana", "tarde", "noche" (texto libre)
    modality: WorkshopModality = WorkshopModality.ANY
    location: Optional[str] = None


class WorkshopSummary(BaseModel):
    """
    Información básica de un taller: solo lo necesario para que un usuario
    pueda elegir o confirmar.
    """
    workshop_id: str
    title: str
    topic: WorkshopTopic
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    modality: WorkshopModality
    location: Optional[str] = None
    description: Optional[str] = None   # breve resumen del taller


class WorkshopIntent(BaseModel):
    """
    Intención interpretada por el LLM a partir del mensaje del usuario:
    - "busca talleres"
    - "muéstrame mis talleres"
    - "inscríbeme al taller del sábado"
    """
    operation: WorkshopOperation
    filters: Optional[WorkshopFilters] = None
    workshop_id: Optional[str] = None


class WorkshopInterpretRequest(BaseModel):
    """
    Request para el endpoint /workshops/interpret.
    Igual que Request, pero lo hacemos explícito
    por simetría con appointments & triage.
    """
    user_id: str
    message: str


class WorkshopInterpretResponse(BaseModel):
    """
    Respuesta enviada al agente. El agente recibirá esta estructura y
    luego generará un mensaje final en español para el usuario.
    """
    operation: WorkshopOperation
    workshops: List[WorkshopSummary] = []    # Para SEARCH o LIST
    registered_workshop: Optional[WorkshopSummary] = None  # Para REGISTER
    message: str  # mensaje en español que el agente puede usar o resumir
    rag_documents: List[dict] = []  # Documentos RAG para enriquecer respuesta


# ─────────────────────────────────────────
# SHARED
# ─────────────────────────────────────────

class Request(BaseModel):
    """
    Mensaje de usuario genérico que cualquier servicio puede recibir.
    Lo usas en los endpoints tipo /triage/interpret, /appointments/interpret, etc.
    """
    user_id: str
    message: str  # mensaje_usuario en tu diseño, aquí lo llamamos message

class UserState(BaseModel):
    user_id: str
    last_symptom_summary: Optional[SymptomSummary] = None
    last_risk_assessment: Optional[RiskAssessment] = None
    last_specialty_recommended: Optional[str] = None
    last_workshop_topic_recommended: Optional[str] = None