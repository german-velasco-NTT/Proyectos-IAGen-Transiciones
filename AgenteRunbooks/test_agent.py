#!/usr/bin/env python3
"""
Test automático para AgenteRunbooks
Simula un usuario completo: análisis de tickets y visualización de resultados
"""

import requests
import json
import time
import sys

API_BASE = "http://localhost:8006"

def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_health():
    """Test health endpoint"""
    print_section("1️⃣  HEALTH CHECK")
    response = requests.get(f"{API_BASE}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    print("✅ Health check OK")

def test_analyze():
    """Test analyze endpoint with GitLab repository"""
    print_section("2️⃣  INICIAR ANÁLISIS")
    
    config = {
        "repository_url": "https://umane.emeal.nttdata.com/git/COITDEVSOCOEAPPSIA/crewai-nativeai",
        "token": "sebwvkV21gB-gpK12j1y",
        "project_path": "COITDEVSOCOEAPPSIA/crewai-nativeai"
    }
    
    payload = {"config": config}
    print(f"📤 Enviando análisis...")
    print(f"   Repositorio: {config['repository_url']}")
    
    response = requests.post(f"{API_BASE}/api/v1/analyze", json=payload)
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None
    
    job = response.json()
    job_id = job['job_id']
    print(f"✅ Job creado: {job_id}")
    print(f"   Status inicial: {job['status']}")
    print(f"   Mensaje: {job['message']}")
    
    return job_id

def poll_job(job_id):
    """Poll job status until completion"""
    print_section("3️⃣  MONITOREAR PROGRESO")
    
    print(f"🔄 Monitoreando job {job_id}...\n")
    
    max_attempts = 30  # 60 segundos máximo
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        response = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}")
        
        if response.status_code != 200:
            print(f"❌ Job no encontrado")
            return None
        
        job = response.json()
        progress = job.get('progress', 0)
        status = job['status']
        message = job['message']
        
        # Mostrar barra de progreso
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r[{bar}] {progress:.0f}% - {message}", end="")
        
        if status == "completed":
            print(f"\n\n✅ Análisis completado")
            return job
        elif status == "failed":
            print(f"\n❌ Análisis falló: {message}")
            return None
        
        time.sleep(2)
    
    print(f"\n❌ Timeout esperando resultado")
    return None

def show_results(job):
    """Display analysis results"""
    print_section("4️⃣  RESULTADOS DEL ANÁLISIS")
    
    if not job or not job.get('data'):
        print("❌ No hay datos para mostrar")
        return
    
    analysis = job['data']
    
    print(f"📊 ESTADÍSTICAS GENERALES")
    print(f"  • Total de Tickets: {analysis['total']}")
    print(f"  • Abiertos: {analysis['opened']} ({100*analysis['opened']/analysis['total']:.0f}%)")
    print(f"  • Cerrados: {analysis['closed']} ({100*analysis['closed']/analysis['total']:.0f}%)")
    
    print(f"\n⚠️  DISTRIBUCIÓN DE SEVERIDAD")
    sev = analysis['severity_distribution']
    print(f"  • Crítica:  {sev['critical']}")
    print(f"  • Alta:     {sev['high']}")
    print(f"  • Media:    {sev['medium']}")
    print(f"  • Baja:     {sev['low']}")
    
    print(f"\n🏷️  CATEGORÍAS PRINCIPALES")
    categories = sorted(analysis['categories'].items(), key=lambda x: x[1], reverse=True)[:5]
    for label, count in categories:
        print(f"  • {label}: {count}")
    
    print(f"\n🔝 TOP ISSUES RESUELTOS")
    for i, issue in enumerate(analysis['top_issues'][:3], 1):
        print(f"  {i}. [{issue['severity'].upper()}] {issue['title']}")

def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "🧪 TEST AGENTERUNBOOKS" + " "*31 + "║")
    print("╚" + "="*68 + "╝")
    
    try:
        # Test health
        test_health()
        time.sleep(1)
        
        # Start analysis
        job_id = test_analyze()
        if not job_id:
            print("❌ No se pudo iniciar análisis")
            return False
        
        time.sleep(2)
        
        # Poll until completion
        job = poll_job(job_id)
        if not job:
            print("❌ No se completó el análisis")
            return False
        
        # Show results
        show_results(job)
        
        print_section("✅ PRUEBA COMPLETADA EXITOSAMENTE")
        print("El agente está funcionando correctamente!\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
