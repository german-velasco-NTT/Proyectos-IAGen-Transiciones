#!/usr/bin/env python3
"""Script para verificar si el HTML se carga correctamente"""

import subprocess
import time

print("🌐 Abriendo navegador en http://localhost:8006...")
print("Instrucciones:")
print("1. Cuando se abra el navegador, abre la consola (F12)")
print("2. Copia la URL: https://umane.emeal.nttdata.com/git/COITDEVSOCOEAPPSIA/crewai-nativeai")
print("3. Pega el token: sebwvkV21gB-gpK12j1y")
print("4. Pega el project path: COITDEVSOCOEAPPSIA/crewai-nativeai")
print("5. Haz clic en 'Iniciar Análisis'")
print("6. Observa la consola (F12) para ver los logs")
print("7. Si todo funciona, verás los números actualizar en el dashboard\n")

# Abrir navegador
subprocess.Popen(["open", "http://localhost:8006"])
print("✅ Navegador abierto (si no aparece, ve a http://localhost:8006)")
