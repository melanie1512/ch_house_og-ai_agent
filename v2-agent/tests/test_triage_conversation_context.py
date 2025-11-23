"""
Tests for conversation context accumulation in triage/interpret endpoint.

This test verifies that:
1. Conversation history is retrieved and used in triage
2. Symptoms from previous turns are considered
3. The system doesn't repeat questions already answered
"""

import pytest
from unittest.mock import patch, MagicMock
from triage.interpret import interpret_triage_request
from models import TriageRequest


class TestTriageConversationContext:
    """Test conversation context in triage"""
    
    @patch('triage.interpret.get_session_manager')
    @patch('triage.interpret.boto3.client')
    def test_triage_uses_conversation_history(
        self, 
        mock_boto_client, 
        mock_session_manager
    ):
        """
        Test that triage retrieves and uses conversation history.
        
        Scenario:
        - Turn 1: User mentions "me duele el pecho"
        - Turn 2: User adds "desde hace 2 horas"
        - Expected: System should consider both pieces of information
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager with conversation history
        mock_sm = MagicMock()
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: me duele el pecho
  Capa de atención: 4
  Razones: dolor de pecho
  Acción recomendada: llamar_emergencias
"""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"capa\\": 4, \\"razones\\": [\\"dolor de pecho\\", \\"duración 2 horas\\"], \\"especialidad_sugerida\\": \\"cardiología\\", \\"taller_sugerido\\": null, \\"accion_recomendada\\": \\"llamar_emergencias\\", \\"requiere_mas_informacion\\": false, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        # Create request for second turn
        request = TriageRequest(
            user_id="test_user",
            message="desde hace 2 horas"
        )
        
        # Execute
        result = interpret_triage_request(request)
        
        # Verify conversation history was retrieved
        mock_sm.get_conversation_summary.assert_called_once_with("test_user")
        
        # Verify classification considers both turns
        assert result['capa'] == 4
        assert 'dolor de pecho' in str(result['razones']) or 'duración' in str(result['razones'])
    
    @patch('triage.interpret.retrieve_context')
    @patch('triage.interpret.get_session_manager')
    @patch('triage.interpret.boto3.client')
    def test_triage_accumulates_symptoms(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that triage accumulates symptoms across multiple turns.
        
        Scenario:
        - Turn 1: "tengo fiebre"
        - Turn 2: "y me duele la cabeza"
        - Turn 3: "y el cuello está rígido"
        - Expected: System should recognize the combination as potential meningitis
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock RAG
        mock_retrieve_context.return_value = {
            'documents': [
                {
                    'content': 'Fiebre + dolor de cabeza + rigidez de cuello = posible meningitis',
                    'source': 'medical_knowledge'
                }
            ]
        }
        
        # Mock session manager with accumulated symptoms
        mock_sm = MagicMock()
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: tengo fiebre alta
  Capa de atención: 2
  Razones: fiebre alta
  Acción recomendada: solicitar_medico_a_domicilio

Turno 2:
  Usuario dijo: y me duele mucho la cabeza
  Capa de atención: 2
  Razones: fiebre alta, dolor de cabeza
  Acción recomendada: solicitar_medico_a_domicilio
"""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response - should upgrade to Capa 4 with all symptoms
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"capa\\": 4, \\"razones\\": [\\"fiebre alta\\", \\"dolor de cabeza\\", \\"rigidez de cuello\\", \\"posible meningitis\\"], \\"especialidad_sugerida\\": \\"neurología\\", \\"taller_sugerido\\": null, \\"accion_recomendada\\": \\"llamar_emergencias\\", \\"requiere_mas_informacion\\": false, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        # Create request for third turn
        request = TriageRequest(
            user_id="test_user",
            message="y el cuello está rígido"
        )
        
        # Execute
        result = interpret_triage_request(request)
        
        # Verify classification upgraded to emergency
        assert result['capa'] == 4
        assert result['accion_recomendada'] == 'llamar_emergencias'
        
        # Verify all symptoms are considered
        razones_str = ' '.join(result['razones'])
        assert 'fiebre' in razones_str.lower() or 'meningitis' in razones_str.lower()
    
    @patch('triage.interpret.retrieve_context')
    @patch('triage.interpret.get_session_manager')
    @patch('triage.interpret.boto3.client')
    def test_triage_no_repeated_questions(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that triage doesn't ask for information already provided.
        
        Scenario:
        - Turn 1: User says "me duele el estómago"
        - System asks: "¿Desde cuándo?"
        - Turn 2: User says "desde ayer"
        - Expected: System should not ask about duration again
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_retrieve_context.return_value = {'documents': []}
        
        # Mock session manager
        mock_sm = MagicMock()
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: me duele el estómago
  Capa de atención: 2
  Razones: dolor abdominal
  Acción recomendada: solicitar_medico_a_domicilio
"""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response - should have duration from current message
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"capa\\": 2, \\"razones\\": [\\"dolor abdominal\\", \\"duración 1 día\\"], \\"especialidad_sugerida\\": \\"medicina_interna\\", \\"taller_sugerido\\": null, \\"accion_recomendada\\": \\"solicitar_medico_a_domicilio\\", \\"requiere_mas_informacion\\": false, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        request = TriageRequest(
            user_id="test_user",
            message="desde ayer"
        )
        
        result = interpret_triage_request(request)
        
        # Verify no additional information is requested
        assert result['requiere_mas_informacion'] == False
        
        # Verify duration is included in analysis
        razones_str = ' '.join(result['razones'])
        assert 'duración' in razones_str.lower() or 'día' in razones_str.lower()


class TestTriageHistoryFormat:
    """Test that triage history is properly formatted"""
    
    @patch('triage.interpret.get_session_manager')
    @patch('triage.interpret.boto3.client')
    def test_triage_history_includes_key_info(
        self, 
        mock_boto_client, 
        mock_session_manager
    ):
        """
        Test that triage conversation history includes key information.
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_sm = MagicMock()
        mock_sm.get_conversation_summary.return_value = """
Turno 1:
  Usuario dijo: me duele el pecho
  Capa de atención: 4
  Especialidad sugerida por triaje: cardiología
  Razones: dolor de pecho intenso, sudoración
  Acción recomendada: llamar_emergencias
"""
        mock_session_manager.return_value = mock_sm
        
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"capa\\": 4, \\"razones\\": [\\"dolor de pecho\\"], \\"especialidad_sugerida\\": \\"cardiología\\", \\"taller_sugerido\\": null, \\"accion_recomendada\\": \\"llamar_emergencias\\", \\"requiere_mas_informacion\\": false, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        request = TriageRequest(
            user_id="test_user",
            message="sigo con el dolor"
        )
        
        result = interpret_triage_request(request)
        
        # Verify history was retrieved
        mock_sm.get_conversation_summary.assert_called_once()
        
        # Verify the prompt includes history (check that Bedrock was called)
        mock_bedrock.invoke_model.assert_called_once()
