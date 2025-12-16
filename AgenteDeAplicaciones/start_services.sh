#!/bin/bash
# Script para levantar frontend y backend

echo "🚀 Iniciando servicios..."

# Matar procesos anteriores
killall -9 python3 2>/dev/null
sleep 1

# Levantar servidor web en background
echo "📱 Levantando servidor web (puerto 8000)..."
cd /Users/juanguaqueta/Desktop/AgentesIA/AgenteDeAplicaciones/web
python3 serve.py &
WEB_PID=$!
sleep 2

# Levantar servidor API en background
echo "⚙️ Levantando servidor API (puerto 8001)..."
cd /Users/juanguaqueta/Desktop/AgentesIA/AgenteDeAplicaciones
/Users/juanguaqueta/Library/Python/3.9/bin/uvicorn api:app --host 127.0.0.1 --port 8001 &
API_PID=$!
sleep 2

echo ""
echo "✅ Servicios iniciados:"
echo "  📱 Web:  http://127.0.0.1:8000/"
echo "  ⚙️  API:  http://127.0.0.1:8001/"
echo ""
echo "PIDs: WEB=$WEB_PID, API=$API_PID"
echo "Presiona Ctrl+C para detener"
echo ""

# Esperar indefinidamente
wait
