#!/bin/bash
# Helper script to install dependencies and run the server
# Run with: sh install_and_run.sh

echo "🔍 Checking Python environment..."

# Try to use python3
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    echo "⚠️ 'python3' not found, trying 'python'..."
    PYTHON_CMD="python"
fi

echo "📦 Installing dependencies using $PYTHON_CMD..."
$PYTHON_CMD -m pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed."
    echo "🚀 Starting Runbook Generator on port 8006..."
    $PYTHON_CMD api.py
else
    echo "❌ Error installing dependencies."
    echo "Try running: $PYTHON_CMD -m pip install -r requirements.txt manually."
    exit 1
fi
