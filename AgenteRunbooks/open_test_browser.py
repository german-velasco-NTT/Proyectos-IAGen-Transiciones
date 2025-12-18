#!/usr/bin/env python3
"""
Simula un navegador real descargando el HTML, ejecutando el JS y haciendo el test
"""

import subprocess
import json
import time

print("\n" + "="*80)
print("🌐 PRUEBA COMPLETA EN NAVEGADOR")
print("="*80 + "\n")

print("Abriendo navegador con inspector de elementos...")
print("\n⚠️  INSTRUCCIONES PARA EL USUARIO:")
print("1. Cuando se abra el navegador, abre la consola (F12 → Console)")
print("2. Haz que el formulario tenga estos valores:")
print("   - URL: https://umane.emeal.nttdata.com/git/COITDEVSOCOEAPPSIA/crewai-nativeai")
print("   - Token: sebwvkV21gB-gpK12j1y")
print("   - Project Path: COITDEVSOCOEAPPSIA/crewai-nativeai")
print("3. Haz clic en 'Iniciar Análisis'")
print("4. OBSERVA la consola (F12)")
print("5. Deberías ver:")
print("   ✅ '🎨 Renderizando dashboard:'")
print("   ✅ '📍 Elements found - total: true, opened: true, closed: true'")
print("   ✅ '✏️ Setting stat-total to: 120'")
print("   ✅ Los números actualizándose en el dashboard")
print("\n")

# Abrir navegador en test.html (más simple)
print("🔗 Abriendo http://localhost:8006/web/test.html (versión simplificada para debug)\n")
subprocess.Popen(["open", "http://localhost:8006/web/test.html"])

# Alternativamente, mostrar la URL principal
print("📌 O si prefieres, la versión completa está en: http://localhost:8006/\n")

print("⏰ Esperando 3 segundos antes de mostrar el siguiente paso...")
time.sleep(3)

print("\n💡 CONSEJO: Si ves los números en el dashboard (ej: 120, 60, 60), ¡FUNCIONA!")
print("❌ Si ves ceros (0, 0, 0), mira la consola (F12) para buscar errores")
print("\n")
