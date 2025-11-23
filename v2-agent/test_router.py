"""
Script de prueba para el router de Bedrock
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_router(message: str, user_id: str = "test_user_123"):
    """Prueba el endpoint principal del router"""
    
    response = requests.post(
        f"{BASE_URL}/agent/route",
        json={
            "user_id": user_id,
            "message": message
        }
    )
    
    print(f"\n{'='*60}")
    print(f"Mensaje: {message}")
    print(f"{'='*60}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Endpoint: {data['endpoint']}")
        print(f"✓ Confianza: {data['confidence']}")
        print(f"✓ Razonamiento: {data['reasoning']}")
        print(f"\nRespuesta:")
        print(json.dumps(data['response'], indent=2, ensure_ascii=False))
    else:
        print(f"✗ Error {response.status_code}: {response.text}")
    
    return response


if __name__ == "__main__":
    print("Probando el router de Bedrock Agent...")
    
    # Test 1: Síntomas (debe ir a triage)
    test_router("Me duele la cabeza y tengo fiebre desde hace 2 días")
    
    # Test 2: Buscar doctor (debe ir a doctors)
    test_router("Necesito agendar una cita con un cardiólogo")
    
    # Test 3: Talleres (debe ir a workshops)
    test_router("Quiero inscribirme en un taller de manejo del estrés")
    
    # Test 4: Caso ambiguo
    test_router("Estoy muy estresado últimamente")
