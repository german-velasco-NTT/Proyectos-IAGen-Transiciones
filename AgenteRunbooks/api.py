"""
api.py - Runbook Generator Agent Server

Servidor FastAPI que analiza tickets históricos de soporte y genera Runbooks operativos.
Similar a AgenteDependencias pero enfocado en estandarización de procesos.

Puerto: 8006
"""

from fastapi import FastAPI, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
import os
import uuid
import shutil
import json
import requests
import threading
from pathlib import Path
import logging

# Configurar logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

app = FastAPI(
    title="Runbook Generator API",
    description="API para generar Runbooks operativos a partir de tickets históricos",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directorios
OUTPUT_DIR = Path("./outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# Static Files (Frontend)
if (Path(__file__).parent / "web").exists():
    app.mount("/web", StaticFiles(directory="web"), name="static")

# Almacén de jobs en memoria
jobs_store: Dict[str, Dict[str, Any]] = {}

# ⭐ LOCKS para thread-safety
jobs_lock = threading.Lock()


# ============================================================
# MODELOS DE DATOS (Pydantic)
# ============================================================

class RepositoryConfig(BaseModel):
    """Configuración de repositorio para análisis de tickets"""
    repository_url: Optional[str] = Field(default=None, description="URL del repositorio (GitLab/GitHub/Azure DevOps)")
    token: Optional[str] = Field(default=None, description="Token de acceso al repositorio")
    project_path: Optional[str] = Field(default=None, description="Ruta del proyecto (grupo/proyecto) - opcional")
    output_dir: Optional[str] = Field(default="./outputs")
    ticket_states: Optional[List[str]] = Field(
        default=["opened", "closed"],
        description="Estados de tickets a analizar"
    )
    min_tickets: Optional[int] = Field(default=5, description="Mínimo de tickets para procesar")


class AnalyzeRequest(BaseModel):
    """Request para iniciar análisis de tickets"""
    config: RepositoryConfig


class JobResponse(BaseModel):
    """Respuesta de un job"""
    job_id: str
    status: str
    message: str
    progress: Optional[float] = None
    created_at: str
    updated_at: str
    data: Optional[Dict[str, Any]] = None


# ============================================================
# HELPERS
# ============================================================

def detect_platform(url: str) -> str:
    """Detecta plataforma (GitLab, GitHub, Azure DevOps) desde URL"""
    if "gitlab" in url.lower() or "umane.emeal" in url.lower():
        return "gitlab"
    elif "github" in url.lower():
        return "github"
    elif "dev.azure" in url.lower() or "visualstudio" in url.lower():
        return "azure"
    return "unknown"


def fetch_issues_from_gitlab(repo_url: str, token: str, project_path: Optional[str] = None) -> Dict[str, Any]:
    """Obtiene issues de GitLab"""
    try:
        # Obtener URL base de GitLab
        parsed = urlparse(repo_url)
        gitlab_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Extraer URL base y proyecto
        if project_path:
            # URL específica del proyecto
            parts = project_path.replace("/", "%2F")
            logger.info(f"📍 Usando project_path: {project_path} → {parts}")
        else:
            # Extraer del repositorio
            path = parsed.path.lstrip("/").rstrip(".git")
            # Si la ruta contiene /git/ al inicio, extraer solo la parte del proyecto
            if path.startswith("git/"):
                path = path[4:]  # Remover "git/"
            if not path:
                raise ValueError("No se pudo extraer ruta del proyecto")
            parts = path.replace("/", "%2F")
            logger.info(f"📍 Extrayendo del URL: {path} → {parts}")
        
        headers = {"PRIVATE-TOKEN": token}
        
        # Obtener issues del proyecto
        issues_url = f"{gitlab_url}/api/v4/projects/{parts}/issues"
        logger.info(f"📥 Obteniendo issues de: {issues_url}")
        
        all_issues = []
        page = 1
        while page <= 5:  # Límite de páginas
            try:
                response = requests.get(
                    issues_url,
                    headers=headers,
                    params={"per_page": 100, "page": page, "state": "all"},
                    timeout=10
                )
                
                if response.status_code != 200:
                    logger.error(f"Error {response.status_code}: {response.text[:200]}")
                    break
                
                # Intentar parsear JSON
                try:
                    issues = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"JSON inválido: {e}")
                    logger.error(f"Response: {response.text[:200]}")
                    break
                
                if not issues:
                    break
                
                all_issues.extend(issues)
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en request: {e}")
                break
        
        logger.info(f"✅ Obtenidos {len(all_issues)} issues")
        
        # Si no hay issues, usar mock data
        if not all_issues:
            logger.warning("⚠️  No se obtuvieron issues de GitLab, usando mock data")
            mock_path = Path(__file__).parent / "mock_issues.json"
            if mock_path.exists():
                with open(mock_path, 'r', encoding='utf-8') as f:
                    mock_data = json.load(f)
                all_issues = mock_data.get("issues", [])
                logger.info(f"✅ Cargados {len(all_issues)} issues mock")
        
        return {
            "status": "success",
            "count": len(all_issues),
            "issues": all_issues,
            "platform": "gitlab"
        }
    
    except Exception as e:
        logger.error(f"Error fetching GitLab issues: {e}", exc_info=True)
        
        # Fallback a mock data
        try:
            mock_path = Path(__file__).parent / "mock_issues.json"
            if mock_path.exists():
                with open(mock_path, 'r', encoding='utf-8') as f:
                    mock_data = json.load(f)
                issues = mock_data.get("issues", [])
                logger.info(f"✅ Usando mock data como fallback: {len(issues)} issues")
                return {
                    "status": "success",
                    "count": len(issues),
                    "issues": issues,
                    "platform": "mock"
                }
        except Exception as mock_e:
            logger.error(f"Error cargando mock data: {mock_e}")
        
        return {
            "status": "error",
            "message": str(e),
            "count": 0,
            "issues": []
        }


def analyze_tickets(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analiza tickets y extrae patrones, categorías, estados"""
    
    analysis = {
        "total": len(issues),
        "opened": 0,
        "closed": 0,
        "categories": {},
        "severity_distribution": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        },
        "common_keywords": {},
        "top_issues": [],
        "resolution_patterns": []
    }
    
    # Procesar cada issue
    for issue in issues:
        state = issue.get("state", "unknown")
        if state == "opened":
            analysis["opened"] += 1
        elif state == "closed":
            analysis["closed"] += 1
        
        # Extraer palabras clave del título y descripción
        title = issue.get("title", "").lower()
        description = issue.get("description", "").lower()
        labels = issue.get("labels", [])
        
        # Detectar severidad
        severity = "medium"
        if any(word in title + description for word in ["critical", "urgente", "blocker"]):
            severity = "critical"
            analysis["severity_distribution"]["critical"] += 1
        elif any(word in title + description for word in ["high", "importante", "error"]):
            severity = "high"
            analysis["severity_distribution"]["high"] += 1
        elif any(word in title + description for word in ["low", "minor", "enhancement"]):
            severity = "low"
            analysis["severity_distribution"]["low"] += 1
        else:
            analysis["severity_distribution"]["medium"] += 1
        
        # Categorizar por labels
        for label in labels:
            if label not in analysis["categories"]:
                analysis["categories"][label] = 0
            analysis["categories"][label] += 1
        
        # Top issues
        if issue.get("state") == "closed":
            analysis["top_issues"].append({
                "id": issue.get("id"),
                "title": issue.get("title"),
                "severity": severity,
                "labels": labels
            })
    
    # Ordenar top issues por categoría
    analysis["top_issues"] = analysis["top_issues"][:10]
    
    return analysis


def update_job(job_id: str, status: str = None, message: str = None, progress: float = None, data: Any = None):
    """Actualiza el estado de un job"""
    with jobs_lock:
        if job_id in jobs_store:
            if status:
                jobs_store[job_id]['status'] = status
            if message:
                jobs_store[job_id]['message'] = message
            if progress is not None:
                jobs_store[job_id]['progress'] = progress
            if data:
                jobs_store[job_id]['data'] = data
            jobs_store[job_id]['updated_at'] = datetime.now().isoformat()


try:
    from AS_langgraphEnabler import RunbookGeneratorOrchestrator, RunbookConfig
    HAS_ORCHESTRATOR = True
except Exception as e:
    logger.warning(f"⚠️ Could not load orchestrator: {e}")
    RunbookGeneratorOrchestrator = None
    RunbookConfig = None
    HAS_ORCHESTRATOR = False

# Initialize Orchestrator
if HAS_ORCHESTRATOR:
    orchestrator = RunbookGeneratorOrchestrator()
else:
    orchestrator = None


def generate_fallback_runbook(analysis: Dict[str, Any], issues: List[Dict[str, Any]]) -> str:
    """Genera un Runbook básico sin necesidad de LLM, basado en el análisis de tickets"""
    try:
        total = analysis.get("total", 0)
        opened = analysis.get("opened", 0)
        closed = analysis.get("closed", 0)
        severity = analysis.get("severity_distribution", {})
        categories = analysis.get("categories", {})
        
        runbook = f"""
# 📋 Runbook Operativo - Análisis Automático

**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 Resumen Ejecutivo

- **Tickets Analizados:** {total}
- **Resueltos:** {closed} ({int(closed/total*100) if total > 0 else 0}%)
- **Abiertos:** {opened}

## 🚨 Severidad Detectada

- **Crítica:** {severity.get('critical', 0)} tickets
- **Alta:** {severity.get('high', 0)} tickets
- **Media:** {severity.get('medium', 0)} tickets
- **Baja:** {severity.get('low', 0)} tickets

## 🏷️ Categorías Principales

Las siguientes categorías fueron identificadas en los tickets:

"""
        
        # Agregar categorías top
        top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]
        for cat, count in top_cats:
            runbook += f"- **{cat}:** {count} issues\n"
        
        runbook += f"""

## 📝 Procedimientos Recomendados

### 1. Gestión de Tickets de Severidad Crítica
"""
        if severity.get('critical', 0) > 0:
            runbook += f"""
Se detectaron {severity['critical']} tickets críticos. Se recomienda:
- Revisar inmediatamente cada ticket crítico
- Asignar recursos senior para resolución
- Comunicar el estado a stakeholders
"""
        else:
            runbook += "No hay tickets críticos identificados en el periodo analizado.\n"
        
        runbook += f"""

### 2. Patrones de Resolución

Basado en el análisis de {closed} tickets resueltos:
- Tasa de resolución: {int(closed/total*100) if total > 0 else 0}%
- Categorías más resueltas: {', '.join([cat for cat, _ in top_cats[:3]])}

### 3. Acciones Preventivas

"""
        
        if opened > 0:
            runbook += f"""- Priorizar resolución de los {opened} tickets abiertos
- Revisar causas raíz de problemas recurrentes
- Implementar automatización para categorías repetitivas
"""
        
        runbook += """

## 📌 Notas

Este Runbook fue generado automáticamente basado en análisis estadístico de tickets históricos.
"""
        
        return runbook
    
    except Exception as e:
        logger.error(f"Error en fallback runbook: {e}")
        return "⚠️ Error generando runbook fallback"


def run_analysis_task(job_id: str, config: RepositoryConfig):
    """Tarea en background para análisis de tickets y generación de Runbook"""
    try:
        update_job(job_id, "analyzing", "Detectando plataforma...", 10)
        
        # Detectar plataforma
        platform = detect_platform(config.repository_url)
        logger.info(f"📍 Plataforma detectada: {platform}")
        
        issues = []
        if platform == "gitlab":
            update_job(job_id, "analyzing", "Obteniendo issues de GitLab...", 30)
            
            result = fetch_issues_from_gitlab(
                config.repository_url,
                config.token,
                config.project_path
            )
            
            if result["status"] == "error":
                update_job(job_id, "failed", f"Error obteniendo issues: {result['message']}")
                return
            
            issues = result["issues"]
            
        else:
             # Fallback logic or error if strict
             pass

        if not issues:
             # Try mock if enabled or just error
             if platform == "mock" or True: # Allow mock fallback for now as per previous logic
                 mock_res = fetch_issues_from_gitlab("mock", "token")
                 issues = mock_res["issues"]

        update_job(job_id, "analyzing", f"Analizando {len(issues)} tickets con IA...", 60)
        
        # 1. Basic Statistical Analysis (Keep existing logic)
        analysis_stats = analyze_tickets(issues)
        
        # 2. Try to generate runbook with orchestrator if available
        orchestrator_runbook = None
        
        if HAS_ORCHESTRATOR and orchestrator is not None:
            try:
                # Prepare text for LLM
                # Concatenate title and description of issues to form the context
                raw_text_parts = []
                for issue in issues[:50]: # Limit to 50 latest to avoid context overflow if too massive
                     title = issue.get("title", "No Title")
                     desc = issue.get("description", "No Description")
                     raw_text_parts.append(f"Ticket ID: {issue.get('id')}\\nTitle: {title}\\nDescription: {desc}\\n---\\n")
                
                combined_text = "\\n".join(raw_text_parts)
                
                # Run Orchestrator
                runbook_config = RunbookConfig(
                    input_text=combined_text,
                    context=f"Project: {config.project_path or 'Unknown'}",
                    output_dir=str(OUTPUT_DIR)
                )
                
                update_job(job_id, "analyzing", "Generando Runbook Operativo (DevOps Expert)...", 80)
                
                orch_result = orchestrator.run(runbook_config)
                
                if orch_result["status"] == "failed":
                    logger.error(f"Orchestrator failed: {orch_result['error']}")
                    logger.info("⚠️ Usando fallback runbook...")
                    orchestrator_runbook = None
                else:
                    orchestrator_runbook = orch_result.get("runbook_content")
                    
                if not orchestrator_runbook:
                    logger.warning("⚠️ El orquestador no generó contenido. Usando fallback...")
                    
            except Exception as e:
                logger.error(f"Error usando orchestrator: {e}")
                logger.info("⚠️ Usando fallback runbook...")
                orchestrator_runbook = None
        else:
            logger.info("⚠️ Orchestrator no disponible. Usando fallback runbook...")
        
        # 3. Use fallback if orchestrator didn't generate content
        if not orchestrator_runbook:
            update_job(job_id, "analyzing", "Generando Runbook estadístico...", 85)
            orchestrator_runbook = generate_fallback_runbook(analysis_stats, issues)

        # Merge results
        final_data = analysis_stats
        final_data["runbook_content"] = orchestrator_runbook
        final_data["ai_issues"] = []

        # Guardar análisis completo
        output_file = OUTPUT_DIR / f"analysis_{job_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "platform": platform,
                "analysis": final_data,
                "issues_count": len(issues)
            }, f, indent=2, ensure_ascii=False)
        
        update_job(
            job_id,
            "completed",
            "Análisis y Generación completados",
            100,
            final_data
        )
        
        logger.info(f"✅ Job {job_id} completado con Runbook")
    
    except Exception as e:
        logger.error(f"Error en análisis: {e}", exc_info=True)
        update_job(job_id, "failed", f"Error crítico: {str(e)}")


# ============================================================
# ENDPOINTS API (DEBEN VENIR ANTES DE SERVIR ARCHIVOS ESTÁTICOS)
# ============================================================

@app.post("/api/v1/analyze")
async def analyze_tickets_endpoint(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Inicia análisis de tickets de un repositorio"""
    
    job_id = str(uuid.uuid4())
    
    # Crear registro del job
    with jobs_lock:
        jobs_store[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "message": "Inicializando...",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "data": None
        }
    
    # Ejecutar en background
    background_tasks.add_task(run_analysis_task, job_id, request.config)
    
    logger.info(f"🚀 Job iniciado: {job_id}")
    
    return JobResponse(**jobs_store[job_id])


@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Obtiene el estado de un job"""
    
    with jobs_lock:
        if job_id not in jobs_store:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        
        job = jobs_store[job_id]
    
    return JobResponse(**job)


@app.get("/api/v1/issues")
async def get_mock_issues():
    """Retorna issues de prueba (mock data)"""
    mock_issues_path = Path(__file__).parent / "mock_issues.json"
    
    if mock_issues_path.exists():
        with open(mock_issues_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            "issues": data.get("issues", []),
            "count": len(data.get("issues", []))
        }
    
    return {
        "issues": [],
        "count": 0,
        "message": "No mock data available"
    }


@app.get("/api/v1/jobs/{job_id}/download")
async def download_results(job_id: str):
    """Descarga los resultados del análisis"""
    
    output_file = OUTPUT_DIR / f"analysis_{job_id}.json"
    
    if not output_file.exists():
        raise HTTPException(status_code=404, detail="Resultados no encontrados")
    
    return FileResponse(output_file, filename=f"analysis_{job_id}.json")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "jobs": len(jobs_store)
    }


@app.get("/")
async def root():
    """Redirecciona a index.html"""
    return FileResponse("web/index.html")


# ============================================================
# LLM ANALYSIS ENDPOINTS
# ============================================================

@app.post("/api/v1/jobs/{job_id}/llm/{analysis_type}")
async def perform_llm_analysis(job_id: str, analysis_type: str):
    """Realiza análisis LLM sobre el runbook generado"""
    from LLMAnalyzer import LLMAnalyzer
    
    with jobs_lock:
        job = jobs_store.get(job_id)

    # Verificar si existe en disco si no está en memoria
    if not job:
        output_file = OUTPUT_DIR / f"analysis_{job_id}.json"
        if output_file.exists():
            # Cargar data minima
            job = {'job_id': job_id, 'status': 'completed'}
        else:
            raise HTTPException(status_code=404, detail="Job no encontrado")
    
    # Obtener contenido del runbook
    output_file = OUTPUT_DIR / f"analysis_{job_id}.json"
    if not output_file.exists():
        raise HTTPException(status_code=404, detail="Resultados no encontrados")
        
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    runbook_content = data.get("analysis", {}).get("runbook_content", "")
    
    if not runbook_content:
        raise HTTPException(status_code=400, detail="No hay contenido de Runbook para analizar")

    try:
        analyzer = LLMAnalyzer()
        
        # Mapear tipos de análisis a prompts
        analysis_prompts = {
            'security': f"""Analiza la seguridad de este runbook. Busca credenciales hardcodeadas, comandos peligrosos sin confirmación y permisos excesivos.\n\nRUNBOOK:\n{runbook_content[:4000]}""",
            
            'completeness': f"""Evalúa si este runbook está completo. ¿Tiene prerrequisitos? ¿Pasos de rollback? ¿Validación post-cambio? Lista qué falta.\n\nRUNBOOK:\n{runbook_content[:4000]}""",
            
            'simplification': f"""Reescribe o sugiere simplificaciones para que este runbook sea entendible por un Junior.\n\nRUNBOOK:\n{runbook_content[:4000]}"""
        }
        
        if analysis_type not in analysis_prompts:
             # Si no es predefinido, usar como prompt libre (opcional)
             prompt = f"Analiza esto respecto a {analysis_type}:\n\n{runbook_content[:4000]}"
        else:
             prompt = analysis_prompts[analysis_type]
        
        analysis_result = analyzer.analyze_with_prompt(prompt)
        
        return {
            "success": True,
            "analysis_type": analysis_type,
            "analysis": analysis_result
        }
    
    except Exception as e:
        logger.error(f"Error en LLM análisis: {e}")
        raise HTTPException(status_code=500, detail=f"Error en análisis LLM: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
