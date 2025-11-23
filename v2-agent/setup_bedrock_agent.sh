#!/bin/bash

# Script para configurar AWS Bedrock Agent con AWS CLI
# Asegúrate de tener AWS CLI configurado con las credenciales correctas

set -e  # Salir si hay algún error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Configurando AWS Bedrock Agent${NC}\n"

# Variables - MODIFICA ESTAS
AWS_REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AGENT_NAME="health-assistant-agent"
LAMBDA_FUNCTION_NAME="bedrock-health-agent-actions"
ROLE_NAME="bedrock-agent-role"
LAMBDA_ROLE_NAME="lambda-bedrock-agent-role"

echo "📋 Configuración:"
echo "   Region: $AWS_REGION"
echo "   Account ID: $ACCOUNT_ID"
echo "   Agent Name: $AGENT_NAME"
echo ""

# ============================================
# PASO 1: Crear rol IAM para Lambda
# ============================================
echo -e "${YELLOW}📝 Paso 1: Creando rol IAM para Lambda...${NC}"

# Trust policy para Lambda
cat > /tmp/lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Crear rol para Lambda (si no existe)
if aws iam get-role --role-name $LAMBDA_ROLE_NAME 2>/dev/null; then
    echo "   ✓ Rol Lambda ya existe"
else
    aws iam create-role \
        --role-name $LAMBDA_ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json
    
    # Adjuntar política básica de Lambda
    aws iam attach-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    echo "   ✓ Rol Lambda creado"
    sleep 10  # Esperar a que el rol se propague
fi

LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

# ============================================
# PASO 2: Desplegar Lambda Function
# ============================================
echo -e "\n${YELLOW}📦 Paso 2: Desplegando Lambda Function...${NC}"

# Crear package
mkdir -p /tmp/lambda_package
cp lambda_handler.py /tmp/lambda_package/
cd /tmp/lambda_package
zip -q -r ../lambda_function.zip .
cd - > /dev/null

# Crear o actualizar Lambda
if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>/dev/null; then
    echo "   Actualizando función existente..."
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --zip-file fileb:///tmp/lambda_function.zip \
        --region $AWS_REGION > /dev/null
else
    echo "   Creando nueva función..."
    aws lambda create-function \
        --function-name $LAMBDA_FUNCTION_NAME \
        --runtime python3.11 \
        --role $LAMBDA_ROLE_ARN \
        --handler lambda_handler.lambda_handler \
        --zip-file fileb:///tmp/lambda_function.zip \
        --timeout 30 \
        --memory-size 256 \
        --region $AWS_REGION > /dev/null
fi

LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${LAMBDA_FUNCTION_NAME}"
echo "   ✓ Lambda desplegada: $LAMBDA_ARN"

# Dar permiso a Bedrock para invocar Lambda
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id bedrock-agent-invoke \
    --action lambda:InvokeFunction \
    --principal bedrock.amazonaws.com \
    --region $AWS_REGION 2>/dev/null || echo "   ✓ Permiso ya existe"

# ============================================
# PASO 3: Crear rol IAM para Bedrock Agent
# ============================================
echo -e "\n${YELLOW}📝 Paso 3: Creando rol IAM para Bedrock Agent...${NC}"

# Trust policy para Bedrock
cat > /tmp/bedrock-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:bedrock:${AWS_REGION}:${ACCOUNT_ID}:agent/*"
        }
      }
    }
  ]
}
EOF

# Política de permisos para el agente
cat > /tmp/bedrock-agent-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:${AWS_REGION}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "${LAMBDA_ARN}"
    }
  ]
}
EOF

# Crear rol para Bedrock Agent
if aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
    echo "   ✓ Rol Bedrock ya existe"
else
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/bedrock-trust-policy.json
    
    aws iam put-role-policy \
        --role-name $ROLE_NAME \
        --policy-name bedrock-agent-permissions \
        --policy-document file:///tmp/bedrock-agent-policy.json
    
    echo "   ✓ Rol Bedrock creado"
    sleep 10
fi

AGENT_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# ============================================
# PASO 4: Crear Bedrock Agent
# ============================================
echo -e "\n${YELLOW}🤖 Paso 4: Creando Bedrock Agent...${NC}"

AGENT_INSTRUCTION="Eres un asistente de salud inteligente que ayuda a usuarios con:

1. Evaluación de síntomas y triaje médico
2. Búsqueda y agendamiento de citas con doctores
3. Búsqueda y registro en talleres de bienestar

Cuando un usuario te consulte:
- Si menciona síntomas, dolor, malestar o emergencias → usa TriageActionGroup
- Si busca doctores, citas médicas o especialistas → usa DoctorsActionGroup
- Si busca talleres, bienestar, estrés o nutrición → usa WorkshopsActionGroup

Siempre responde en español de manera amable y profesional."

# Crear agente
AGENT_ID=$(aws bedrock-agent create-agent \
    --agent-name $AGENT_NAME \
    --agent-resource-role-arn $AGENT_ROLE_ARN \
    --foundation-model "anthropic.claude-3-sonnet-20240229-v1:0" \
    --instruction "$AGENT_INSTRUCTION" \
    --region $AWS_REGION \
    --query 'agent.agentId' \
    --output text 2>/dev/null || \
    aws bedrock-agent list-agents --region $AWS_REGION --query "agentSummaries[?agentName=='$AGENT_NAME'].agentId" --output text)

echo "   ✓ Agent ID: $AGENT_ID"

# ============================================
# PASO 5: Crear Action Groups
# ============================================
echo -e "\n${YELLOW}⚡ Paso 5: Creando Action Groups...${NC}"

# Action Group 1: Triage
echo "   Creando TriageActionGroup..."

cat > /tmp/triage-schema.json <<'EOF'
{
  "openapi": "3.0.0",
  "info": {
    "title": "Triage API",
    "version": "1.0.0",
    "description": "API para evaluación de síntomas y triaje médico"
  },
  "paths": {
    "/triage/interpret": {
      "post": {
        "summary": "Evalúa síntomas del usuario",
        "description": "Analiza los síntomas reportados y determina el nivel de riesgo",
        "operationId": "evaluateSymptoms",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["user_id", "message"],
                "properties": {
                  "user_id": {
                    "type": "string",
                    "description": "ID del usuario"
                  },
                  "message": {
                    "type": "string",
                    "description": "Descripción de síntomas del usuario"
                  }
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Evaluación completada",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "risk": {
                      "type": "object",
                      "properties": {
                        "risk_level": {
                          "type": "string",
                          "enum": ["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]
                        },
                        "recommended_action": {
                          "type": "string"
                        },
                        "reasons": {
                          "type": "array",
                          "items": {
                            "type": "string"
                          }
                        }
                      }
                    },
                    "reply": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
EOF

aws bedrock-agent create-agent-action-group \
    --agent-id $AGENT_ID \
    --agent-version DRAFT \
    --action-group-name "TriageActionGroup" \
    --action-group-executor lambda=$LAMBDA_ARN \
    --api-schema file:///tmp/triage-schema.json \
    --region $AWS_REGION > /dev/null 2>&1 || echo "   ⚠️  TriageActionGroup ya existe o error"

echo "   ✓ TriageActionGroup creado"

# Action Group 2: Doctors
echo "   Creando DoctorsActionGroup..."

cat > /tmp/doctors-schema.json <<'EOF'
{
  "openapi": "3.0.0",
  "info": {
    "title": "Doctors API",
    "version": "1.0.0",
    "description": "API para búsqueda de doctores y gestión de citas"
  },
  "paths": {
    "/doctors/interpret": {
      "post": {
        "summary": "Busca doctores o gestiona citas",
        "description": "Interpreta solicitudes de búsqueda de doctores o gestión de citas",
        "operationId": "manageDoctorAppointments",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["user_id", "message"],
                "properties": {
                  "user_id": {"type": "string"},
                  "message": {"type": "string"}
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Operación completada",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "operation": {
                      "type": "string",
                      "enum": ["LIST", "CREATE", "CANCEL"]
                    },
                    "appointments": {
                      "type": "array",
                      "items": {"type": "object"}
                    },
                    "message": {"type": "string"}
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
EOF

aws bedrock-agent create-agent-action-group \
    --agent-id $AGENT_ID \
    --agent-version DRAFT \
    --action-group-name "DoctorsActionGroup" \
    --action-group-executor lambda=$LAMBDA_ARN \
    --api-schema file:///tmp/doctors-schema.json \
    --region $AWS_REGION > /dev/null 2>&1 || echo "   ⚠️  DoctorsActionGroup ya existe o error"

echo "   ✓ DoctorsActionGroup creado"

# Action Group 3: Workshops
echo "   Creando WorkshopsActionGroup..."

cat > /tmp/workshops-schema.json <<'EOF'
{
  "openapi": "3.0.0",
  "info": {
    "title": "Workshops API",
    "version": "1.0.0",
    "description": "API para talleres de bienestar"
  },
  "paths": {
    "/workshops/interpret": {
      "post": {
        "summary": "Busca talleres o gestiona inscripciones",
        "description": "Interpreta solicitudes sobre talleres de bienestar",
        "operationId": "manageWorkshops",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["user_id", "message"],
                "properties": {
                  "user_id": {"type": "string"},
                  "message": {"type": "string"}
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Operación completada",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "operation": {
                      "type": "string",
                      "enum": ["SEARCH", "LIST_MY_WORKSHOPS", "REGISTER"]
                    },
                    "workshops": {
                      "type": "array",
                      "items": {"type": "object"}
                    },
                    "message": {"type": "string"}
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
EOF

aws bedrock-agent create-agent-action-group \
    --agent-id $AGENT_ID \
    --agent-version DRAFT \
    --action-group-name "WorkshopsActionGroup" \
    --action-group-executor lambda=$LAMBDA_ARN \
    --api-schema file:///tmp/workshops-schema.json \
    --region $AWS_REGION > /dev/null 2>&1 || echo "   ⚠️  WorkshopsActionGroup ya existe o error"

echo "   ✓ WorkshopsActionGroup creado"

# ============================================
# PASO 6: Preparar el agente
# ============================================
echo -e "\n${YELLOW}🔧 Paso 6: Preparando el agente...${NC}"

aws bedrock-agent prepare-agent \
    --agent-id $AGENT_ID \
    --region $AWS_REGION > /dev/null

echo "   ✓ Agente preparado"

# Esperar a que termine la preparación
echo "   Esperando a que termine la preparación..."
sleep 15

# ============================================
# PASO 7: Crear alias
# ============================================
echo -e "\n${YELLOW}🏷️  Paso 7: Creando alias...${NC}"

ALIAS_ID=$(aws bedrock-agent create-agent-alias \
    --agent-id $AGENT_ID \
    --agent-alias-name "production" \
    --region $AWS_REGION \
    --query 'agentAlias.agentAliasId' \
    --output text 2>/dev/null || echo "TSTALIASID")

echo "   ✓ Alias ID: $ALIAS_ID"

# ============================================
# PASO 8: Actualizar .env
# ============================================
echo -e "\n${YELLOW}📝 Paso 8: Actualizando .env...${NC}"

if [ -f ".env" ]; then
    # Actualizar valores existentes o agregar nuevos
    sed -i.bak "s/^BEDROCK_AGENT_ID=.*/BEDROCK_AGENT_ID=$AGENT_ID/" .env
    sed -i.bak "s/^BEDROCK_AGENT_ALIAS_ID=.*/BEDROCK_AGENT_ALIAS_ID=$ALIAS_ID/" .env
    
    # Si no existen, agregarlos
    grep -q "BEDROCK_AGENT_ID" .env || echo "BEDROCK_AGENT_ID=$AGENT_ID" >> .env
    grep -q "BEDROCK_AGENT_ALIAS_ID" .env || echo "BEDROCK_AGENT_ALIAS_ID=$ALIAS_ID" >> .env
    
    rm -f .env.bak
else
    cp .env.example .env
    sed -i.bak "s/^BEDROCK_AGENT_ID=.*/BEDROCK_AGENT_ID=$AGENT_ID/" .env
    sed -i.bak "s/^BEDROCK_AGENT_ALIAS_ID=.*/BEDROCK_AGENT_ALIAS_ID=$ALIAS_ID/" .env
    rm -f .env.bak
fi

echo "   ✓ .env actualizado"

# Limpiar archivos temporales
rm -f /tmp/lambda-trust-policy.json /tmp/bedrock-trust-policy.json /tmp/bedrock-agent-policy.json
rm -f /tmp/triage-schema.json /tmp/doctors-schema.json /tmp/workshops-schema.json
rm -rf /tmp/lambda_package /tmp/lambda_function.zip

# ============================================
# RESUMEN
# ============================================
echo -e "\n${GREEN}✅ ¡Configuración completada!${NC}\n"
echo "📋 Resumen:"
echo "   Agent ID: $AGENT_ID"
echo "   Alias ID: $ALIAS_ID"
echo "   Lambda ARN: $LAMBDA_ARN"
echo "   Region: $AWS_REGION"
echo ""
echo "🚀 Próximos pasos:"
echo "   1. Ejecuta: uvicorn main_agent:app --reload"
echo "   2. Prueba: python test_bedrock_agent.py"
echo ""
echo "🔗 Ver en AWS Console:"
echo "   https://${AWS_REGION}.console.aws.amazon.com/bedrock/home?region=${AWS_REGION}#/agents/${AGENT_ID}"
