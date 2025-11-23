"""
Tests for RAG integration in the doctors/interpret endpoint.

This test verifies that:
1. RAG is NOT called when sufficient information is provided
2. RAG IS called when more information is needed
3. RAG context is used only for formulating questions
"""

import pytest
from unittest.mock import patch, MagicMock
from doctors.interpret import interpret_appointment_request
from models import TriageRequest


class TestRAGIntegration:
    """Test RAG integration behavior"""
    
    @patch('doctors.interpret.retrieve_context')
    @patch('doctors.interpret.get_session_manager')
    @patch('doctors.interpret.boto3.client')
    def test_rag_not_called_with_sufficient_info(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that RAG is NOT called when user provides sufficient information
        for a DynamoDB query.
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager
        mock_sm = MagicMock()
        mock_sm.get_triage_context.return_value = None
        mock_sm.get_conversation_summary.return_value = ""
        mock_session_manager.return_value = mock_sm
        
        # Mock Bedrock response with sufficient info (no requiere_mas_informacion)
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '{"content": [{"text": "{\\"accion\\": \\"buscar\\", \\"criterios\\": {\\"especialidad\\": \\"Cardiología\\"}, \\"consulta_doctores\\": {\\"TableName\\": \\"doctores\\"}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": false, \\"pregunta_pendiente\\": null, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"}]}')
        }
        
        # Create request with sufficient information
        request = TriageRequest(
            user_id="test_user",
            message="Quiero una cita con un cardiólogo en Lima"
        )
        
        # Execute
        result = interpret_appointment_request(request)
        
        # Verify RAG was NOT called
        mock_retrieve_context.assert_not_called()
        
        # Verify response
        assert result['accion'] == 'buscar'
        assert result['requiere_mas_informacion'] == False
    
    @patch('doctors.interpret.retrieve_context')
    @patch('doctors.interpret.get_session_manager')
    @patch('doctors.interpret.boto3.client')
    def test_rag_called_when_info_needed(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that RAG IS called when user doesn't provide sufficient information
        and the system needs to ask questions.
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager
        mock_sm = MagicMock()
        mock_sm.get_triage_context.return_value = None
        mock_sm.get_conversation_summary.return_value = ""
        mock_session_manager.return_value = mock_sm
        
        # Mock RAG response
        mock_retrieve_context.return_value = {
            'documents': [
                {
                    'content': 'La cardiología trata problemas del corazón',
                    'source': 'knowledge_base'
                }
            ],
            'metadata': {}
        }
        
        # First call: insufficient info (requiere_mas_informacion = true)
        # Second call: with RAG context
        mock_bedrock.invoke_model.side_effect = [
            {
                'body': MagicMock(read=lambda: '{"content": [{"text": "{\\"accion\\": \\"necesita_mas_informacion\\", \\"criterios\\": {}, \\"consulta_doctores\\": {}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": true, \\"pregunta_pendiente\\": \\"¿Con qué especialidad médica deseas atenderte?\\", \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"}]}')
            },
            {
                'body': MagicMock(read=lambda: '{"content": [{"text": "{\\"accion\\": \\"necesita_mas_informacion\\", \\"criterios\\": {}, \\"consulta_doctores\\": {}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": true, \\"pregunta_pendiente\\": \\"Veo que mencionas dolor de pecho. ¿Deseas una cita con cardiología?\\", \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"}]}')
            }
        ]
        
        # Create request with insufficient information
        request = TriageRequest(
            user_id="test_user",
            message="Necesito una cita"
        )
        
        # Execute
        result = interpret_appointment_request(request)
        
        # Verify RAG WAS called
        mock_retrieve_context.assert_called_once()
        
        # Verify Bedrock was called twice (once without RAG, once with RAG)
        assert mock_bedrock.invoke_model.call_count == 2
        
        # Verify response
        assert result['requiere_mas_informacion'] == True
        assert result['pregunta_pendiente'] is not None
    
    @patch('doctors.interpret.retrieve_context')
    @patch('doctors.interpret.get_session_manager')
    @patch('doctors.interpret.boto3.client')
    def test_rag_graceful_degradation_on_error(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that the system continues to work even if RAG fails.
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager
        mock_sm = MagicMock()
        mock_sm.get_triage_context.return_value = None
        mock_sm.get_conversation_summary.return_value = ""
        mock_session_manager.return_value = mock_sm
        
        # Mock RAG to raise an exception
        mock_retrieve_context.side_effect = Exception("RAG service unavailable")
        
        # Mock Bedrock response (requiere_mas_informacion = true)
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '{"content": [{"text": "{\\"accion\\": \\"necesita_mas_informacion\\", \\"criterios\\": {}, \\"consulta_doctores\\": {}, \\"consulta_horarios\\": [], \\"requiere_mas_informacion\\": true, \\"pregunta_pendiente\\": \\"¿Con qué especialidad médica deseas atenderte?\\", \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"}]}')
        }
        
        # Create request
        request = TriageRequest(
            user_id="test_user",
            message="Necesito una cita"
        )
        
        # Execute - should not raise exception
        result = interpret_appointment_request(request)
        
        # Verify system still works
        assert result['requiere_mas_informacion'] == True
        assert result['pregunta_pendiente'] is not None
        
        # Verify only one Bedrock call (RAG failed, so no second call)
        assert mock_bedrock.invoke_model.call_count == 1
