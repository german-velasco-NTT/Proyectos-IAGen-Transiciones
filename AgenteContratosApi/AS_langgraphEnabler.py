"""
AS_langgraphEnabler.py

Agente LangGraph para análisis de contratos API y topología en repositorios
Soporta GitLab, GitHub y Azure DevOps
"""

import os
import json
import re
import yaml
import logging
from enum import Enum
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import traceback
from urllib.parse import urlparse

# LLM imports
try:
    from langchain_openai import AzureChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    AzureChatOpenAI = None
    ChatPromptTemplate = None
    JsonOutputParser = None

# Azure SDK
try:
    from azure.identity import DefaultAzureCredential
    from azure.devops.connection import Connection
except ImportError:
    pass

# GitLab SDK
try:
    import gitlab
except ImportError:
    gitlab = None

# GitHub SDK
try:
    from github import Github
except ImportError:
    Github = None

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# ========================================================================
# CONFIGURACIÓN Y ENUMS
# ========================================================================

class RepositoryPlatform(str, Enum):
    GITLAB = "gitlab"
    GITHUB = "github"
    AZURE_DEVOPS = "azure_devops"
    UNKNOWN = "unknown"

# ============================================================
# CONFIGURACIÓN DE SALIDA
# ============================================================

OUT_DIR = os.environ.get("OUT_DIR", "./out/api_topology")
os.makedirs(OUT_DIR, exist_ok=True)

# ========================================================================
# UTILIDADES
# ========================================================================

class PlatformDetector:
    """Detecta y parsea URLs de GitLab, GitHub y Azure DevOps"""
    
    @staticmethod
    def detect_platform(url: str) -> RepositoryPlatform:
        """Detecta si una URL es de GitLab, GitHub, Azure DevOps u otra plataforma"""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or parsed.netloc
            
            if "github.com" in hostname:
                return RepositoryPlatform.GITHUB
            elif "dev.azure.com" in hostname or "visualstudio.com" in hostname:
                return RepositoryPlatform.AZURE_DEVOPS
            elif "gitlab" in hostname or "git" in hostname.lower():
                # Si contiene "gitlab" o "git" en el hostname, asumir que es GitLab
                return RepositoryPlatform.GITLAB
            else:
                # Por defecto, asumir GitLab para cualquier URL no identificada
                return RepositoryPlatform.GITLAB
        except Exception:
            return RepositoryPlatform.GITLAB
    
    @staticmethod
    def get_api_url(url: str) -> str:
        """Extrae la URL base de la API"""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or parsed.netloc
            
            if "github.com" in hostname:
                return "https://api.github.com"
            elif "dev.azure.com" in hostname or "visualstudio.com" in hostname:
                # Azure DevOps API
                return "https://dev.azure.com"
            elif "gitlab" in hostname:
                # Para GitLab, usa la URL base del servidor
                scheme = parsed.scheme or "https"
                return f"{scheme}://{hostname}"
            else:
                return url
        except Exception:
            return url

class GitLabUtils:
    SEMVER_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+].*)?$")

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def parse_iso(dt_str: str) -> datetime:
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            # fallback común en GitLab
            from datetime import datetime as dt
            return dt.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

    @staticmethod
    def days_ago(dt: datetime) -> int:
        return (GitLabUtils.utcnow() - dt).days

    @staticmethod
    def is_semver(tag_name: str) -> bool:
        return GitLabUtils.SEMVER_RE.match(tag_name) is not None

    @staticmethod
    def save_json(obj: Any, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    @staticmethod
    def gl_list_all(func, **kwargs) -> List:
        page = 1
        per_page = kwargs.pop("per_page", 100)
        acc = []
        while True:
            items = func(page=page, per_page=per_page, **kwargs)
            if not items:
                break
            acc.extend(items)
            if len(items) < per_page:
                break
            page += 1
        return acc

# ============================================================
# UTILIDADES DE GUARDADO
# ============================================================

def save_json(obj: Any, filename: str, output_dir: str = None) -> str:
    """Guardar objeto como JSON"""
    _dir = output_dir or OUT_DIR
    os.makedirs(_dir, exist_ok=True)
    path = os.path.join(_dir, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Guardado: {path}")
        return path
    except Exception as e:
        logger.error(f"❌ Error guardando {filename}: {e}")
        return ""

def save_yaml(obj: Any, filename: str, output_dir: str = None) -> str:
    """Guardar objeto como YAML"""
    _dir = output_dir or OUT_DIR
    os.makedirs(_dir, exist_ok=True)
    path = os.path.join(_dir, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(obj, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"✅ Guardado: {path}")
        return path
    except Exception as e:
        logger.error(f"❌ Error guardando {filename}: {e}")
        return ""

# ============================================================
# CONFIGURACIÓN DE PATRONES
# ============================================================

# Extensiones de archivos API
API_SPEC_EXTENSIONS = {'.yaml', '.yml', '.json', '.raml', '.wsdl', '.xml'}
CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cs'}

# Patrones para detectar APIs en código
API_PATTERNS = {
    'rest': {
        'decorator': r'@(?:app\.|api\.|router\.)?(?:route|get|post|put|delete|patch|api_view)\s*\(["\']([^"\']+)',
        'flask': r'@app\.route\s*\(["\']([^"\']+)["\'].*?methods\s*=\s*\[([^\]]+)\]',
        'fastapi': r'@app\.(?:get|post|put|delete|patch)\s*\(["\']([^"\']+)',
        'express': r'(?:app|router)\.(?:get|post|put|delete|patch)\s*\(["\']([^"\']+)',
        'spring': r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*\((?:value\s*=\s*)?["\']([^"\']+)',
        'django': r'path\s*\(["\']([^"\']+)["\'],',
        'axios': r'axios\.(?:get|post|put|delete|patch)\s*\(["\']([^"\']+)',
        'fetch': r'fetch\s*\(["\']([^"\']+)["\']',
    },
    'soap': {
        'wsdl': r'<wsdl:service\s+name=["\']([^"\']+)',
        'endpoint': r'<soap:address\s+location=["\']([^"\']+)',
        'operation': r'<wsdl:operation\s+name=["\']([^"\']+)',
    }
}

# Patrones de autenticación
AUTH_PATTERNS = {
    'jwt': r'(?i)(jwt|jsonwebtoken|bearer|token)',
    'oauth': r'(?i)(oauth|oauth2)',
    'apikey': r'(?i)(api[_-]?key|x-api-key)',
    'basic': r'(?i)(basic\s+auth|authorization:\s*basic)',
    'session': r'(?i)(session|cookie)',
}

# ============================================================
# CLASE PRINCIPAL DEL AGENTE
# ============================================================

class RepositoryAgent:
    """Agente inteligente para análisis de APIs en repositorios"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializar el agente con configuración
        
        Args:
            config: Diccionario con configuración del agente
                - repo_type: 'gitlab', 'github', 'azure'
                - repo_url o url: URL del repositorio
                - token: Token de autenticación
                - project_path: Ruta del proyecto (GitLab/Azure)
                - organization: Organización (GitHub)
                - use_ai: Boolean para usar LLM para análisis
                - output_dir: Directorio de salida para resultados
        """
        self.config = config
        # Soportar diferentes nombres de parámetros
        # Detectar plataforma
        repository_url =  config.get('url')
        self.repo_type = PlatformDetector.detect_platform(repository_url)
        self.repo_url = PlatformDetector.get_api_url(repository_url)
        # self.repo_type = config.get('repo_type', 'gitlab')
        # self.repo_url = config.get('url') or config.get('repo_url', 'https://gitlab.com')
        self.token = config.get('token')
        
        # Cargar project_path del config o del .env
        self.project_path = config.get('project_path') or os.getenv('PROJECT_PATH')
        
        self.output_dir = config.get('output_dir', OUT_DIR)
        
        # Crear directorio de salida
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.repo_client = None
        self.specs = []
        self.code_apis = []
        self.topology = {}
        self.normalized_contracts = []
        self.catalog = {}
        
        # Inicializar cliente según tipo de repositorio
        self._init_repo_client()
        
        # Inicializar LLM si está habilitado
        self.llm = None
        if config.get('use_ai', True):
            self._init_llm()
        
        logger.info(f"✅ Agente inicializado para {self.repo_type}")
    
    def _init_repo_client(self):
        """Inicializar cliente del repositorio"""
        try:
            if self.repo_type == 'gitlab':
                if not gitlab:
                    raise ImportError("python-gitlab no está instalado")
                self.repo_client = gitlab.Gitlab(
                    self.repo_url,
                    private_token=self.token
                )
                self.repo_client.auth()
                logger.info("✅ Conectado a GitLab")
            
            elif self.repo_type == 'github':
                if not Github:
                    raise ImportError("PyGithub no está instalado")
                self.repo_client = Github(self.config.get('token'))
                logger.info("✅ Conectado a GitHub")
            
            elif self.repo_type == 'azure':
                credential = DefaultAzureCredential()
                connection = Connection(
                    base_url=self.config.get('repo_url'),
                    creds=credential
                )
                self.repo_client = connection.clients.get_git_client()
                logger.info("✅ Conectado a Azure DevOps")
            
            else:
                raise ValueError(f"Tipo de repositorio no soportado: {self.repo_type}")
        
        except Exception as e:
            logger.error(f"❌ Error inicializando cliente: {e}")
            raise
    
    def _init_llm(self):
        """Inicializar cliente LLM"""
        try:
            if AzureChatOpenAI is None:
                logger.warning("⚠️ langchain_openai no está disponible")
                return
                
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
            
            if api_key and endpoint:
                self.llm = AzureChatOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=endpoint,
                    deployment_name=deployment,
                    temperature=0.3
                )
                logger.info("✅ LLM inicializado")
            else:
                logger.warning("⚠️ Credenciales de Azure OpenAI no configuradas")
        
        except Exception as e:
            logger.warning(f"⚠️ Error inicializando LLM: {e}")
    
    # ============================================================
    # MÉTODOS DE ANÁLISIS
    # ============================================================
    
    def run(self) -> Dict[str, Any]:
        """
        Método compatible con API - ejecuta análisis y retorna resultados
        
        Returns:
            Dict con estado del análisis
        """
        return self.analyze()
    
    def analyze(self) -> Dict[str, Any]:
        """
        Ejecutar análisis completo del repositorio
        
        Returns:
            Dict con resultados del análisis
        """
        logger.info("🚀 Iniciando análisis completo...")
        
        try:
            # Paso 1: Escanear especificaciones
            logger.info("📋 Escaneando especificaciones de API...")
            self.specs = self._scan_api_specs()
            logger.info(f"   ✅ {len(self.specs)} especificaciones encontradas")
            
            # Paso 2: Escanear código
            logger.info("💻 Escaneando código fuente...")
            self.code_apis = self._scan_code_apis()
            logger.info(f"   ✅ {len(self.code_apis)} archivos con APIs encontrados")
            
            if not self.specs and not self.code_apis:
                logger.warning("⚠️ No se encontraron APIs")
                # Aun así, es un análisis exitoso - solo sin resultados
                # Crear catálogo vacío
                self.catalog = {
                    "total_specs": 0,
                    "total_code_files": 0,
                    "total_endpoints": 0,
                    "specs": [],
                    "code_apis": [],
                    "topology": {}
                }
                # Guardar catálogo vacío
                save_json(self.catalog, "catalogo_apis_completo.json", self.output_dir)
                return {
                    'success': True,  # Cambiar a True - es un resultado válido
                    'status': 'no_apis_found',
                    'specs_found': 0,
                    'code_apis_found': 0,
                    'total_endpoints': 0,
                    'total_contracts': 0
                }
            
            # Paso 3: Construir topología
            logger.info("🗺️ Construyendo topología de APIs...")
            self.topology = self._build_api_topology()
            
            # Paso 4: Normalizar contratos
            logger.info("📝 Normalizando contratos a OpenAPI 3.0...")
            self.normalized_contracts = self._normalize_contracts()
            
            # Paso 5: Generar catálogo
            logger.info("📚 Generando catálogo de APIs...")
            self.catalog = self._generate_api_catalog()
            
            # Paso 6: Análisis con IA (si está disponible)
            if self.llm:
                logger.info("🤖 Generando análisis con IA...")
                self._generate_ai_analysis()
            
            logger.info("✅ Análisis completado exitosamente")
            
            return {
                'success': True,
                'status': 'success',
                'specs_found': len(self.specs),
                'code_apis_found': len(self.code_apis),
                'total_endpoints': self.topology.get('total_endpoints', 0),
                'total_contracts': len(self.normalized_contracts),
                'catalog': self.catalog
            }
        
        except Exception as e:
            logger.error(f"❌ Error en análisis: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'status': 'error',
                'error': str(e),
                'specs_found': 0,
                'code_apis_found': 0,
                'total_endpoints': 0,
                'total_contracts': 0
            }
    
    def _scan_api_specs(self) -> List[Dict]:
        """Escanear especificaciones de API en el repositorio"""
        specs = []
        
        try:
            if self.repo_type == 'gitlab':
                specs = self._scan_specs_gitlab()
            elif self.repo_type == 'github':
                specs = self._scan_specs_github()
            elif self.repo_type == 'azure':
                specs = self._scan_specs_azure()
        
        except Exception as e:
            logger.error(f"Error escaneando specs: {e}")
        
        return specs
    
    def _scan_specs_gitlab(self) -> List[Dict]:
        """Escanear especificaciones en GitLab"""
        specs = []
        
        try:
            project_path = self.config.get('project_path')
            group_path = self.config.get('group_path')
            auto_discover = self.config.get('auto_discover_groups', False)
            
            # Determinar qué proyectos escanear
            projects_to_scan = []
            
            if project_path:
                # Escanear un proyecto específico
                try:
                    project = self.repo_client.projects.get(project_path)
                    projects_to_scan = [project]
                    logger.info(f"📦 Escaneando proyecto: {project_path}")
                except Exception as e:
                    logger.error(f"❌ No se encontró proyecto {project_path}: {e}")
                    return specs
            
            elif group_path:
                # Escanear todos los proyectos en un grupo
                try:
                    group = self.repo_client.groups.get(group_path)
                    projects_to_scan = group.projects.list(get_all=True)
                    logger.info(f"📦 Escaneando grupo: {group_path} ({len(projects_to_scan)} proyectos)")
                except Exception as e:
                    logger.error(f"❌ No se encontró grupo {group_path}: {e}")
                    return specs
            
            elif auto_discover:
                # Auto-discovery: escanear todos los proyectos del usuario
                try:
                    projects_to_scan = self.repo_client.projects.list(get_all=True, visibility='private')
                    logger.info(f"📦 Auto-discovery: {len(projects_to_scan)} proyectos encontrados")
                except Exception as e:
                    logger.warning(f"⚠️ Error en auto-discovery de proyectos privados: {e}")
                    # Intentar con proyectos públicos si falla lo privado
                    try:
                        projects_to_scan = self.repo_client.projects.list(get_all=True, visibility='public')
                        logger.info(f"📦 Auto-discovery (públicos): {len(projects_to_scan)} proyectos encontrados")
                    except Exception as e2:
                        logger.error(f"❌ Error en auto-discovery: {e2}")
                        return specs
            
            else:
                logger.warning("⚠️ No se especificó proyecto, grupo ni auto-discovery")
                return specs
            
            # Escanear cada proyecto
            for project in projects_to_scan:
                try:
                    logger.debug(f"   Escaneando: {project.path_with_namespace}")
                    items = project.repository_tree(recursive=True, all=True)
                    
                    for item in items:
                        if item['type'] != 'blob':
                            continue
                        
                        file_path = item['path']
                        file_ext = Path(file_path).suffix.lower()
                        file_name = Path(file_path).name.lower()
                        
                        # Detectar especificaciones
                        is_spec = (
                            file_ext in API_SPEC_EXTENSIONS or
                            'swagger' in file_name or
                            'openapi' in file_name or
                            'api-spec' in file_name
                        )
                        
                        if not is_spec:
                            continue
                        
                        try:
                            file_obj = project.files.get(file_path=file_path, ref='main')
                            content = self._extract_text(file_obj.decode())
                            
                            if not content:
                                continue
                            
                            spec_data = self._parse_yaml_safe(content)
                            if spec_data:
                                spec_type = self._detect_spec_type(spec_data, content)
                                
                                if spec_type:
                                    spec_info = {
                                        'project': project.path_with_namespace,
                                        'file_path': file_path,
                                        'spec_type': spec_type,
                                        'raw_content': content[:5000]
                                    }
                                    
                                    # Parsear según tipo
                                    if spec_type == 'openapi':
                                        spec_info.update(self._parse_openapi(spec_data))
                                    elif spec_type == 'swagger':
                                        spec_info.update(self._parse_swagger(spec_data))
                                    elif spec_type == 'wsdl':
                                        spec_info.update(self._parse_wsdl(content))
                                    
                                    specs.append(spec_info)
                                    logger.info(f"   ✅ {spec_type.upper()}: {file_path}")
                        
                        except Exception as e:
                            logger.debug(f"   Error procesando {file_path}: {e}")
                            continue
                
                except Exception as e:
                    logger.debug(f"   Error en proyecto {project.path_with_namespace}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error en scan GitLab: {e}")
        
        return specs
    
    def _scan_specs_github(self) -> List[Dict]:
        """Escanear especificaciones en GitHub"""
        specs = []
        
        try:
            owner = self.config.get('organization')
            repo_name = self.config.get('repository')
            
            if not owner or not repo_name:
                return specs
            
            repo = self.repo_client.get_user(owner).get_repo(repo_name)
            
            def walk_tree(tree, path=''):
                for item in tree:
                    if item.type == 'blob':
                        file_path = f"{path}{item.name}" if path else item.name
                        file_ext = Path(file_path).suffix.lower()
                        
                        if file_ext in API_SPEC_EXTENSIONS or 'swagger' in item.name.lower():
                            try:
                                content = repo.get_contents(file_path).decoded_content.decode()
                                spec_data = self._parse_yaml_safe(content)
                                
                                if spec_data:
                                    spec_type = self._detect_spec_type(spec_data, content)
                                    if spec_type:
                                        spec_info = {
                                            'project': repo.full_name,
                                            'file_path': file_path,
                                            'spec_type': spec_type
                                        }
                                        
                                        if spec_type == 'openapi':
                                            spec_info.update(self._parse_openapi(spec_data))
                                        elif spec_type == 'swagger':
                                            spec_info.update(self._parse_swagger(spec_data))
                                        
                                        specs.append(spec_info)
                            except Exception as e:
                                logger.debug(f"Error con {item.name}: {e}")
                    
                    elif item.type == 'dir':
                        new_path = f"{path}{item.name}/" if path else f"{item.name}/"
                        try:
                            walk_tree(repo.get_contents(new_path), new_path)
                        except Exception:
                            pass
            
            walk_tree(repo.get_contents(''))
        
        except Exception as e:
            logger.error(f"Error en scan GitHub: {e}")
        
        return specs
    
    def _scan_specs_azure(self) -> List[Dict]:
        """Escanear especificaciones en Azure DevOps"""
        specs = []
        return specs
    
    def _scan_code_apis(self) -> List[Dict]:
        """Escanear código fuente para detectar APIs"""
        apis = []
        
        try:
            if self.repo_type == 'gitlab':
                apis = self._scan_code_gitlab()
            elif self.repo_type == 'github':
                apis = self._scan_code_github()
        
        except Exception as e:
            logger.error(f"Error escaneando código: {e}")
        
        return apis
    
    def _scan_code_gitlab(self) -> List[Dict]:
        """Escanear código en GitLab"""
        apis = []
        
        try:
            project_path = self.config.get('project_path')
            group_path = self.config.get('group_path')
            auto_discover = self.config.get('auto_discover_groups', False)
            
            # Determinar qué proyectos escanear
            projects_to_scan = []
            
            if project_path:
                # Escanear un proyecto específico
                try:
                    project = self.repo_client.projects.get(project_path)
                    projects_to_scan = [project]
                    logger.info(f"📦 Escaneando código en proyecto: {project_path}")
                except Exception as e:
                    logger.error(f"❌ No se encontró proyecto {project_path}: {e}")
                    return apis
            
            elif group_path:
                # Escanear todos los proyectos en un grupo
                try:
                    group = self.repo_client.groups.get(group_path)
                    projects_to_scan = group.projects.list(get_all=True)
                    logger.info(f"📦 Escaneando código en grupo: {group_path} ({len(projects_to_scan)} proyectos)")
                except Exception as e:
                    logger.error(f"❌ No se encontró grupo {group_path}: {e}")
                    return apis
            
            elif auto_discover:
                # Auto-discovery: escanear todos los proyectos del usuario
                try:
                    projects_to_scan = self.repo_client.projects.list(get_all=True, visibility='private')
                    logger.info(f"📦 Auto-discovery (código): {len(projects_to_scan)} proyectos encontrados")
                except Exception as e:
                    logger.warning(f"⚠️ Error en auto-discovery de proyectos privados: {e}")
                    # Intentar con proyectos públicos si falla lo privado
                    try:
                        projects_to_scan = self.repo_client.projects.list(get_all=True, visibility='public')
                        logger.info(f"📦 Auto-discovery (código, públicos): {len(projects_to_scan)} proyectos encontrados")
                    except Exception as e2:
                        logger.error(f"❌ Error en auto-discovery: {e2}")
                        return apis
            
            else:
                logger.warning("⚠️ No se especificó proyecto, grupo ni auto-discovery para escaneo de código")
                return apis
            
            # Escanear cada proyecto
            for project in projects_to_scan:
                try:
                    logger.debug(f"   Escaneando código en: {project.path_with_namespace}")
                    items = project.repository_tree(recursive=True, all=True)
                    
                    for item in items:
                        if item['type'] != 'blob':
                            continue
                        
                        file_path = item['path']
                        file_ext = Path(file_path).suffix.lower()
                        
                        if file_ext not in CODE_EXTENSIONS:
                            continue
                        
                        try:
                            file_obj = project.files.get(file_path=file_path, ref='main')
                            content = self._extract_text(file_obj.decode())
                            
                            if not content:
                                continue
                            
                            endpoints = self._detect_rest_endpoints(content, file_path)
                            api_calls = self._detect_api_calls(content)
                            auth = self._detect_authentication(content)
                            
                            if endpoints or api_calls:
                                apis.append({
                                    'project': project.path_with_namespace,
                                    'file_path': file_path,
                                    'language': self._detect_language(file_ext),
                                    'endpoints_defined': endpoints,
                                    'api_calls': api_calls,
                                    'authentication': auth,
                                    'total_endpoints': len(endpoints)
                                })
                        
                        except Exception:
                            continue
                
                except Exception as e:
                    logger.debug(f"   Error en proyecto {project.path_with_namespace}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error en scan código GitLab: {e}")
        
        return apis
    
    def _scan_code_github(self) -> List[Dict]:
        """Escanear código en GitHub"""
        apis = []
        return apis
    
    # ============================================================
    # MÉTODOS DE DETECCIÓN Y PARSING
    # ============================================================
    
    def _detect_spec_type(self, spec_data: Dict, content: str) -> Optional[str]:
        """Detectar tipo de especificación"""
        content_lower = content.lower()
        
        if 'openapi' in spec_data and str(spec_data['openapi']).startswith('3'):
            return 'openapi'
        if 'swagger' in spec_data:
            return 'swagger'
        if '#%RAML' in content or 'raml' in content_lower:
            return 'raml'
        if '<wsdl:' in content or '<definitions' in content:
            return 'wsdl'
        
        return None
    
    def _parse_openapi(self, spec: Dict) -> Dict:
        """Parsear OpenAPI 3.x"""
        info = spec.get('info', {})
        servers = spec.get('servers', [])
        paths = spec.get('paths', {})
        components = spec.get('components', {})
        
        endpoints = []
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                    endpoints.append({
                        'path': path,
                        'method': method.upper(),
                        'summary': details.get('summary', ''),
                        'description': details.get('description', ''),
                        'parameters': details.get('parameters', []),
                        'responses': list(details.get('responses', {}).keys()),
                        'tags': details.get('tags', []),
                        'security': details.get('security', [])
                    })
        
        return {
            'api_title': info.get('title', 'Unknown'),
            'api_version': info.get('version', '1.0.0'),
            'api_description': info.get('description', ''),
            'base_urls': [s.get('url', '') for s in servers],
            'endpoints': endpoints,
            'total_endpoints': len(endpoints),
            'schemas': list(components.get('schemas', {}).keys()),
            'security_schemes': list(components.get('securitySchemes', {}).keys())
        }
    
    def _parse_swagger(self, spec: Dict) -> Dict:
        """Parsear Swagger 2.0"""
        info = spec.get('info', {})
        base_path = spec.get('basePath', '')
        host = spec.get('host', '')
        paths = spec.get('paths', {})
        definitions = spec.get('definitions', {})
        
        endpoints = []
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                    endpoints.append({
                        'path': path,
                        'method': method.upper(),
                        'summary': details.get('summary', ''),
                        'description': details.get('description', ''),
                        'parameters': details.get('parameters', []),
                        'responses': list(details.get('responses', {}).keys()),
                        'tags': details.get('tags', [])
                    })
        
        return {
            'api_title': info.get('title', 'Unknown'),
            'api_version': info.get('version', '1.0.0'),
            'api_description': info.get('description', ''),
            'base_urls': [f"{spec.get('schemes', ['http'])[0]}://{host}{base_path}"],
            'endpoints': endpoints,
            'total_endpoints': len(endpoints),
            'schemas': list(definitions.keys()),
            'security_schemes': list(spec.get('securityDefinitions', {}).keys())
        }
    
    def _parse_wsdl(self, content: str) -> Dict:
        """Parsear WSDL"""
        service_match = re.search(r'<wsdl:service\s+name=["\']([^"\']+)', content)
        service_name = service_match.group(1) if service_match else 'Unknown'
        
        operations = re.findall(r'<wsdl:operation\s+name=["\']([^"\']+)', content)
        endpoints = re.findall(r'<soap:address\s+location=["\']([^"\']+)', content)
        
        return {
            'api_title': service_name,
            'api_type': 'SOAP',
            'api_version': '1.0',
            'base_urls': endpoints,
            'operations': operations,
            'total_endpoints': len(operations)
        }
    
    def _detect_rest_endpoints(self, content: str, file_path: str) -> List[Dict]:
        """Detectar endpoints REST en código"""
        endpoints = []
        
        for framework, pattern in API_PATTERNS['rest'].items():
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for match in matches:
                path = match.group(1)
                method = 'GET'
                
                line = content[max(0, match.start()-100):match.end()+50]
                for m in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    if m in line.upper():
                        method = m
                        break
                
                endpoints.append({
                    'path': path,
                    'method': method,
                    'framework': framework,
                    'line': content[:match.start()].count('\n') + 1
                })
        
        return endpoints
    
    def _detect_api_calls(self, content: str) -> List[Dict]:
        """Detectar llamadas a APIs externas"""
        calls = []
        
        patterns = [
            r'(?:axios|fetch|requests)\.(?:get|post|put|delete|patch)\s*\(["\']([^"\']+)',
            r'http\.(?:get|post|put|delete)\s*\(["\']([^"\']+)',
            r'RestTemplate.*\.(?:get|post|put|delete).*\(["\']([^"\']+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                url = match.group(1)
                if url.startswith('http'):
                    calls.append({
                        'url': url,
                        'type': 'external_api_call'
                    })
        
        return calls
    
    def _detect_authentication(self, content: str) -> List[str]:
        """Detectar métodos de autenticación"""
        auth_methods = []
        content_lower = content.lower()
        
        for auth_type, pattern in AUTH_PATTERNS.items():
            if re.search(pattern, content_lower):
                auth_methods.append(auth_type)
        
        return auth_methods
    
    def _detect_language(self, file_ext: str) -> str:
        """Detectar lenguaje de programación"""
        lang_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.go': 'Go',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.cs': 'C#'
        }
        return lang_map.get(file_ext, 'Unknown')
    
    # ============================================================
    # MÉTODOS DE CONSTRUCCIÓN DE TOPOLOGÍA Y NORMALIZACIÓN
    # ============================================================
    
    def _build_api_topology(self) -> Dict:
        """Construir mapa de topología de APIs"""
        all_endpoints = []
        
        # De especificaciones
        for spec in self.specs:
            for endpoint in spec.get('endpoints', []):
                all_endpoints.append({
                    'source': 'spec',
                    'project': spec['project'],
                    'file': spec['file_path'],
                    'path': endpoint['path'],
                    'method': endpoint['method'],
                    'type': spec['spec_type'],
                    'api_title': spec.get('api_title', ''),
                    'base_url': spec.get('base_urls', [''])[0]
                })
        
        # De código
        for api_file in self.code_apis:
            for endpoint in api_file.get('endpoints_defined', []):
                all_endpoints.append({
                    'source': 'code',
                    'project': api_file['project'],
                    'file': api_file['file_path'],
                    'path': endpoint['path'],
                    'method': endpoint['method'],
                    'type': 'rest',
                    'language': api_file['language'],
                    'framework': endpoint.get('framework', '')
                })
        
        # Detectar dependencias
        dependencies = []
        for api_file in self.code_apis:
            for call in api_file.get('api_calls', []):
                dependencies.append({
                    'from_project': api_file['project'],
                    'from_file': api_file['file_path'],
                    'to_url': call['url'],
                    'type': 'external_call'
                })
        
        # Agrupar por proyecto
        endpoints_by_project = defaultdict(list)
        for ep in all_endpoints:
            endpoints_by_project[ep['project']].append(ep)
        
        return {
            'total_endpoints': len(all_endpoints),
            'endpoints_by_project': dict(endpoints_by_project),
            'dependencies': dependencies,
            'api_types': {
                'rest': len([e for e in all_endpoints if e['type'] in ['openapi', 'swagger', 'rest']]),
                'soap': len([e for e in all_endpoints if e['type'] == 'wsdl']),
            }
        }
    
    def _normalize_contracts(self) -> List[Dict]:
        """Normalizar contratos a formato estándar"""
        normalized = []
        
        for spec in self.specs:
            if spec['spec_type'] in ['openapi', 'swagger']:
                normalized.append({
                    'project': spec['project'],
                    'file': spec['file_path'],
                    'title': spec.get('api_title', 'Unknown API'),
                    'version': spec.get('api_version', '1.0.0'),
                    'type': 'REST',
                    'format': 'openapi_3.0',
                    'endpoints': spec.get('endpoints', []),
                    'base_url': spec.get('base_urls', [''])[0],
                    'original_format': spec['spec_type']
                })
            
            elif spec['spec_type'] == 'wsdl':
                normalized.append({
                    'project': spec['project'],
                    'file': spec['file_path'],
                    'title': spec.get('api_title', 'Unknown SOAP Service'),
                    'version': '1.0',
                    'type': 'SOAP',
                    'format': 'wsdl',
                    'operations': spec.get('operations', []),
                    'base_url': spec.get('base_urls', [''])[0],
                    'original_format': 'wsdl'
                })
        
        # Contratos desde código
        for api_file in self.code_apis:
            if api_file['endpoints_defined']:
                normalized.append({
                    'project': api_file['project'],
                    'file': api_file['file_path'],
                    'title': f"API in {Path(api_file['file_path']).name}",
                    'version': 'inferred',
                    'type': 'REST',
                    'format': 'inferred_from_code',
                    'endpoints': api_file['endpoints_defined'],
                    'language': api_file['language'],
                    'authentication': api_file['authentication']
                })
        
        return normalized
    
    def _generate_api_catalog(self) -> Dict:
        """Generar catálogo de APIs"""
        endpoints_by_project = defaultdict(lambda: {'apis': 0, 'endpoints': 0})
        
        for contract in self.normalized_contracts:
            project = contract['project']
            endpoints_by_project[project]['apis'] += 1
            endpoints_by_project[project]['endpoints'] += len(contract.get('endpoints', []))
        
        catalog = {
            'metadata': {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'total_apis': len(self.normalized_contracts),
                'total_endpoints': self.topology.get('total_endpoints', 0)
            },
            'apis': self.normalized_contracts,
            'topology': self.topology,
            'summary_by_type': {
                'REST': len([c for c in self.normalized_contracts if c['type'] == 'REST']),
                'SOAP': len([c for c in self.normalized_contracts if c['type'] == 'SOAP'])
            },
            'summary_by_project': dict(endpoints_by_project)
        }
        
        # Generar documentación
        self._generate_documentation(catalog)
        
        # Generar reportes
        self._generate_reports(catalog)
        
        return catalog
    
    def _generate_ai_analysis(self) -> Optional[Dict]:
        """Generar análisis con IA"""
        if not self.llm or not ChatPromptTemplate or not JsonOutputParser:
            return None
        
        try:
            summary = {
                'total_apis': len(self.normalized_contracts),
                'total_endpoints': self.topology.get('total_endpoints', 0),
                'rest_apis': self.catalog['summary_by_type']['REST'],
                'soap_apis': self.catalog['summary_by_type']['SOAP'],
            }
            
            prompt = ChatPromptTemplate.from_template(
                """Analiza este ecosistema de APIs y proporciona evaluación en JSON:

                {{
                  "arquitectura": "evaluación de la arquitectura",
                  "documentacion": "nivel de documentación",
                  "riesgos": ["riesgo1", "riesgo2"],
                  "mejoras": ["mejora1", "mejora2"],
                  "recomendaciones": ["rec1", "rec2"]
                }}
                
                Resumen: {summary}
                """
            )
            
            chain = prompt | self.llm | JsonOutputParser()
            analysis = chain.invoke({"summary": str(summary)})
            
            self.catalog['ai_analysis'] = analysis
            return analysis
        
        except Exception as e:
            logger.warning(f"Error en análisis IA: {e}")
            return None
    
    # ============================================================
    # MÉTODOS AUXILIARES
    # ============================================================
    
    def _extract_text(self, file_content: bytes) -> str:
        """Extraer texto de contenido de archivo"""
        try:
            return file_content.decode('utf-8')
        except:
            try:
                return file_content.decode('latin-1')
            except:
                return ""
    
    def _parse_yaml_safe(self, content: str) -> Optional[Dict]:
        """Parsear YAML/JSON de manera segura"""
        try:
            return yaml.safe_load(content)
        except:
            try:
                return json.loads(content)
            except:
                return None
    
    def _generate_documentation(self, catalog: Dict) -> None:
        """Genera documentación técnica"""
        logger.info("📖 Generando documentación técnica...")
        
        # Guía rápida
        quick_guide = self._generate_quick_guide(catalog)
        save_json(quick_guide, 'guia_rapida_apis.json', self.output_dir)
        
        # Mapa de endpoints
        endpoint_map = self._generate_endpoint_map(catalog)
        save_json(endpoint_map, 'mapa_endpoints.json', self.output_dir)
        
        # Políticas de seguridad
        security_policies = self._generate_security_policies(catalog)
        save_json(security_policies, 'politicas_seguridad.json', self.output_dir)
        
        # Guía de versionamiento
        versioning_guide = self._generate_versioning_guide(catalog)
        save_json(versioning_guide, 'guia_versionamiento.json', self.output_dir)
        
        logger.info("   ✅ Documentación generada")
    
    def _generate_quick_guide(self, catalog: Dict) -> Dict:
        """Genera guía rápida de uso de APIs"""
        guide = {
            'title': 'Guía Rápida de APIs',
            'total_apis': catalog['metadata']['total_apis'],
            'apis': []
        }
        
        for api in catalog['apis'][:10]:
            guide['apis'].append({
                'name': api['title'],
                'type': api['type'],
                'base_url': api.get('base_url', ''),
                'total_endpoints': len(api.get('endpoints', [])),
                'authentication': api.get('authentication', []),
                'project': api['project']
            })
        
        return guide
    
    def _generate_endpoint_map(self, catalog: Dict) -> Dict:
        """Genera mapa detallado de endpoints"""
        endpoint_map = {
            'total_endpoints': catalog['metadata']['total_endpoints'],
            'by_method': defaultdict(int),
            'by_path': []
        }
        
        for api in catalog['apis']:
            for endpoint in api.get('endpoints', []):
                method = endpoint.get('method', 'GET')
                endpoint_map['by_method'][method] += 1
                endpoint_map['by_path'].append({
                    'api': api['title'],
                    'method': method,
                    'path': endpoint.get('path', ''),
                    'summary': endpoint.get('summary', '')
                })
        
        endpoint_map['by_method'] = dict(endpoint_map['by_method'])
        return endpoint_map
    
    def _generate_security_policies(self, catalog: Dict) -> Dict:
        """Genera políticas de seguridad detectadas"""
        policies = {
            'authentication_methods': defaultdict(int),
            'recommendations': []
        }
        
        for api in catalog['apis']:
            for auth in api.get('authentication', []):
                policies['authentication_methods'][auth] += 1
        
        policies['authentication_methods'] = dict(policies['authentication_methods'])
        
        # Recomendaciones
        if 'basic' in policies['authentication_methods']:
            policies['recommendations'].append({
                'severity': 'HIGH',
                'message': 'Se detectó autenticación Basic. Considerar migrar a OAuth2 o JWT'
            })
        
        if not policies['authentication_methods']:
            policies['recommendations'].append({
                'severity': 'MEDIUM',
                'message': 'No se detectaron métodos de autenticación en algunas APIs'
            })
        
        return policies
    
    def _generate_versioning_guide(self, catalog: Dict) -> Dict:
        """Genera guía de versionamiento"""
        return {
            'title': 'Guía de Versionamiento de APIs',
            'current_versions': [
                {
                    'api': api['title'],
                    'version': api.get('version', 'unknown')
                }
                for api in catalog['apis']
            ],
            'recommendations': [
                'Usar versionamiento semántico (MAJOR.MINOR.PATCH)',
                'Incluir versión en URL (/v1/, /v2/) o en header',
                'Deprecar versiones antiguas gradualmente',
                'Documentar breaking changes en changelog'
            ]
        }
    
    def _generate_reports(self, catalog: Dict) -> None:
        """Genera todos los reportes"""
        logger.info("📊 Generando reportes finales...")
        
        try:
            # 1. Catálogo completo
            save_json(catalog, 'catalogo_apis_completo.json', self.output_dir)
            
            # 2. Topología
            save_json(self.topology, 'topologia_apis.json', self.output_dir)
            
            # 3. Contratos normalizados
            save_json({
                'contracts': self.normalized_contracts,
                'total': len(self.normalized_contracts)
            }, 'contratos_normalizados.json', self.output_dir)
            
            # 4. Resumen ejecutivo
            summary = {
                'metadata': {
                    'analysis_date': datetime.now(timezone.utc).isoformat()
                },
                'summary': {
                    'total_specs_found': len(self.specs),
                    'total_code_files_with_apis': len(self.code_apis),
                    'total_normalized_contracts': len(self.normalized_contracts),
                    'total_endpoints': self.topology.get('total_endpoints', 0),
                    'total_dependencies': len(self.topology.get('dependencies', [])),
                    'api_types': self.topology.get('api_types', {})
                },
                'breakdown_by_type': {
                    'OpenAPI/Swagger': len([s for s in self.specs if s.get('spec_type') in ['openapi', 'swagger']]),
                    'WSDL/SOAP': len([s for s in self.specs if s.get('spec_type') == 'wsdl']),
                    'RAML': len([s for s in self.specs if s.get('spec_type') == 'raml']),
                    'Inferred from Code': len([c for c in self.normalized_contracts if c.get('format') == 'inferred_from_code'])
                },
                'breakdown_by_project': catalog.get('summary_by_project', {})
            }
            
            save_json(summary, 'resumen_ejecutivo.json', self.output_dir)
            
            # 5. Mostrar resumen
            self._print_summary(summary)
        
        except Exception as e:
            logger.error(f"Error generando reportes: {e}")
            traceback.print_exc()
    
    def _print_summary(self, summary: Dict) -> None:
        """Imprime resumen en consola"""
        logger.info("\n" + "="*80)
        logger.info("🔌 RESUMEN DE ANÁLISIS DE APIs")
        logger.info("="*80)
        
        logger.info(f"\n📊 ESTADÍSTICAS GENERALES:")
        logger.info(f"   • Especificaciones encontradas: {summary['summary']['total_specs_found']}")
        logger.info(f"   • Archivos de código con APIs: {summary['summary']['total_code_files_with_apis']}")
        logger.info(f"   • Contratos normalizados: {summary['summary']['total_normalized_contracts']}")
        logger.info(f"   • Total de endpoints: {summary['summary']['total_endpoints']}")
        logger.info(f"   • Dependencias detectadas: {summary['summary']['total_dependencies']}")
        
        logger.info(f"\n📋 DESGLOSE POR TIPO:")
        for tipo, count in summary['breakdown_by_type'].items():
            if count > 0:
                logger.info(f"   • {tipo}: {count}")
        
        logger.info(f"\n🌐 TIPOS DE API:")
        logger.info(f"   • REST: {summary['summary']['api_types'].get('rest', 0)} endpoints")
        logger.info(f"   • SOAP: {summary['summary']['api_types'].get('soap', 0)} endpoints")
        
        logger.info(f"\n📦 DESGLOSE POR PROYECTO:")
        for project, stats in summary['breakdown_by_project'].items():
            logger.info(f"   • {project}:")
            logger.info(f"      └─ {stats.get('apis', 0)} API(s), {stats.get('endpoints', 0)} endpoint(s)")
        
        logger.info(f"\n📁 ARCHIVOS GENERADOS EN: {OUT_DIR}")
        logger.info("   • catalogo_apis_completo.json")
        logger.info("   • topologia_apis.json")
        logger.info("   • contratos_normalizados.json")
        logger.info("   • resumen_ejecutivo.json")
        logger.info("   • guia_rapida_apis.json")
        logger.info("   • mapa_endpoints.json")
        logger.info("   • politicas_seguridad.json")
        logger.info("   • guia_versionamiento.json")
        
        logger.info("\n" + "="*80)
    
    def get_results(self) -> Dict[str, Any]:
        """Obtener resultados del análisis"""
        return {
            'specs': self.specs,
            'code_apis': self.code_apis,
            'topology': self.topology,
            'normalized_contracts': self.normalized_contracts,
            'catalog': self.catalog
        }
