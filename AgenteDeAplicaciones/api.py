"""
api.py

FastAPI server para Agente de Inventario Consolidado de Aplicaciones
Integra: Repositorios (GitHub, GitLab, Bitbucket, Azure), CMDB, Documentación, Jobs
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import uuid
import json
import threading
import traceback
from pathlib import Path
import logging

# Configurar logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# Importar agentes
from AS_langgraphEnabler import InventoryAgent
from LLMAnalyzer import InventoryAnalyzer

# ============================================================
# CONFIGURACIÓN
# ============================================================

app = FastAPI(
    title="Application Inventory Agent",
    description="Agente para consolidar inventario de aplicaciones desde múltiples fuentes",
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
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Almacén de jobs en memoria
jobs_store: Dict[str, Dict[str, Any]] = {}
agents_store: Dict[str, InventoryAgent] = {}

# ⭐ LOCKS para thread-safety
jobs_lock = threading.Lock()
agents_lock = threading.Lock()

# ============================================================
# MODELOS DE DATOS (Pydantic)
# ============================================================

class InventoryConfig(BaseModel):
    """Configuración del análisis de inventario"""
    # Fuente de repositorios
    source_type: str = Field(default="gitlab", description="gitlab|github|bitbucket|azure")
    source_url: str = Field(description="URL del servidor/organización")
    token: str = Field(description="Token de autenticación")
    
    # Opciones de análisis
    project_path: Optional[str] = Field(default=None, description="Ruta del proyecto específico")
    include_cmdb: Optional[bool] = Field(default=False, description="Incluir datos de CMDB")
    include_documentation: Optional[bool] = Field(default=False, description="Incluir datos de wiki/documentación")
    include_jobs: Optional[bool] = Field(default=False, description="Incluir datos de planificadores de jobs")
    use_ai_analysis: bool = Field(default=True, description="Usar LLM para análisis")
    
    class Config:
        extra = "allow"


class JobStatus(BaseModel):
    """Estado de un job"""
    job_id: str
    status: str
    progress: float
    message: str
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================
# FUNCIONES AUXILIARES (THREAD-SAFE)
# ============================================================

def create_job() -> str:
    """Crea un nuevo job (thread-safe)"""
    job_id = str(uuid.uuid4())
    
    with jobs_lock:
        jobs_store[job_id] = {
            'job_id': job_id,
            'status': 'pending',
            'progress': 0.0,
            'message': 'Job creado',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'result': None,
            'error': None
        }
    
    return job_id


def update_job(job_id: str, status: str = None, progress: float = None,
               message: str = None, result: Dict = None, error: str = None):
    """Actualiza el estado de un job (thread-safe)"""
    with jobs_lock:
        if job_id not in jobs_store:
            return
        
        job = jobs_store[job_id]
        if status:
            job['status'] = status
        if progress is not None:
            job['progress'] = progress
        if message:
            job['message'] = message
        if result is not None:
            job['result'] = result
        if error:
            job['error'] = error
        
        job['updated_at'] = datetime.now().isoformat()


def get_job_safe(job_id: str) -> Optional[Dict]:
    """Obtiene un job de forma thread-safe (copia)"""
    with jobs_lock:
        if job_id not in jobs_store:
            return None
        return dict(jobs_store[job_id])


# ============================================================
# FUNCIÓN DE EJECUCIÓN DE JOBS
# ============================================================

def run_inventory_job(job_id: str, config: InventoryConfig):
    """
    Ejecuta el análisis de inventario en background
    """
    try:
        update_job(job_id, status='running', progress=10, message='Inicializando agente...')
        
        # Crear agente
        agent_config = config.dict()
        logger.info(f"🔍 DEBUG - agent_config type: {type(agent_config)}")
        logger.info(f"🔍 DEBUG - agent_config keys: {list(agent_config.keys())}")
        logger.info(f"🔍 DEBUG - agent_config: {agent_config}")
        
        # Importar InventoryAgent aquí para forzar recarga
        import importlib
        import AS_langgraphEnabler
        importlib.reload(AS_langgraphEnabler)
        from AS_langgraphEnabler import InventoryAgent as IA
        
        agent = IA(agent_config)
        
        with agents_lock:
            agents_store[job_id] = agent
        
        # Ejecutar análisis
        update_job(job_id, progress=20, message='Escaneando repositorios...')
        agent.repositories = agent.scan_repositories()
        
        update_job(job_id, progress=40, message='Extrayendo aplicaciones...')
        agent.applications = agent.extract_applications()
        
        update_job(job_id, progress=60, message='Detectando problemas...')
        agent.detect_issues()
        
        update_job(job_id, progress=80, message='Construyendo catálogo...')
        catalog = agent.build_unified_catalog()
        
        # Generar insights si LLM está disponible
        if config.use_ai_analysis:
            update_job(job_id, progress=85, message='Generando insights con IA...')
            try:
                analyzer = InventoryAnalyzer()
                insights = analyzer.generate_inventory_insights(catalog)
                catalog['ai_insights'] = insights
            except Exception as e:
                logger.warning(f"⚠️ No se pudieron generar insights: {e}")
        
        # Guardar resultados
        update_job(job_id, progress=90, message='Guardando resultados...')
        output_path = OUTPUT_DIR / job_id
        output_path.mkdir(exist_ok=True)
        
        logger.info(f"💾 Guardando en: {output_path}")
        
        catalog_file = output_path / 'inventory_catalog.json'
        with open(catalog_file, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Catálogo guardado en: {catalog_file}")
        
        # Guardar metadatos del job
        job_metadata = {
            'job_id': job_id,
            'config': config.dict(),
            'execution_date': datetime.now().isoformat(),
            'results_summary': {
                'total_applications': len(agent.applications),
                'total_repositories': len(agent.repositories),
                'total_issues': len(agent.issues),
                'health_score': catalog.get('summary', {}).get('health_score', 0)
            }
        }
        
        metadata_file = output_path / 'job_metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(job_metadata, f, ensure_ascii=False, indent=2)
        
        # Completar job
        update_job(
            job_id,
            status='completed',
            progress=100,
            message='Análisis completado exitosamente',
            result={
                'applications_found': len(agent.applications),
                'repositories_found': len(agent.repositories),
                'issues_detected': len(agent.issues),
                'health_score': catalog.get('summary', {}).get('health_score', 0),
                'catalog_file': str(catalog_file),
                'metadata_file': str(metadata_file)
            }
        )
        
        logger.info(f"✅ Job {job_id} completado exitosamente")
    
    except Exception as e:
        logger.error(f"❌ Error en job {job_id}: {e}")
        traceback.print_exc()
        update_job(
            job_id,
            status='failed',
            progress=100,
            error=str(e),
            message=f'Error: {str(e)}'
        )


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Application Inventory Agent",
        "version": "2.0.0",
        "description": "Agente para consolidar inventario de aplicaciones",
        "endpoints": {
            "health": "/health",
            "analyze": "/api/v1/analyze",
            "status": "/api/v1/jobs/{job_id}",
            "files": "/api/v1/jobs/{job_id}/files",
            "download": "/api/v1/download/{job_id}/{filename}"
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Application Inventory Agent"
    }


def detect_source_type_from_url(url: str) -> str:
    """Detecta automáticamente el tipo de fuente desde la URL"""
    if not url:
        return "gitlab"
    
    url_lower = url.lower()
    
    if "gitlab.com" in url_lower or "gitlab" in url_lower:
        return "gitlab"
    elif "github.com" in url_lower or "github" in url_lower:
        return "github"
    elif "dev.azure.com" in url_lower or "visualstudio.com" in url_lower or "azure.com" in url_lower:
        return "azure"
    elif "bitbucket.org" in url_lower or "bitbucket" in url_lower:
        return "bitbucket"
    
    return "gitlab"  # Por defecto


@app.post("/api/v1/analyze")
async def start_analysis(
    config: InventoryConfig,
    background_tasks: BackgroundTasks
):
    """
    Inicia análisis de inventario de aplicaciones
    
    Escanea repositorios y consolida información en catálogo unificado
    """
    
    # Detectar tipo de fuente automáticamente si no se especificó o es el default
    if not config.source_type or config.source_type == "gitlab":
        detected_type = detect_source_type_from_url(config.source_url)
        if detected_type != config.source_type:
            config.source_type = detected_type
            logger.info(f"🔍 Tipo de fuente detectado automáticamente: {detected_type}")
    
    logger.info(f"📨 Solicitud de análisis recibida")
    logger.info(f"   Fuente: {config.source_type}")
    logger.info(f"   URL: {config.source_url}")
    
    # Validaciones
    if not config.source_url:
        raise HTTPException(status_code=400, detail="Debe especificar source_url")
    
    if not config.token:
        raise HTTPException(status_code=400, detail="Debe especificar token")
    
    # Crear job
    job_id = create_job()
    
    logger.info(f"🚀 Iniciando análisis - Job: {job_id}")
    
    # Ejecutar en background
    background_tasks.add_task(run_inventory_job, job_id, config)
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Análisis iniciado en background",
        "polling_url": f"/api/v1/jobs/{job_id}"
    }


@app.get("/api/v1/jobs/{job_id}/analysis")
async def get_job_analysis(job_id: str):
    """Obtiene el análisis completo de un job"""
    logger.info(f"📊 Solicitando análisis para job: {job_id}")
    
    job = get_job_safe(job_id)
    
    # Si el job no está en memoria, verificar si existe el archivo en disco
    if not job:
        metadata_file = OUTPUT_DIR / job_id / 'job_metadata.json'
        if metadata_file.exists():
            logger.info(f"✅ Job encontrado en disco: {job_id}")
            # El job existe en disco, puede estar completado
            job = {
                'job_id': job_id,
                'status': 'completed',
                'progress': 100.0,
                'message': 'Análisis completado (recuperado de disco)'
            }
        else:
            logger.error(f"❌ Job no encontrado: {job_id}")
            raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        logger.warning(f"⚠️ Job no completado. Status: {job['status']}")
        raise HTTPException(status_code=400, detail=f"Job aún no completado. Status: {job['status']}")
    
    # Leer el archivo de catálogo
    output_dir = OUTPUT_DIR / job_id
    catalog_file = output_dir / 'inventory_catalog.json'
    
    logger.info(f"🔍 Buscando catálogo en: {catalog_file}")
    
    if not catalog_file.exists():
        logger.error(f"❌ Archivo no encontrado: {catalog_file}")
        logger.info(f"   OUTPUT_DIR: {OUTPUT_DIR}")
        logger.info(f"   job_id: {job_id}")
        logger.info(f"   output_dir: {output_dir}")
        if output_dir.exists():
            logger.info(f"   Archivos en {output_dir}: {list(output_dir.glob('*'))}")
        raise HTTPException(status_code=404, detail="Archivo de catálogo no encontrado")
    
    try:
        with open(catalog_file, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
        
        logger.info(f"✅ Catálogo cargado: {len(str(catalog))} bytes")
        
        return {
            "job_id": job_id,
            "status": job['status'],
            "inventory": catalog
        }
    except Exception as e:
        logger.error(f"❌ Error leyendo catálogo: {e}")
        raise HTTPException(status_code=500, detail="Error leyendo datos del análisis")


@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Obtiene el estado de un job"""
    job = get_job_safe(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    return JobStatus(**job)


@app.get("/api/v1/jobs/{job_id}/files")
async def list_job_files(job_id: str):
    """Lista archivos generados por un job"""
    job = get_job_safe(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        return {
            "files": [],
            "message": f"Job aún no completado. Status: {job['status']}"
        }
    
    output_dir = OUTPUT_DIR / job_id
    
    if not output_dir.exists():
        return {"files": [], "message": "No se encontraron archivos"}
    
    files = []
    for file_path in output_dir.glob("*.json"):
        files.append({
            "filename": file_path.name,
            "size_kb": round(file_path.stat().st_size / 1024, 2),
            "download_url": f"/api/v1/download/{job_id}/{file_path.name}"
        })
    
    return {
        "job_id": job_id,
        "file_count": len(files),
        "files": files
    }


@app.get("/api/v1/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Descarga un archivo específico de un job"""
    job = get_job_safe(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    file_path = OUTPUT_DIR / job_id / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    # Validar que el archivo está dentro del directorio permitido
    if not str(file_path.resolve()).startswith(str((OUTPUT_DIR / job_id).resolve())):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/json'
    )


@app.get("/api/v1/download/{job_id}")
async def download_all_files(job_id: str):
    """Descarga todos los archivos de un job como ZIP"""
    job = get_job_safe(job_id)
    
    # Si el job no está en memoria, verificar si existe en disco
    if not job:
        metadata_file = OUTPUT_DIR / job_id / 'job_metadata.json'
        if metadata_file.exists():
            job = {'job_id': job_id, 'status': 'completed'}
        else:
            raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job no ha completado")
    
    output_dir = OUTPUT_DIR / job_id
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No se encontraron archivos")
    
    # Crear ZIP en archivo temporal
    import zipfile
    import tempfile
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
            
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in output_dir.glob("*.json"):
                zip_file.write(file_path, arcname=file_path.name)
        
        return FileResponse(
            path=tmp_path,
            media_type="application/zip",
            filename=f"inventory_{job_id}.zip"
        )
    
    except Exception as e:
        logger.error(f"Error creando ZIP: {e}")
        raise HTTPException(status_code=500, detail="Error creando archivo ZIP")


@app.get("/api/v1/jobs")
async def list_jobs():
    """Lista todos los jobs"""
    with jobs_lock:
        jobs_list = list(jobs_store.values())
    
    return {
        "total": len(jobs_list),
        "jobs": jobs_list
    }


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    """Elimina un job y sus archivos"""
    job = get_job_safe(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    # Eliminar archivos
    output_dir = OUTPUT_DIR / job_id
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    
    # Eliminar del almacén
    with jobs_lock:
        if job_id in jobs_store:
            del jobs_store[job_id]
    
    with agents_lock:
        if job_id in agents_store:
            del agents_store[job_id]
    
    return {"message": "Job eliminado", "job_id": job_id}


# ============================================================
# LLM ANALYSIS ENDPOINTS
# ============================================================

@app.post("/api/v1/jobs/{job_id}/llm/{analysis_type}")
async def perform_llm_analysis(job_id: str, analysis_type: str):
    """Realiza análisis LLM sobre los resultados de un job"""
    from LLMAnalyzer import LLMAnalyzer
    
    job = get_job_safe(job_id)
    
    # Verificar si existe en disco
    if not job:
        metadata_file = OUTPUT_DIR / job_id / 'job_metadata.json'
        if metadata_file.exists():
            job = {'job_id': job_id, 'status': 'completed'}
        else:
            raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job no ha completado")
    
    # Obtener catálogo guardado (usar inventory_catalog.json en lugar de inventory_analysis.json)
    catalog_file = OUTPUT_DIR / job_id / 'inventory_catalog.json'
    if not catalog_file.exists():
        logger.error(f"❌ Archivo de catálogo no encontrado: {catalog_file}")
        raise HTTPException(status_code=404, detail="No se encontró catálogo para este job")
    
    with open(catalog_file, 'r', encoding='utf-8') as f:
        inventory_analysis = json.load(f)
    
    try:
        llm_analyzer = LLMAnalyzer()
        
        # Mapear tipos de análisis a prompts
        analysis_prompts = {
            'health': f"""Analiza la salud general de estas aplicaciones basándote en el catálogo:
            
{json.dumps(inventory_analysis, indent=2)}

Proporciona un resumen executivo sobre el estado de salud, métricas clave y recomendaciones prioritarias.""",
            
            'duplicates': f"""Identifica y analiza aplicaciones duplicadas o redundantes en este catálogo:

{json.dumps(inventory_analysis, indent=2)}

Explica cuáles son similares, por qué podrían consolidarse y el impacto de hacerlo.""",
            
            'orphans': f"""Encuentra y analiza aplicaciones huérfanas (sin mantenimiento activo) en:

{json.dumps(inventory_analysis, indent=2)}

Explica cuáles parecen abandonadas y qué acciones se deberían tomar.""",
            
            'dependencies': f"""Analiza las dependencias entre aplicaciones y repositorios:

{json.dumps(inventory_analysis, indent=2)}

Identifica dependencias críticas, acoplamiento y puntos de falla.""",
            
            'recommendations': f"""Proporciona recomendaciones estratégicas para mejorar el portafolio de aplicaciones:

{json.dumps(inventory_analysis, indent=2)}

Incluye priorización, riesgos mitigados y beneficios esperados.""",
            
            'consolidation': f"""Analiza oportunidades de consolidación y modernización:

{json.dumps(inventory_analysis, indent=2)}

Identifica qué aplicaciones podrían consolidarse, obsoletas que deberían retirarse y tecnologías que merecen upgrade."""
        }
        
        if analysis_type not in analysis_prompts:
            raise HTTPException(status_code=400, detail=f"Tipo de análisis no válido: {analysis_type}")
        
        prompt = analysis_prompts[analysis_type]
        
        # Usar el nuevo método que acepta prompts directamente
        if hasattr(llm_analyzer, 'analyze_with_prompt'):
            analysis_result = llm_analyzer.analyze_with_prompt(prompt)
        else:
            # Fallback: usar el catálogo directamente
            analysis_result = llm_analyzer.generate_inventory_insights(inventory_analysis)
            analysis_result = json.dumps(analysis_result, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "analysis_type": analysis_type,
            "analysis": analysis_result
        }
    
    except Exception as e:
        logger.error(f"Error en LLM análisis: {e}")
        raise HTTPException(status_code=500, detail=f"Error en análisis LLM: {str(e)}")


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handler para excepciones HTTP"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
