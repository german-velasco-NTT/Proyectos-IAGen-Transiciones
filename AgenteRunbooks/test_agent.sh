#!/bin/bash
# Test script for AgenteRunbooks

echo "🚀 Testing AgenteRunbooks API"
echo "==============================="
echo ""

API_URL="http://localhost:8006"
GITLAB_TOKEN="sebwvkV21gB-gpK12j1y"
PROJECT_URL="https://umane.emeal.nttdata.com/git"

# Test 1: Health Check
echo "✓ Test 1: Health Check"
curl -s "$API_URL/health" | jq . || echo "❌ Health check failed"
echo ""

# Test 2: Get Mock Issues
echo "✓ Test 2: Get Mock Issues (120 tickets de prueba)"
ISSUE_COUNT=$(curl -s "$API_URL/api/v1/issues" | jq '.count')
echo "  Total issues: $ISSUE_COUNT"
echo ""

# Test 3: Start Analysis
echo "✓ Test 3: Iniciar análisis..."
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d "{
    \"config\": {
      \"repository_url\": \"$PROJECT_URL\",
      \"token\": \"$GITLAB_TOKEN\",
      \"project_path\": \"COITDEVSOCOEAPPSIA/crewai-nativeai\",
      \"ticket_states\": [\"opened\", \"closed\"],
      \"min_tickets\": 5
    }
  }")

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "  Job ID: $JOB_ID"
echo ""

# Test 4: Poll Job Status
echo "✓ Test 4: Esperando resultado (máximo 30 segundos)..."
for i in {1..15}; do
  STATUS=$(curl -s "$API_URL/api/v1/jobs/$JOB_ID" | jq -r '.status')
  PROGRESS=$(curl -s "$API_URL/api/v1/jobs/$JOB_ID" | jq -r '.progress')
  
  if [ "$STATUS" = "completed" ]; then
    echo "  ✅ Análisis completado en $((i*2)) segundos"
    echo ""
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "  ❌ Análisis falló"
    echo ""
    break
  else
    echo "  ⏳ Status: $STATUS ($PROGRESS%)"
    sleep 2
  fi
done

# Test 5: Get Results
echo "✓ Test 5: Obteniendo resultados..."
RESULTS=$(curl -s "$API_URL/api/v1/jobs/$JOB_ID")
echo "$RESULTS" | jq '.data' | head -50
echo ""

# Test 6: Download Results
echo "✓ Test 6: Descargando análisis completo..."
curl -s "$API_URL/api/v1/jobs/$JOB_ID/download" > analysis_$JOB_ID.json
echo "  Guardado en: analysis_$JOB_ID.json"
echo "  Tamaño: $(wc -c < analysis_$JOB_ID.json) bytes"
echo ""

echo "✅ Todos los tests completados!"
echo ""
echo "Dashboard disponible en: http://localhost:8006"
