"""
Session Manager Module

Manages user session data for cross-agent context sharing.
This is a stub implementation to prevent import errors.
Full implementation should be added in a future task.
"""

from typing import Dict, Any, Optional
from logging_config import get_logger

logger = get_logger(__name__)


class SessionManager:
    """
    Manages user sessions and cross-agent context.
    
    This is a minimal stub implementation.
    """
    
    def __init__(self):
        """Initialize session manager."""
        self._sessions = {}
        logger.info("SessionManager initialized (stub implementation)")
    
    def save_triage_result(self, user_id: str, triage_data: Dict[str, Any]) -> None:
        """
        Save triage result to session.
        
        Args:
            user_id: User identifier
            triage_data: Triage result data
        """
        logger.debug(f"Saving triage result for user {user_id}")
        if user_id not in self._sessions:
            self._sessions[user_id] = {}
        self._sessions[user_id]['triage_context'] = triage_data
    
    def get_triage_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get triage context for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Triage context data or None
        """
        logger.debug(f"Getting triage context for user {user_id}")
        return self._sessions.get(user_id, {}).get('triage_context')
    
    def add_conversation_turn(
        self,
        user_id: str,
        message: str,
        response: Dict[str, Any],
        endpoint: str
    ) -> None:
        """
        Add a conversation turn to session history.
        
        Args:
            user_id: User identifier
            message: User message
            response: Agent response
            endpoint: Endpoint that handled the request
        """
        logger.debug(f"Adding conversation turn for user {user_id} at endpoint {endpoint}")
        if user_id not in self._sessions:
            self._sessions[user_id] = {'conversation_history': []}
        
        if 'conversation_history' not in self._sessions[user_id]:
            self._sessions[user_id]['conversation_history'] = []
        
        self._sessions[user_id]['conversation_history'].append({
            'message': message,
            'response': response,
            'endpoint': endpoint
        })
    
    def get_conversation_summary(self, user_id: str) -> str:
        """
        Get conversation history summary for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Formatted conversation summary
        """
        logger.debug(f"Getting conversation summary for user {user_id}")
        history = self._sessions.get(user_id, {}).get('conversation_history', [])
        
        if not history:
            return ""
        
        summary_lines = []
        for i, turn in enumerate(history[-5:], 1):  # Last 5 turns
            summary_lines.append(f"Turno {i}:")
            summary_lines.append(f"  Usuario dijo: {turn['message']}")
            
            # Extract key information from response based on endpoint
            response = turn.get('response', {})
            endpoint = turn.get('endpoint', '')
            
            if 'doctors/interpret' in endpoint:
                criterios = response.get('criterios', {})
                if criterios:
                    if criterios.get('especialidad'):
                        summary_lines.append(f"  Especialidad mencionada: {criterios['especialidad']}")
                    if criterios.get('modalidad'):
                        summary_lines.append(f"  Modalidad: {criterios['modalidad']}")
                    if criterios.get('fecha'):
                        summary_lines.append(f"  Fecha solicitada: {criterios['fecha']}")
                    if criterios.get('distrito'):
                        summary_lines.append(f"  Distrito: {criterios['distrito']}")
                    if criterios.get('genero_preferido'):
                        summary_lines.append(f"  Género preferido: {criterios['genero_preferido']}")
                
                pregunta = response.get('pregunta_pendiente')
                if pregunta:
                    summary_lines.append(f"  Sistema preguntó: {pregunta}")
            
            elif 'triage/interpret' in endpoint:
                capa = response.get('capa')
                if capa:
                    summary_lines.append(f"  Capa de atención clasificada: {capa}")
                
                especialidad = response.get('especialidad_sugerida')
                if especialidad:
                    summary_lines.append(f"  Especialidad sugerida: {especialidad}")
                
                razones = response.get('razones', [])
                if razones:
                    summary_lines.append(f"  Síntomas/razones identificados: {', '.join(razones)}")
                
                accion = response.get('accion_recomendada')
                if accion:
                    summary_lines.append(f"  Acción recomendada: {accion}")
            
            summary_lines.append("")  # Blank line between turns
        
        return "\n".join(summary_lines)
    
    def update_session(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        Update session data for user.
        
        Args:
            user_id: User identifier
            data: Data to update
        """
        logger.debug(f"Updating session for user {user_id}")
        if user_id not in self._sessions:
            self._sessions[user_id] = {}
        self._sessions[user_id].update(data)


# Global session manager instance
_session_manager = None


def get_session_manager() -> SessionManager:
    """
    Get the global session manager instance.
    
    Returns:
        SessionManager instance
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
