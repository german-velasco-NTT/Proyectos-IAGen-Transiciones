"""
api.py

FastAPI server para el agente de análisis de APIs en repositorios (GitLab, GitHub, Azure DevOps)
Compatible con AS_langgraphEnabler.py (API Analysis Edition)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import uuid
import shutil
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
 
# Importar el orquestador
from AS_langgraphEnabler import RepositoryAgent

# ============================================================
# CONFIGURACIÓN
# ============================================================

app = FastAPI(
    title="API Contract & Topology Analysis Agent",
    description="Agente para análisis de especificaciones API, contratos y mapeo de topología en repositorios",
    version="1.0.0"
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

# Almacén de jobs en memoria
jobs_store: Dict[str, Dict[str, Any]] = {}
orchestrators_store: Dict[str, RepositoryAgent] = {}

# ⭐ LOCKS para thread-safety
jobs_lock = threading.Lock()
orchestrators_lock = threading.Lock()

# ============================================================
# MODELOS DE DATOS (Pydantic)
# ============================================================

class AnalysisConfig(BaseModel):
    """Configuración del análisis de APIs"""
    gitlab_url: Optional[str] = None
    repository_url: Optional[str] = None
    gitlab_token: Optional[str] = None
    token: Optional[str] = None
    project_path: Optional[str] = None
    group_path: Optional[str] = None
    auto_discover_groups: Optional[bool] = False
    analysis_mode: str = "full"
    use_ai_analysis: bool = True
    active_days: Optional[int] = 30
    stale_days: Optional[int] = 90
    
    class Config:
        extra = "allow"  # Permitir campos adicionales
    
    def get_url(self):
        """Obtener URL normalizada"""
        return self.gitlab_url or self.repository_url
    
    def get_token(self):
        """Obtener token normalizado"""
        return self.gitlab_token or self.token


class GenerateRequest(BaseModel):
    """Request para generar código"""
    analyzeInfo: AnalysisConfig
    
    # Autenticación con Bearer Token para Axet
    bearer_token: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_api_version: Optional[str] = "2024-02-15-preview"
    axet_user_id: Optional[str] = None  # ⭐ NUEVO
    asset_id: Optional[str] = None


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
        # Devolver una COPIA para evitar modificaciones externas
        return dict(jobs_store[job_id])


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "API Contract & Topology Analysis Agent",
        "version": "1.0.0",
        "description": "Agente para análisis de especificaciones API, contratos y mapeo de topología en repositorios",
        "endpoints": {
            "health": "/health",
            "analyze": "/api/v1/analyze",
            "status": "/api/v1/jobs/{job_id}",
            "analysis": "/api/v1/jobs/{job_id}/analysis",
            "files": "/api/v1/jobs/{job_id}/files",
            "download": "/api/v1/download/{job_id}/{filename}",
            "download_all": "/api/v1/download/{job_id}"
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/analyze")
async def start_analysis(
    req: AnalysisConfig,
    background_tasks: BackgroundTasks
):
    """
    Inicia análisis de APIs en repositorios (GitLab, GitHub, Azure DevOps).
    
    Escanea especificaciones (OpenAPI 3.0, Swagger 2.0, WSDL, RAML) y código fuente
    para detectar APIs implementadas, construir topología de dependencias y generar
    documentación normalizada de contratos.
    """
    logger.info(f"Requ: {req}")
    config = req
    url = config.get_url()
    token = config.get_token()
    
    logger.info(f"📨 Solicitud recibida. URL: {url}, Token: {'***' if token else 'VACIO'}")
    logger.info(f"   Datos: {config.dict()}")
    
    # Validar que tenemos URL y token
    if not url:
        logger.error(f"❌ URL vacía")
        raise HTTPException(
            status_code=400,
            detail="Debe especificar gitlab_url o repository_url"
        )
    
    if not token:
        logger.error(f"❌ Token vacío")
        raise HTTPException(
            status_code=400,
            detail="Debe especificar gitlab_token o token"
        )
    
    # Validar configuración
    if not config.project_path and not config.group_path and not config.auto_discover_groups:
        raise HTTPException(
            status_code=400,
            detail="Debe especificar project_path, group_path o auto_discover_groups"
        )
    
    # Crear job
    job_id = create_job()
    
    logger.info(f"🚀 Iniciando análisis de APIs - Job: {job_id}")
    logger.info(f"   GitLab URL: {config.get_url()}")
    if config.project_path:
        logger.info(f"   Proyecto: {config.project_path}")
    if config.group_path:
        logger.info(f"   Grupo: {config.group_path}")
    logger.info(f"   Modo: {config.analysis_mode}")
    logger.info(f"   Análisis IA: {config.use_ai_analysis}")
    
    # Ejecutar en background
    background_tasks.add_task(
        run_analysis_job,
        job_id,
        config,
        req  # Pasar el request completo para acceso a configuración Azure
    )
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": "Análisis iniciado en background"
    }


@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Obtiene el estado de un job"""
    logger.info(f"📊 Solicitando status para job: {job_id}")
    logger.info(f"   Jobs almacenados: {list(jobs_store.keys())}")
    
    job = get_job_safe(job_id)
    
    if not job:
        logger.error(f"❌ Job no encontrado: {job_id}")
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    logger.info(f"✅ Job encontrado. Status: {job['status']}, Progress: {job['progress']}")
    return JobStatus(**job)


@app.get("/api/v1/jobs/{job_id}/files")
async def list_job_files(job_id: str):
    """Lista archivos generados por un job"""
    job = get_job_safe(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        return {"files": [], "message": "Job aún no completado"}
    
    output_dir = OUTPUT_DIR / job_id
    
    if not output_dir.exists():
        return {"files": [], "message": "No se encontraron archivos"}
    
    files = []
    for file_path in output_dir.glob("*.json"):
        files.append({
            "filename": file_path.name,
            "size": file_path.stat().st_size,
            "size_kb": round(file_path.stat().st_size / 1024, 2),
            "download_url": f"/api/v1/download/{job_id}/{file_path.name}"
        })
    
    return {
        "job_id": job_id,
        "file_count": len(files),
        "files": files
    }


@app.get("/api/v1/jobs/{job_id}/summary")
async def get_job_summary(job_id: str):
    """Obtiene un RESUMEN rápido del análisis (sin datos masivos)"""
    job = get_job_safe(job_id)
    
    output_dir = OUTPUT_DIR / job_id
    if not job and output_dir.exists():
        job = {
            'job_id': job_id,
            'status': 'completed',
            'created_at': 'unknown',
            'result': {}
        }
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job aún no completado")
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Archivos no encontrados")
    
    # 🔥 Resumen RÁPIDO sin cargar los catálogos enormes
    summary = {
        "job_id": job_id,
        "status": job['status'],
        "api_summary": {
            "total_specs": 0,
            "total_code_apis": 0,
            "total_endpoints": 0,
            "api_types": {"rest": 0, "soap": 0, "raml": 0, "graphql": 0}
        }
    }
    
    try:
        # Solo leer los metadatos, no los datos masivos
        catalog_file = output_dir / "catalogo_apis_completo.json"
        if catalog_file.exists():
            with open(catalog_file, 'r', encoding='utf-8') as f:
                # Leer solo las primeras líneas para metadata
                content = json.load(f)
                summary["api_summary"]["total_specs"] = content.get("total_specs", 0)
                summary["api_summary"]["total_code_apis"] = content.get("total_code_files", 0)
                summary["api_summary"]["total_endpoints"] = content.get("total_endpoints", 0)
        
        topology_file = output_dir / "topologia_apis.json"
        if topology_file.exists():
            with open(topology_file, 'r', encoding='utf-8') as f:
                topology = json.load(f)
                api_types = topology.get("api_types", {})
                summary["api_summary"]["api_types"].update(api_types)
    except Exception as e:
        logger.error(f"❌ Error procesando resumen del job {job_id}: {e}")
    
    return summary


@app.get("/api/v1/jobs/{job_id}/analysis")
async def get_job_analysis(job_id: str):
    """Obtiene el análisis completo de APIs de un job (datos masivos)"""
    job = get_job_safe(job_id)
    
    # Si el job no está en memoria pero existen archivos en disco, lo reconstruimos
    output_dir = OUTPUT_DIR / job_id
    logger.info(f"📂 Buscando job {job_id} en disco: {output_dir}")
    
    if not job and output_dir.exists():
        logger.info(f"✅ Encontrado en disco, reconstruyendo...")
        # Reconstruir el job desde los archivos en disco
        job = {
            'job_id': job_id,
            'status': 'completed',
            'created_at': 'unknown',
            'result': {}
        }
    
    if not job:
        logger.error(f"❌ Job no encontrado: {job_id}")
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job aún no completado")
    
    output_dir = OUTPUT_DIR / job_id
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Archivos no encontrados")
    
    # Estructura de datos para APIs
    analysis_data = {
        "api_summary": {
            "total_specs": 0,
            "total_code_apis": 0,
            "total_endpoints": 0,
            "api_types": {
                "rest": 0,
                "soap": 0,
                "raml": 0,
                "graphql": 0
            }
        },
        "specs": [],
        "code_apis": [],
        "topology": {}
    }
    
    try:
        # Leer catálogo completo de APIs
        catalog_file = output_dir / "catalogo_apis_completo.json"
        if catalog_file.exists():
            with open(catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            
            analysis_data["specs"] = catalog.get("specs", [])
            analysis_data["code_apis"] = catalog.get("code_apis", [])
            analysis_data["api_summary"]["total_specs"] = catalog.get("total_specs", 0)
            analysis_data["api_summary"]["total_code_apis"] = catalog.get("total_code_files", 0)
            analysis_data["api_summary"]["total_endpoints"] = catalog.get("total_endpoints", 0)
        
        # Leer topología
        topology_file = output_dir / "topologia_apis.json"
        if topology_file.exists():
            with open(topology_file, 'r', encoding='utf-8') as f:
                topology = json.load(f)
            
            analysis_data["topology"] = topology
            api_types = topology.get("api_types", {})
            analysis_data["api_summary"]["api_types"].update(api_types)
        
        # Leer resumen ejecutivo
        resumen_file = output_dir / "resumen_ejecutivo.json"
        if resumen_file.exists():
            with open(resumen_file, 'r', encoding='utf-8') as f:
                resumen = json.load(f)
            # El resumen ya contiene información adicional
        
    except Exception as e:
        logger.error(f"❌ Error procesando análisis del job {job_id}: {e}")
        logger.error(traceback.format_exc())
    
    # Estructura final que espera el frontend
    response = {
        "job_id": job_id,
        "status": job['status'],
        "analysis_data": analysis_data,
        "result": job.get('result', {})
    }
    
    return response


@app.get("/api/v1/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Descarga un archivo específico de resultado"""
    job = get_job_safe(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job no completado")
    
    # Buscar archivo en el directorio de salida del job
    output_dir = OUTPUT_DIR / job_id
    file_path = output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/json'
    )


@app.get("/api/v1/download/{job_id}")
async def download_all_results(job_id: str, background_tasks: BackgroundTasks):
    """Descarga todos los resultados de un job como ZIP"""
    job = get_job_safe(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job no completado")
    
    output_dir = OUTPUT_DIR / job_id
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Archivos no encontrados")
    
    # Crear ZIP
    zip_path = OUTPUT_DIR / f"{job_id}.zip"
    shutil.make_archive(str(OUTPUT_DIR / job_id), 'zip', output_dir)
    
    # Opcional: Limpiar ZIP después de enviarlo
    def cleanup_zip():
        if zip_path.exists():
            os.remove(zip_path)
    
    background_tasks.add_task(cleanup_zip)
    
    return FileResponse(
        path=zip_path,
        filename=f"api_analysis_{job_id}.zip",
        media_type="application/zip"
    )


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    """Elimina un job y sus archivos (thread-safe)"""
    with jobs_lock:
        if job_id not in jobs_store:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        del jobs_store[job_id]
    
    # Eliminar orquestador
    with orchestrators_lock:
        if job_id in orchestrators_store:
            del orchestrators_store[job_id]
    
    # Eliminar archivos (fuera del lock)
    output_dir = OUTPUT_DIR / job_id
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    zip_path = OUTPUT_DIR / f"{job_id}.zip"
    if zip_path.exists():
        os.remove(zip_path)
    
    return {"message": "Job eliminado correctamente"}


# ============================================================
# ENDPOINT PARA SERVIR JSON DIRECTAMENTE (para dashboard)
# ============================================================

@app.get("/api/v1/jobs/{job_id}/files/{filename}")
async def get_job_file(job_id: str, filename: str):
    """
    Retorna un archivo JSON específico como JSON (no descarga)
    Usado por el dashboard para consumir catálogo y topología
    """
    try:
        # Validar que el archivo tenga extensión .json
        if not filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos JSON")
        
        # Validar nombre de archivo (prevenir path traversal)
        if '..' in filename or '/' in filename:
            raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
        
        file_path = OUTPUT_DIR / job_id / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {filename}")
        
        # Leer y retornar el JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Retornar con headers que desactivan caché
        return JSONResponse(
            content=data,
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
    
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error decodificando JSON")
    except Exception as e:
        logger.error(f"Error sirviendo archivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# LÓGICA DE PROCESAMIENTO
# ============================================================

def run_analysis_job(job_id: str, config: AnalysisConfig, azure_config: Optional[GenerateRequest] = None):
    """
    Ejecuta el análisis de APIs (función principal).
    ⭐ Actualiza progreso en tiempo real.
    """
    
    try:
        logger.info(f"📊 Iniciando análisis para job {job_id}")
        
        # ═══════════════════════════════════════════════════════════════
        # 1. INICIALIZACIÓN
        # ═══════════════════════════════════════════════════════════════
        
        # Crear directorio de salida para este job
        output_dir = OUTPUT_DIR / job_id
        output_dir.mkdir(exist_ok=True)
        
        update_job(
            job_id,
            status="processing",
            progress=0.05,
            message="Inicializando análisis de APIs...",
            result={
                "current_stage": "init",
                "specs_found": 0,
                "code_apis_found": 0,
                "total_endpoints": 0
            }
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 2. CREAR ORQUESTADOR
        # ═══════════════════════════════════════════════════════════════
        
        logger.info(f"🔧 Creando orquestador para job {job_id}")
        
        # Usar project_path del config o cargar desde .env
        project_path = config.project_path or os.getenv('PROJECT_PATH')
        group_path = config.group_path or os.getenv('GROUP_PATH')
        
        agent_config = {
            'url': config.get_url(),
            'token': config.get_token(),
            'project_path': project_path,
            'group_path': group_path,
            'auto_discover_groups': config.auto_discover_groups,
            'output_dir': str(output_dir),  # Pasar directorio específico del job
        }
        
        logger.info(f"   Configuración del agente: project_path={project_path}, group_path={group_path}, auto_discover={config.auto_discover_groups}")
        
        orchestrator = RepositoryAgent(agent_config)
        
        with orchestrators_lock:
            orchestrators_store[job_id] = orchestrator
        
        logger.info(f"✅ Orquestador creado para job {job_id}")
        
        # ═══════════════════════════════════════════════════════════════
        # 3. ACTUALIZAR PROGRESO: Preparado
        # ═══════════════════════════════════════════════════════════════
        
        update_job(
            job_id,
            progress=0.15,
            message="Conectando a repositorio..."
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 4. EJECUTAR ANÁLISIS DE APIs
        # ═══════════════════════════════════════════════════════════════
        
        logger.info(f"🚀 Iniciando análisis de APIs para job {job_id}")
        
        result = orchestrator.run()
        
        logger.info(f"📊 Análisis completado. Success: {result.get('success', False)}")
        
        # ═══════════════════════════════════════════════════════════════
        # 5. VERIFICAR RESULTADO
        # ═══════════════════════════════════════════════════════════════
        
        if not result.get("success"):
            error_msg = result.get("error", "Error desconocido en análisis")
            update_job(
                job_id,
                status="failed",
                progress=0.0,
                error=error_msg,
                message=f"Error: {error_msg}"
            )
            logger.error(f"❌ Análisis falló para job {job_id}: {error_msg}")
            return
        
        # ═══════════════════════════════════════════════════════════════
        # 6. COMPLETAR JOB
        # ═══════════════════════════════════════════════════════════════
        
        # Listar archivos generados
        generated_files = []
        for file_path in output_dir.glob("*.json"):
            generated_files.append({
                "filename": file_path.name,
                "size_kb": round(file_path.stat().st_size / 1024, 2)
            })
        
        # Construir resultado final
        completion_result = {
            "specs_found": result.get("specs_found", 0),
            "code_apis_found": result.get("code_apis_found", 0),
            "total_endpoints": result.get("total_endpoints", 0),
            "files_generated": generated_files,
            "file_count": len(generated_files),
            "output_dir": str(output_dir),
            "success": True
        }
        
        update_job(
            job_id,
            status="completed",
            progress=1.0,
            message="Análisis de APIs completado exitosamente",
            result=completion_result
        )
        
        logger.info(f"✅ Job {job_id} completado exitosamente")
        logger.info(f"📊 Especificaciones encontradas: {completion_result['specs_found']}")
        logger.info(f"💻 APIs en código: {completion_result['code_apis_found']}")
        logger.info(f"🔌 Total endpoints: {completion_result['total_endpoints']}")
        logger.info(f"📁 Archivos generados: {len(generated_files)}")
        
    except Exception as e:
        logger.error(f"❌ Error en job {job_id}: {str(e)}")
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        update_job(
            job_id,
            status="failed",
            progress=0.0,
            error=str(e),
            message=f"Error: {str(e)}",
            result={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": error_trace
            }
        )
    
    finally:
        # Limpiar orquestador
        with orchestrators_lock:
            if job_id in orchestrators_store:
                del orchestrators_store[job_id]


# ============================================================
# FUNCIÓN PARA OBTENER LLM (AzureProvider o AzureBearerProvider)
# ============================================================

try:
    from AzureProvider import get_azure_provider
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    logger.warning("AzureProvider no disponible. Modo análisis básico activado.")

def get_llm(job_id, req: Optional[GenerateRequest] = None):
    """Obtiene el cliente LLM usando AzureProvider o AzureBearerProvider según corresponda"""
    try:
        if req is None or req.bearer_token is None:
            # Usar AzureProvider (con credenciales de .env)
            provider = get_azure_provider()
            llm = provider.get_llm()
            logger.info("✅ LLM habilitado para análisis inteligente (AzureProvider)")

            if not provider.test_connection():
                raise ValueError("Azure OpenAI connection test failed")
        else:
            # Usar AzureBearerProvider (con bearer token del request)
            from AzureBearerProvider import AzureEnablerSimple
            
            if req.azure_endpoint and req.azure_deployment:
                llm = AzureEnablerSimple(
                    bearer_token=req.bearer_token,
                    azure_endpoint=req.azure_endpoint,
                    deployment_name=req.azure_deployment,
                    api_version=req.azure_api_version,
                    axet_user_id=req.axet_user_id,
                    asset_id=req.asset_id
                )

                logger.info(f"✅ Usando Bearer Token para {req.azure_deployment}")
                if req.axet_user_id:
                    logger.info(f"   Axet User ID: {req.axet_user_id}")
                if req.asset_id:
                    logger.info(f"   Asset ID: {req.asset_id}")

                logger.warning(f"✅ LLM inicializado para job {job_id}")
                
                # Test de conexión (opcional, para validar credenciales)            
                if not llm.test_connection():
                    raise ValueError("Azure OpenAI connection test failed")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Proporcione bearer_token + azure_endpoint + azure_deployment + axet_user_id + asset_id"
                )        
    except Exception as e:
        logger.warning(f"⚠️ No se pudo inicializar LLM: {e}")
        return None
    return llm

# ============================================================
# ENDPOINTS PARA INSIGHTS Y RECOMENDACIONES (LLM)
# ============================================================

@app.post("/api/v1/jobs/{job_id}/insights")
async def get_insights(job_id: str, req: GenerateRequest):
    """
    🤖 Generar insights inteligentes usando LLM
    Analiza el catálogo completo de APIs y proporciona análisis profundo
    """
    try:
        # Verificar si el directorio del job existe (con archivos generados)
        job_dir = OUTPUT_DIR / job_id
        if not job_dir.exists():
            raise HTTPException(status_code=404, detail="Job no encontrado")
        
        # Cargar el catálogo de APIs
        catalog_file = job_dir / "catalogo_apis_completo.json"
        if not catalog_file.exists():
            raise HTTPException(status_code=400, detail="Catálogo no encontrado. Job puede aún estar en progreso.")
        
        with open(catalog_file) as f:
            catalog = json.load(f)
        
        # Obtener cliente LLM usando get_llm()
        llm_client = get_llm(job_id, req)
        
        # Usar LLMAnalyzer para generar insights
        from LLMAnalyzer import LLMAnalyzer
        llm_analyzer = LLMAnalyzer(llm_provider=llm_client)
        
        # Generar insights (con fallback automático si no hay LLM)
        insights = llm_analyzer.analyze_api_catalog(catalog)
        source = "llm" if llm_analyzer.llm else "basic"
        
        return {
            "insights": insights,
            "source": source,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando insights: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/jobs/{job_id}/recommendations")
async def get_recommendations(job_id: str, req: GenerateRequest):
    """
    📋 Generar recomendaciones inteligentes usando LLM
    Proporciona plan de acción para optimizar y limpiar APIs
    """
    try:
        # Verificar si el directorio del job existe (con archivos generados)
        job_dir = OUTPUT_DIR / job_id
        if not job_dir.exists():
            raise HTTPException(status_code=404, detail="Job no encontrado")
        
        # Cargar archivos de análisis
        catalog_file = job_dir / "catalogo_apis_completo.json"
        topology_file = job_dir / "topologia_apis.json"
        
        if not catalog_file.exists() or not topology_file.exists():
            raise HTTPException(status_code=400, detail="Archivos de análisis no encontrados. Job puede aún estar en progreso.")
        
        with open(catalog_file) as f:
            catalog = json.load(f)
        with open(topology_file) as f:
            topology = json.load(f)
        
        # Obtener cliente LLM usando get_llm()
        llm_client = get_llm(job_id, req)
        
        # Usar LLMAnalyzer para generar recomendaciones
        from LLMAnalyzer import LLMAnalyzer
        llm_analyzer = LLMAnalyzer(llm_provider=llm_client)
        
        # Generar recomendaciones (con fallback automático si no hay LLM)
        recommendations = llm_analyzer.generate_cleanup_plan(catalog, topology)
        source = "llm" if llm_analyzer.llm else "basic"
        
        return {
            "recommendations": recommendations,
            "source": source,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando recomendaciones: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# ENDPOINT ANÁLISIS LLM
# ============================================================

@app.post("/api/v1/jobs/{job_id}/llm-analysis")
async def llm_analysis(job_id: str, body: dict):
    """Genera análisis usando LLM basado en contexto de APIs"""
    try:
        from LLMAnalyzer import LLMAnalyzer
        
        llm = LLMAnalyzer()
        context = body.get('context', '')
        
        # Generar análisis con LLM
        insights = llm.generate_insights(f"API Analysis Context:\n{context}") if llm.llm else "Análisis no disponible sin LLM"
        recommendations = llm.generate_recommendations(context) if llm.llm else "Recomendaciones no disponibles"
        risks = llm.generate_risks(context) if llm.llm else "Análisis de riesgos no disponible"
        
        return {
            "job_id": job_id,
            "insights": insights,
            "recommendations": recommendations,
            "risks": risks,
            "has_llm": bool(llm.llm)
        }
    except Exception as e:
        logger.error(f"Error en análisis LLM: {e}")
        return {
            "job_id": job_id,
            "insights": "Error generando insights",
            "recommendations": "Error generando recomendaciones",
            "risks": "Error analizando riesgos",
            "has_llm": False,
            "error": str(e)
        }


# ============================================================
# ENDPOINTS ESPECIALIZADOS DE ANÁLISIS CON LLM
# ============================================================

@app.post("/api/v1/jobs/{job_id}/llm/architecture")
async def llm_architecture_analysis(job_id: str):
    """Analiza la arquitectura de APIs encontradas"""
    try:
        from LLMAnalyzer import LLMAnalyzer
        
        # Obtener datos del análisis completado
        analysis_data = await get_job_analysis(job_id)
        if not analysis_data:
            return {
                "success": False,
                "error": "Job no encontrado o análisis incompleto",
                "analysis": ""
            }
        
        llm = LLMAnalyzer()
        prompt = f"""Analiza la siguiente información de APIs y proporciona un análisis detallado de su arquitectura:

APIs encontradas:
{json.dumps(analysis_data.get('catalog', {}), indent=2)}

Topología:
{json.dumps(analysis_data.get('topology', {}), indent=2)}

Por favor, analiza:
1. Patrones arquitectónicos identificados
2. Componentes principales y su rol
3. Dependencias entre APIs
4. Flujos de datos principales
5. Recomendaciones de mejora arquitectónica"""
        
        analysis = llm.generate_insights(prompt) if llm.llm else "Análisis de arquitectura no disponible sin LLM"
        
        return {
            "success": True,
            "job_id": job_id,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error en análisis de arquitectura: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis": ""
        }


@app.post("/api/v1/jobs/{job_id}/llm/security")
async def llm_security_analysis(job_id: str):
    """Analiza aspectos de seguridad en las APIs"""
    try:
        from LLMAnalyzer import LLMAnalyzer
        
        analysis_data = await get_job_analysis(job_id)
        if not analysis_data:
            return {
                "success": False,
                "error": "Job no encontrado o análisis incompleto",
                "analysis": ""
            }
        
        llm = LLMAnalyzer()
        prompt = f"""Realiza un análisis de seguridad detallado de las siguientes APIs:

APIs encontradas:
{json.dumps(analysis_data.get('catalog', {}), indent=2)}

Por favor, evalúa:
1. Mecanismos de autenticación utilizados
2. Estrategias de autorización
3. Potenciales vulnerabilidades (inyecciones, XSS, CSRF, etc)
4. Gestión de secretos y credenciales
5. Validación de inputs
6. Recomendaciones de hardening
7. Cumplimiento de estándares de seguridad (OWASP)"""
        
        analysis = llm.generate_insights(prompt) if llm.llm else "Análisis de seguridad no disponible sin LLM"
        
        return {
            "success": True,
            "job_id": job_id,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error en análisis de seguridad: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis": ""
        }


@app.post("/api/v1/jobs/{job_id}/llm/performance")
async def llm_performance_analysis(job_id: str):
    """Analiza oportunidades de optimización de rendimiento"""
    try:
        from LLMAnalyzer import LLMAnalyzer
        
        analysis_data = await get_job_analysis(job_id)
        if not analysis_data:
            return {
                "success": False,
                "error": "Job no encontrado o análisis incompleto",
                "analysis": ""
            }
        
        llm = LLMAnalyzer()
        prompt = f"""Analiza el rendimiento y oportunidades de optimización de estas APIs:

APIs encontradas:
{json.dumps(analysis_data.get('catalog', {}), indent=2)}

Estadísticas:
{json.dumps(analysis_data.get('resumen_ejecutivo', {}), indent=2)}

Por favor, identifica:
1. Endpoints potencialmente lentos o ineficientes
2. Oportunidades de caching
3. Llamadas innecesarias o redundantes
4. Problemas de escalabilidad
5. Endpoints no utilizados que podrían ser eliminados
6. Oportunidades de paralelización
7. Recomendaciones de optimización específicas"""
        
        analysis = llm.generate_insights(prompt) if llm.llm else "Análisis de rendimiento no disponible sin LLM"
        
        return {
            "success": True,
            "job_id": job_id,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error en análisis de rendimiento: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis": ""
        }


@app.post("/api/v1/jobs/{job_id}/llm/compatibility")
async def llm_compatibility_analysis(job_id: str):
    """Analiza compatibilidad entre versiones y cambios potencialmente incompatibles"""
    try:
        from LLMAnalyzer import LLMAnalyzer
        
        analysis_data = await get_job_analysis(job_id)
        if not analysis_data:
            return {
                "success": False,
                "error": "Job no encontrado o análisis incompleto",
                "analysis": ""
            }
        
        llm = LLMAnalyzer()
        prompt = f"""Realiza un análisis de compatibilidad entre versiones de estas APIs:

APIs encontradas:
{json.dumps(analysis_data.get('catalog', {}), indent=2)}

Topología:
{json.dumps(analysis_data.get('topology', {}), indent=2)}

Por favor, analiza:
1. Cambios breaking entre versiones (si aplica)
2. Compatibilidad hacia atrás
3. Estrategia de versionamiento observada
4. Impacto de cambios en consumidores
5. Plan de migración para cambios incompatibles
6. Recomendaciones de deprecación
7. Estrategia de versioning recomendada"""
        
        analysis = llm.generate_insights(prompt) if llm.llm else "Análisis de compatibilidad no disponible sin LLM"
        
        return {
            "success": True,
            "job_id": job_id,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error en análisis de compatibilidad: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis": ""
        }


@app.post("/api/v1/jobs/{job_id}/llm/documentation")
async def llm_generate_documentation(job_id: str):
    """Genera documentación automática para las APIs"""
    try:
        from LLMAnalyzer import LLMAnalyzer
        
        analysis_data = await get_job_analysis(job_id)
        if not analysis_data:
            return {
                "success": False,
                "error": "Job no encontrado o análisis incompleto",
                "analysis": ""
            }
        
        llm = LLMAnalyzer()
        prompt = f"""Genera documentación comprensiva para estas APIs:

APIs encontradas:
{json.dumps(analysis_data.get('catalog', {}), indent=2)}

Por favor, crea:
1. Descripción general del conjunto de APIs
2. Tabla de contenidos detallada
3. Guía de instalación/configuración
4. Autenticación y autorización
5. Ejemplos de uso para cada endpoint principal
6. Guía de integración paso a paso
7. Solución de problemas comunes
8. Referencias y mejores prácticas
9. Guía de migración para usuarios de versiones previas
10. FAQ y soporte"""
        
        analysis = llm.generate_insights(prompt) if llm.llm else "Generación de documentación no disponible sin LLM"
        
        return {
            "success": True,
            "job_id": job_id,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error generando documentación: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis": ""
        }


@app.post("/api/v1/jobs/{job_id}/llm/migration")
async def llm_generate_migration_plan(job_id: str):
    """Genera un plan detallado de migración y refactorización"""
    try:
        from LLMAnalyzer import LLMAnalyzer
        
        analysis_data = await get_job_analysis(job_id)
        if not analysis_data:
            return {
                "success": False,
                "error": "Job no encontrado o análisis incompleto",
                "analysis": ""
            }
        
        llm = LLMAnalyzer()
        prompt = f"""Crea un plan de migración y refactorización detallado para estas APIs:

APIs actuales:
{json.dumps(analysis_data.get('catalog', {}), indent=2)}

Topología actual:
{json.dumps(analysis_data.get('topology', {}), indent=2)}

Por favor, proporciona:
1. Análisis del estado actual
2. Objetivos de migración recomendados
3. Fase 1: Preparación
   - Auditoría de dependencias
   - Identificación de riesgos
   - Plan de comunicación
4. Fase 2: Refactorización
   - Mejoras arquitectónicas
   - Modernización de tecnologías
   - Cambios de API
5. Fase 3: Migración
   - Pasos secuenciales
   - Gestión de compatibilidad
   - Rollback plans
6. Fase 4: Post-migración
   - Validación
   - Optimización
   - Documentación
7. Cronograma estimado
8. Recursos necesarios
9. Métricas de éxito
10. Planes de contingencia"""
        
        analysis = llm.generate_insights(prompt) if llm.llm else "Generación de plan de migración no disponible sin LLM"
        
        return {
            "success": True,
            "job_id": job_id,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error generando plan de migración: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis": ""
        }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )