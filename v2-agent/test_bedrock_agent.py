"""
Script de prueba para Bedrock Agent
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"


def test_agent_chat(message: str, user_id: str = "test_user_123", session_id: str = None):
    """Prueba el endpoint del agente"""
    
    payload = {
        "user_id": user_id,
        "message": message
    }
    
    if session_id:
        payload["session_id"] = session_id
    
    print(f"\n{'='*70}")
    print(f"👤 Usuario: {message}")
    print(f"{'='*70}")
    
    response = requests.post(
        f"{BASE_URL}/agent/chat",
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"🤖 Agente: {data['response']}")
        print(f"\n📊 Metadata:")
        print(f"   - Session ID: {data['session_id']}")
        print(f"   - Type: {data['type']}")
        
        return data['session_id']
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None


def test_health():
    """Verifica el estado del servicio"""
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        data = response.json()
        print("\n🏥 Health Check:")
        print(f"   Status: {data['status']}")
        print(f"   Bedrock Agent Configured: {data['bedrock_agent_configured']}")
        if data.get('agent_id'):
            print(f"   Agent ID: {data['agent_id']}")
        return data['bedrock_agent_configured']
    return False


if __name__ == "__main__":
    print("🚀 Probando Bedrock Agent...")
    
    # Verificar configuración
    if not test_health():
        print("\n⚠️  Bedrock Agent no está configurado.")
        print("   Configura BEDROCK_AGENT_ID en tu .env")
        print("   Ver bedrock_agent_setup.md para instrucciones")
        exit(1)
    
    time.sleep(1)
    
    # Test 1: Síntomas (debe usar TriageActionGroup)
    print("\n\n🧪 Test 1: Consulta de síntomas")
    session_id = test_agent_chat("Me duele la cabeza y tengo fiebre desde hace 2 días")
    
    time.sleep(2)
    
    # Test 2: Buscar doctor (debe usar DoctorsActionGroup)
    print("\n\n🧪 Test 2: Buscar doctor")
    session_id = test_agent_chat(
        "Necesito agendar una cita con un cardiólogo",
        session_id=session_id
    )
    
    time.sleep(2)
    
    # Test 3: Talleres (debe usar WorkshopsActionGroup)
    print("\n\n🧪 Test 3: Buscar taller")
    session_id = test_agent_chat(
        "Quiero inscribirme en un taller de manejo del estrés",
        session_id=session_id
    )
    
    time.sleep(2)
    
    # Test 4: Conversación contextual
    print("\n\n🧪 Test 4: Seguimiento contextual")
    test_agent_chat(
        "¿Qué otros talleres hay disponibles?",
        session_id=session_id
    )
    
    print("\n\n✅ Tests completados")
