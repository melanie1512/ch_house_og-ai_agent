"""
RAG (Retrieval-Augmented Generation) helper module.

This module provides functionality to retrieve relevant context from a knowledge base
using the rimac-rag-worker-prod Lambda function.
"""

import os
from typing import Dict, Any, List, Optional

from lambda_client import invoke_lambda_sync, LambdaInvocationError
from logging_config import get_logger, log_error

logger = get_logger(__name__)


def retrieve_context(
    query: str,
    user_id: Optional[str] = None,
    max_results: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Retrieve relevant context from the knowledge base using the RAG worker Lambda.
    
    Args:
        query: The search query or user message
        user_id: Optional user ID for personalization
        max_results: Maximum number of results to return (default: 5)
        filters: Optional filters to apply to the search
    
    Returns:
        Dict containing:
        - 'documents': List of relevant documents/chunks
        - 'metadata': Additional metadata about the search
    
    Raises:
        LambdaInvocationError: If the Lambda invocation fails
    
    Example:
        >>> context = retrieve_context("síntomas de diabetes", max_results=3)
        >>> for doc in context['documents']:
        ...     print(doc['content'])
    """
    lambda_arn = os.getenv('RAG_WORKER_LAMBDA_ARN')
    
    if not lambda_arn:
        logger.warning("RAG_WORKER_LAMBDA_ARN not configured, skipping context retrieval")
        return {'documents': [], 'metadata': {}}
    
    # Build the payload for the Lambda function
    payload = {
        'query': query,
        'max_results': max_results
    }
    
    if user_id:
        payload['user_id'] = user_id
    
    if filters:
        payload['filters'] = filters
    
    logger.info(f"Retrieving context for query: {query[:50]}...")
    
    try:
        # Invoke the Lambda function synchronously
        response = invoke_lambda_sync(
            function_arn=lambda_arn,
            payload=payload
        )
        
        # Extract the payload from the response
        result = response.get('payload', {})
        
        # Log success
        num_docs = len(result.get('documents', []))
        logger.info(f"Retrieved {num_docs} documents from RAG worker")
        
        return result
        
    except LambdaInvocationError as e:
        log_error(
            logger,
            e,
            "Failed to retrieve context from RAG worker",
            extra={'query': query[:100]}
        )
        # Return empty result on error to allow graceful degradation
        return {'documents': [], 'metadata': {'error': str(e)}}


def format_context_for_prompt(documents: List[Dict[str, Any]]) -> str:
    """
    Format retrieved documents into a string suitable for inclusion in an LLM prompt.
    
    Args:
        documents: List of document dictionaries from retrieve_context()
    
    Returns:
        Formatted string with document contents
    
    Example:
        >>> docs = retrieve_context("diabetes")['documents']
        >>> context_str = format_context_for_prompt(docs)
        >>> prompt = f"Context: {context_str}\\n\\nQuestion: {user_query}"
    """
    if not documents:
        return ""
    
    formatted_parts = []
    for i, doc in enumerate(documents, 1):
        content = doc.get('content', '')
        source = doc.get('source', 'Unknown')
        
        formatted_parts.append(
            f"[Documento {i} - Fuente: {source}]\n{content}"
        )
    
    return "\n\n".join(formatted_parts)
