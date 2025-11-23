"""
Tests for RAG integration in the triage/interpret endpoint.

This test verifies that:
1. RAG is called on every triage request
2. RAG context is included in the response
3. RAG context is used for generating natural language responses
"""

import pytest
from unittest.mock import patch, MagicMock
from triage.interpret import interpret_triage_request
from models import TriageRequest


class TestTriageRAGIntegration:
    """Test RAG integration in triage endpoint"""
    
    @patch('triage.interpret.retrieve_context')
    @patch('triage.interpret.get_session_manager')
    @patch('triage.interpret.boto3.client')
    def test_rag_always_called_in_triage(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that RAG is called on every triage request.
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock session manager
        mock_sm = MagicMock()
        mock_session_manager.return_value = mock_sm
        
        # Mock RAG response
        mock_retrieve_context.return_value = {
            'documents': [
                {
                    'content': 'El dolor de pecho puede indicar problemas cardíacos',
                    'source': 'knowledge_base'
                }
            ],
            'metadata': {}
        }
        
        # Mock Bedrock response
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"capa\\": 4, \\"razones\\": [\\"dolor de pecho\\"], \\"especialidad_sugerida\\": \\"cardiología\\", \\"taller_sugerido\\": null, \\"accion_recomendada\\": \\"llamar_emergencias\\", \\"requiere_mas_informacion\\": false, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        # Create request
        request = TriageRequest(
            user_id="test_user",
            message="Me duele el pecho"
        )
        
        # Execute
        result = interpret_triage_request(request)
        
        # Verify RAG was called
        mock_retrieve_context.assert_called_once_with(
            query="Me duele el pecho",
            user_id="test_user",
            max_results=3
        )
        
        # Verify response includes RAG documents
        assert 'rag_documents' in result
        assert len(result['rag_documents']) > 0
    
    @patch('triage.interpret.retrieve_context')
    @patch('triage.interpret.get_session_manager')
    @patch('triage.interpret.boto3.client')
    def test_rag_context_enriches_triage_classification(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that RAG context is available to help classify symptoms.
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_sm = MagicMock()
        mock_session_manager.return_value = mock_sm
        
        # Mock RAG with medical context
        mock_retrieve_context.return_value = {
            'documents': [
                {
                    'content': 'La fiebre alta con rigidez de cuello puede indicar meningitis, una emergencia médica',
                    'source': 'medical_knowledge'
                },
                {
                    'content': 'Los signos de alarma incluyen fiebre >39°C con rigidez de cuello',
                    'source': 'triage_guidelines'
                }
            ],
            'metadata': {}
        }
        
        # Mock Bedrock response - should classify as Capa 4 with RAG context
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"capa\\": 4, \\"razones\\": [\\"fiebre alta\\", \\"rigidez de cuello\\", \\"posible meningitis\\"], \\"especialidad_sugerida\\": \\"neurología\\", \\"taller_sugerido\\": null, \\"accion_recomendada\\": \\"llamar_emergencias\\", \\"requiere_mas_informacion\\": false, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        request = TriageRequest(
            user_id="test_user",
            message="Tengo fiebre muy alta y me duele el cuello al moverlo"
        )
        
        result = interpret_triage_request(request)
        
        # Verify classification is Capa 4 (emergency)
        assert result['capa'] == 4
        assert result['accion_recomendada'] == 'llamar_emergencias'
        
        # Verify RAG documents are included
        assert len(result['rag_documents']) == 2
    
    @patch('triage.interpret.retrieve_context')
    @patch('triage.interpret.get_session_manager')
    @patch('triage.interpret.boto3.client')
    def test_triage_works_without_rag_on_failure(
        self, 
        mock_boto_client, 
        mock_session_manager,
        mock_retrieve_context
    ):
        """
        Test that triage continues to work even if RAG fails.
        """
        # Setup mocks
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_sm = MagicMock()
        mock_session_manager.return_value = mock_sm
        
        # Mock RAG to fail
        mock_retrieve_context.side_effect = Exception("RAG service unavailable")
        
        # Mock Bedrock response
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "{\\"capa\\": 1, \\"razones\\": [\\"síntomas leves\\"], \\"especialidad_sugerida\\": null, \\"taller_sugerido\\": null, \\"accion_recomendada\\": \\"contactar_medico_virtual\\", \\"requiere_mas_informacion\\": false, \\"derivar_a\\": null, \\"advertencia\\": \\"test\\"}"
                }]
            }''')
        }
        
        request = TriageRequest(
            user_id="test_user",
            message="Tengo un resfriado leve"
        )
        
        # Should not raise exception
        result = interpret_triage_request(request)
        
        # Verify triage still works
        assert result['capa'] == 1
        assert result['accion_recomendada'] == 'contactar_medico_virtual'
        
        # Verify rag_documents is empty list (not None)
        assert result['rag_documents'] == []


class TestTriageRAGInNaturalLanguageResponse:
    """Test that RAG context is used in natural language responses"""
    
    @patch('main.boto3.client')
    def test_rag_context_in_triage_response(self, mock_boto_client):
        """
        Test that RAG context is included in the natural language response prompt.
        """
        from main import generate_natural_language_response
        
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: '''{
                "content": [{
                    "text": "Entiendo que tienes dolor de pecho. Este síntoma puede indicar problemas cardíacos que requieren atención inmediata. Te recomiendo llamar a emergencias de inmediato."
                }]
            }''')
        }
        
        # Response data with RAG documents
        response_data = {
            'capa': 4,
            'razones': ['dolor de pecho intenso'],
            'especialidad_sugerida': 'cardiología',
            'accion_recomendada': 'llamar_emergencias',
            'derivar_a': None,
            'rag_documents': [
                {
                    'content': 'El dolor de pecho puede indicar infarto, angina u otros problemas cardíacos graves',
                    'source': 'medical_knowledge'
                }
            ]
        }
        
        # Generate natural language response
        result = generate_natural_language_response(
            endpoint="triage/interpret",
            response_data=response_data,
            user_message="Me duele el pecho"
        )
        
        # Verify Bedrock was called
        mock_bedrock.invoke_model.assert_called_once()
        
        # Verify the prompt includes RAG context
        call_args = mock_bedrock.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        prompt = body['messages'][0]['content'][0]['text']
        
        # The prompt should mention the RAG context
        assert 'Contexto médico adicional' in prompt or 'base de conocimiento' in prompt
