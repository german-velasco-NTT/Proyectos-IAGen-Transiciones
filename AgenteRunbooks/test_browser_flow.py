#!/usr/bin/env python3
"""Test completo del flujo de navegador - emula exactamente lo que hace JS"""

import requests
import json
import time
from typing import Dict, Any

API_BASE = "http://localhost:8006"

def test_complete_flow():
    """Test completo del flujo"""
    print("\n" + "="*80)
    print("🧪 TEST COMPLETO DEL FLUJO FRONTEND")
    print("="*80 + "\n")
    
    # 1. Health check
    print("1️⃣  HEALTH CHECK")
    print("-" * 80)
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        assert response.status_code == 200
        print("✅ Health OK\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return
    
    # 2. Iniciar análisis (POST)
    print("2️⃣  INICIAR ANÁLISIS (POST /api/v1/analyze)")
    print("-" * 80)
    
    payload = {
        "config": {
            "repository_url": "https://umane.emeal.nttdata.com/git/COITDEVSOCOEAPPSIA/crewai-nativeai",
            "token": "sebwvkV21gB-gpK12j1y",
            "project_path": "COITDEVSOCOEAPPSIA/crewai-nativeai",
            "ticket_states": ["opened", "closed"],
            "min_tickets": 5
        }
    }
    
    print(f"POST Body: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/analyze",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\nStatus: {response.status_code}")
        job_data = response.json()
        print(f"Response:\n{json.dumps(job_data, indent=2)}")
        
        if response.status_code != 200:
            print("❌ Error en POST")
            return
        
        job_id = job_data.get("job_id")
        print(f"\n✅ Job created: {job_id}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return
    
    # 3. Polling (GET)
    print("3️⃣  POLLING (GET /api/v1/jobs/{job_id})")
    print("-" * 80)
    
    max_polls = 15
    poll_count = 0
    
    while poll_count < max_polls:
        poll_count += 1
        
        try:
            response = requests.get(
                f"{API_BASE}/api/v1/jobs/{job_id}",
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"❌ Poll {poll_count}: Status {response.status_code}")
                break
            
            job = response.json()
            status = job.get("status", "unknown")
            message = job.get("message", "")
            progress = job.get("progress", 0)
            data = job.get("data")
            
            # Mostrar en consola
            print(f"\nPoll {poll_count}:")
            print(f"  Status: {status}")
            print(f"  Message: {message}")
            print(f"  Progress: {progress}%")
            print(f"  Data present: {data is not None}")
            
            if data:
                print(f"  Data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                if isinstance(data, dict):
                    print(f"    - total: {data.get('total')}")
                    print(f"    - opened: {data.get('opened')}")
                    print(f"    - closed: {data.get('closed')}")
                    print(f"    - severity_distribution: {data.get('severity_distribution')}")
                    print(f"    - categories: {data.get('categories')}")
                    print(f"    - top_issues count: {len(data.get('top_issues', []))}")
            
            # Si está completado, mostrar todo
            if status == "completed":
                print("\n✅ Analysis completed!")
                print("\nFull response:")
                print(json.dumps(job, indent=2))
                break
            elif status == "failed":
                print("\n❌ Analysis failed!")
                print("\nFull response:")
                print(json.dumps(job, indent=2))
                break
            
            time.sleep(1)
        
        except Exception as e:
            print(f"❌ Poll error: {e}")
            break
    
    if poll_count >= max_polls:
        print(f"❌ Max polls ({max_polls}) reached")

if __name__ == "__main__":
    test_complete_flow()
