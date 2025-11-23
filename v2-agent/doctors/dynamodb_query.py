"""
Utilidades para ejecutar queries de DynamoDB basadas en respuestas de Claude.
"""

import boto3
from typing import Dict, List, Any, Optional
from decimal import Decimal
from botocore.exceptions import ClientError


def decimal_to_native(obj):
    """Convierte Decimal de DynamoDB a tipos nativos de Python"""
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj


def ejecutar_consulta_doctores(consulta: Dict[str, Any], region: str = 'us-east-1') -> List[Dict]:
    """
    Ejecuta una consulta en la tabla de doctores.
    
    Args:
        consulta: Diccionario con los parámetros de la consulta
        Ejemplo:
        {
            "TableName": "doctores",
            "IndexName": "especialidad-index",
            "KeyConditionExpression": "especialidad = :esp",
            "ExpressionAttributeValues": {":esp": "cardiología"}
        }
    
    Returns:
        Lista de doctores encontrados
    """
    
    dynamodb = boto3.client('dynamodb', region_name=region)
    
    # Convertir valores a formato DynamoDB
    if 'ExpressionAttributeValues' in consulta:
        attr_values = {}
        for key, value in consulta['ExpressionAttributeValues'].items():
            if isinstance(value, str):
                attr_values[key] = {'S': value}
            elif isinstance(value, int):
                attr_values[key] = {'N': str(value)}
            elif isinstance(value, list):
                attr_values[key] = {'L': [{'S': v} for v in value]}
        consulta['ExpressionAttributeValues'] = attr_values
    
    # Ejecutar query o scan
    try:
        if 'KeyConditionExpression' in consulta:
            response = dynamodb.query(**consulta)
        else:
            response = dynamodb.scan(**consulta)
    except ClientError as e:
        # Si el índice no existe, hacer un Scan con FilterExpression
        if 'IndexName' in consulta and 'does not have the specified index' in str(e):
            print(f"⚠️  Índice no disponible, usando Scan con filtro...")
            
            # Convertir KeyConditionExpression a FilterExpression
            filter_expr = consulta.get('KeyConditionExpression', '').replace('=', '=')
            
            scan_params = {
                'TableName': consulta['TableName'],
                'FilterExpression': filter_expr,
                'ExpressionAttributeValues': consulta.get('ExpressionAttributeValues', {})
            }
            
            response = dynamodb.scan(**scan_params)
        else:
            raise
    
    # Convertir respuesta de DynamoDB a formato Python
    items = []
    for item in response.get('Items', []):
        parsed_item = {}
        for key, value in item.items():
            if 'S' in value:
                parsed_item[key] = value['S']
            elif 'N' in value:
                parsed_item[key] = int(value['N']) if '.' not in value['N'] else float(value['N'])
            elif 'L' in value:
                parsed_item[key] = [v.get('S', v.get('N', '')) for v in value['L']]
            elif 'M' in value:
                parsed_item[key] = {k: v.get('S', v.get('N', '')) for k, v in value['M'].items()}
        items.append(parsed_item)
    
    return items


def ejecutar_consulta_horarios(consulta: Dict[str, Any], region: str = 'us-east-1') -> List[Dict]:
    """
    Ejecuta una consulta en la tabla de horarios_doctores.
    
    Args:
        consulta: Diccionario con los parámetros de la consulta
        Ejemplo:
        {
            "TableName": "horarios_doctores",
            "KeyConditionExpression": "doctor_id = :id",
            "ExpressionAttributeValues": {":id": "DOC-0001"}
        }
    
    Returns:
        Lista de horarios encontrados
    """
    
    dynamodb = boto3.client('dynamodb', region_name=region)
    
    # Convertir valores a formato DynamoDB
    if 'ExpressionAttributeValues' in consulta:
        attr_values = {}
        for key, value in consulta['ExpressionAttributeValues'].items():
            if isinstance(value, str):
                attr_values[key] = {'S': value}
            elif isinstance(value, int):
                attr_values[key] = {'N': str(value)}
            elif isinstance(value, list):
                attr_values[key] = {'L': [{'S': v} for v in value]}
        consulta['ExpressionAttributeValues'] = attr_values
    
    # Ejecutar query
    response = dynamodb.query(**consulta)
    
    # Convertir respuesta
    items = []
    for item in response.get('Items', []):
        parsed_item = {}
        for key, value in item.items():
            if 'S' in value:
                parsed_item[key] = value['S']
            elif 'N' in value:
                parsed_item[key] = int(value['N']) if '.' not in value['N'] else float(value['N'])
            elif 'L' in value:
                parsed_item[key] = [v.get('S', v.get('N', '')) for v in value['L']]
        items.append(parsed_item)
    
    return items


def ejecutar_consultas_desde_claude(respuesta_claude: Dict[str, Any], region: str = 'us-east-1') -> Dict[str, List[Dict]]:
    """
    Ejecuta las consultas generadas por Claude.
    
    Args:
        respuesta_claude: Respuesta completa de Claude con consultas
        Ejemplo:
        {
            "consulta_doctores": {
                "TableName": "doctores",
                "IndexName": "especialidad-index",
                "KeyConditionExpression": "especialidad = :esp",
                "ExpressionAttributeValues": {":esp": "cardiología"}
            },
            "consulta_horarios": []
        }
    
    Returns:
        Diccionario con resultados:
        {
            "doctores": [...],
            "horarios": [...]
        }
    """
    
    resultados = {
        "doctores": [],
        "horarios": []
    }
    
    # Ejecutar consulta de doctores si existe
    if respuesta_claude.get('consulta_doctores'):
        try:
            resultados['doctores'] = ejecutar_consulta_doctores(
                respuesta_claude['consulta_doctores'],
                region
            )
        except Exception as e:
            print(f"Error ejecutando consulta de doctores: {str(e)}")
    
    # Ejecutar consulta de horarios si existe
    if respuesta_claude.get('consulta_horarios') and respuesta_claude['consulta_horarios']:
        try:
            # Si es una lista de consultas
            if isinstance(respuesta_claude['consulta_horarios'], list):
                for consulta in respuesta_claude['consulta_horarios']:
                    horarios = ejecutar_consulta_horarios(consulta, region)
                    resultados['horarios'].extend(horarios)
            # Si es una sola consulta
            else:
                resultados['horarios'] = ejecutar_consulta_horarios(
                    respuesta_claude['consulta_horarios'],
                    region
                )
        except Exception as e:
            print(f"Error ejecutando consulta de horarios: {str(e)}")
    
    return resultados


# Versión simplificada usando boto3.resource (más fácil)
def ejecutar_consultas_simple(respuesta_claude: Dict[str, Any], region: str = 'us-east-1') -> Dict[str, List[Dict]]:
    """
    Versión simplificada usando boto3.resource.
    Más fácil de usar pero menos control.
    """
    
    dynamodb = boto3.resource('dynamodb', region_name=region)
    resultados = {
        "doctores": [],
        "horarios": []
    }
    
    # Consulta de doctores
    if respuesta_claude.get('consulta_doctores'):
        try:
            consulta = respuesta_claude['consulta_doctores']
            table = dynamodb.Table(consulta['TableName'])
            
            # Preparar parámetros
            params = {}
            if 'IndexName' in consulta:
                params['IndexName'] = consulta['IndexName']
            if 'KeyConditionExpression' in consulta:
                # Convertir expresión a formato boto3
                key_condition = consulta['KeyConditionExpression']
                attr_values = consulta.get('ExpressionAttributeValues', {})
                
                # Ejemplo: "especialidad = :esp" -> Key('especialidad').eq('cardiología')
                from boto3.dynamodb.conditions import Key
                
                # Parsear la expresión (simplificado)
                if '=' in key_condition:
                    field, placeholder = key_condition.split('=')
                    field = field.strip()
                    placeholder = placeholder.strip()
                    value = attr_values.get(placeholder)
                    
                    response = table.query(
                        IndexName=params.get('IndexName'),
                        KeyConditionExpression=Key(field).eq(value)
                    )
                    resultados['doctores'] = [decimal_to_native(item) for item in response.get('Items', [])]
        except Exception as e:
            print(f"Error ejecutando consulta de doctores: {str(e)}")
    
    # Consulta de horarios
    if respuesta_claude.get('consulta_horarios'):
        try:
            consultas = respuesta_claude['consulta_horarios']
            if not isinstance(consultas, list):
                consultas = [consultas]
            
            for consulta in consultas:
                if not consulta:
                    continue
                    
                table = dynamodb.Table(consulta['TableName'])
                
                # Parsear expresión
                key_condition = consulta.get('KeyConditionExpression', '')
                attr_values = consulta.get('ExpressionAttributeValues', {})
                
                from boto3.dynamodb.conditions import Key
                
                if '=' in key_condition:
                    field, placeholder = key_condition.split('=')
                    field = field.strip()
                    placeholder = placeholder.strip()
                    value = attr_values.get(placeholder)
                    
                    response = table.query(
                        KeyConditionExpression=Key(field).eq(value)
                    )
                    resultados['horarios'].extend([decimal_to_native(item) for item in response.get('Items', [])])
        except Exception as e:
            print(f"Error ejecutando consulta de horarios: {str(e)}")
    
    return resultados
