"""
Tests for conversation context accumulation in doctors/interpret endpoint.

This test verifies that:
1. Criteria from conversation history are preserved
2. New criteria are added to existing ones
3. The system doesn't forget previously mentioned information
"""

import pytest
from unittest.mock import patch, MagicMock
from doctors.interpret import interpret_appointment_request
from models import TriageRequest


class TestConversationContextAccumulation:
    """Test conversation context accumulation"""
    
    @patch('doctors.interpret.ejecutar_consultas_simple')
    @patch('doctors.interpret.get_session_manager')
    @patch('doctors.interpret.boto3.client')
    def test_criteria_accumulation_across_turns(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_ejecutar_consultas
    ):
        """
        Test that criteria accumulate across conversation turns.
        
        Scenario:
        - Turn 1: User says "quiero cita con cardiólogo"
        - Turn 2: User says "para mañana"
        - Expected: Both especialidad AND fecha should be in criteria
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager with conversation history
        mock_sm = MagicMock()
        mock_sm.get_triage_context.return_value = None
        
        # Simulate conversation history where user mentioned "cardiólogo"
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: quiero cita con cardiólogo
  Especialidad mencionada: Cardiología
  Sistema preguntó: ¿Para qué día deseas tu cita?
"""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response that should include BOTH especialidad (from history) and fecha (from current message)
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"accion\\": \\"buscar\\", \\"criterios\\": {\\"especialidad\\": \\"Cardiología\\", \\"fecha\\": \\"2025-11-24\\"}, \\"consulta_doctores\\": {\\"TableName\\": \\"doctores\\", \\"IndexName\\": \\"especialidad-index\\", \\"KeyConditionExpression\\": \\"especialidad = :esp\\", \\"ExpressionAttributeValues\\": {\\\":esp\\": \\"Cardiología\\"}}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": false, \\"pregunta_pendiente\\": null, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        # Mock DynamoDB query results
        mock_ejecutar_consultas.return_value = {
            'doctores': [{'doctor_id': 'DOC-001', 'nombre': 'Dr. Test'}],
            'horarios': []
        }
        
        # Create request for second turn (user says "para mañana")
        request = TriageRequest(
            user_id="test_user",
            message="para mañana"
        )
        
        # Execute
        result = interpret_appointment_request(request)
        
        # Verify that BOTH criteria are present
        assert result['criterios']['especialidad'] == 'Cardiología', \
            "Especialidad from history should be preserved"
        assert result['criterios']['fecha'] is not None, \
            "Fecha from current message should be added"
        
        # Verify query was generated with especialidad
        assert result['consulta_doctores'].get('IndexName') == 'especialidad-index'
        
        # Verify no additional questions are asked
        assert result['requiere_mas_informacion'] == False, \
            "Should not ask for more info when criteria are sufficient"
    
    @patch('doctors.interpret.ejecutar_consultas_simple')
    @patch('doctors.interpret.get_session_manager')
    @patch('doctors.interpret.boto3.client')
    def test_multiple_criteria_accumulation(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_ejecutar_consultas
    ):
        """
        Test accumulation of multiple criteria across multiple turns.
        
        Scenario:
        - Turn 1: "cardiólogo" → especialidad
        - Turn 2: "mañana" → fecha
        - Turn 3: "en Lima" → departamento
        - Expected: All three criteria should be present
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager with rich conversation history
        mock_sm = MagicMock()
        mock_sm.get_triage_context.return_value = None
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: quiero cita con cardiólogo
  Especialidad mencionada: Cardiología
  Sistema preguntó: ¿Para qué día deseas tu cita?

Turno 2:
  Usuario dijo: para mañana
  Especialidad mencionada: Cardiología
  Fecha solicitada: 2025-11-24
  Sistema preguntó: ¿En qué distrito te gustaría la consulta?
"""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response with all three criteria
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"accion\\": \\"buscar\\", \\"criterios\\": {\\"especialidad\\": \\"Cardiología\\", \\"fecha\\": \\"2025-11-24\\", \\"departamento\\": \\"Lima\\"}, \\"consulta_doctores\\": {\\"TableName\\": \\"doctores\\", \\"IndexName\\": \\"especialidad-index\\"}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": false, \\"pregunta_pendiente\\": null, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        mock_ejecutar_consultas.return_value = {'doctores': [], 'horarios': []}
        
        # Create request for third turn
        request = TriageRequest(
            user_id="test_user",
            message="en Lima"
        )
        
        # Execute
        result = interpret_appointment_request(request)
        
        # Verify all three criteria are present
        assert result['criterios']['especialidad'] == 'Cardiología'
        assert result['criterios']['fecha'] == '2025-11-24'
        assert result['criterios']['departamento'] == 'Lima'
    
    @patch('doctors.interpret.get_session_manager')
    @patch('doctors.interpret.boto3.client')
    def test_no_repeated_questions(
        self, 
        mock_boto_client, 
        mock_session_manager
    ):
        """
        Test that the system doesn't ask for information already provided.
        
        Scenario:
        - History shows user already said "cardiólogo"
        - User now says "para mañana"
        - System should NOT ask "¿con qué especialidad?" again
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager
        mock_sm = MagicMock()
        mock_sm.get_triage_context.return_value = None
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: quiero cita con cardiólogo
  Especialidad mencionada: Cardiología
"""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response - should have especialidad from history
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"accion\\": \\"buscar\\", \\"criterios\\": {\\"especialidad\\": \\"Cardiología\\", \\"fecha\\": \\"2025-11-24\\"}, \\"consulta_doctores\\": {\\"TableName\\": \\"doctores\\"}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": false, \\"pregunta_pendiente\\": null, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        # Create request
        request = TriageRequest(
            user_id="test_user",
            message="para mañana"
        )
        
        # Execute
        result = interpret_appointment_request(request)
        
        # Verify no question about especialidad
        pregunta = result.get('pregunta_pendiente', '')
        assert 'especialidad' not in pregunta.lower(), \
            "Should not ask about especialidad when it's already in history"
        
        # Verify especialidad is in criteria
        assert result['criterios']['especialidad'] == 'Cardiología'


class TestConversationContextEdgeCases:
    """Test edge cases in conversation context"""
    
    @patch('doctors.interpret.get_session_manager')
    @patch('doctors.interpret.boto3.client')
    def test_user_changes_mind(
        self, 
        mock_boto_client, 
        mock_session_manager
    ):
        """
        Test that user can change their mind and override previous criteria.
        
        Scenario:
        - History: "cardiólogo"
        - User now: "mejor con un neurólogo"
        - Expected: especialidad should be updated to Neurología
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_sm = MagicMock()
        mock_sm.get_triage_context.return_value = None
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: quiero cita con cardiólogo
  Especialidad mencionada: Cardiología
"""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response - should update to Neurología
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"accion\\": \\"buscar\\", \\"criterios\\": {\\"especialidad\\": \\"Neurología\\"}, \\"consulta_doctores\\": {\\"TableName\\": \\"doctores\\"}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": false, \\"pregunta_pendiente\\": null, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        request = TriageRequest(
            user_id="test_user",
            message="mejor con un neurólogo"
        )
        
        result = interpret_appointment_request(request)
        
        # Verify especialidad was updated
        assert result['criterios']['especialidad'] == 'Neurología', \
            "User should be able to change their mind and override previous criteria"
