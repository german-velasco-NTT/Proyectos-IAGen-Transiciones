#!/bin/bash

# Script para reiniciar AgenteDependencias

echo "🛑 Deteniendo proceso anterior..."
pkill -f "AgenteDependencias.*uvicorn" || true
sleep 2

echo "📁 Entrando al directorio..."
cd "$(dirname "$0")"

echo "🐍 Activando entorno virtual..."
source venv/bin/activate 2>/dev/null || true

echo "🚀 Iniciando AgenteDependencias en puerto 8005..."
python -m uvicorn api:app --host 0.0.0.0 --port 8005 --reload

