"""
AS_langgraphEnabler.py

Agente LangGraph para inventario consolidado de aplicaciones
Integra: Repositorios (GitHub, GitLab, Bitbucket, Azure), CMDB, Documentación, Jobs
"""

import os
import json
import re
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import traceback

# LLM imports (tolerantes a entornos con restricciones de SSL/permiso)
try:
    from langchain_openai import AzureChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except Exception:
    # Cualquier problema al importar (incluidos errores de SSL o permisos)
    # deshabilita el LLM pero no rompe el backend.
    AzureChatOpenAI = None
    ChatPromptTemplate = None
    JsonOutputParser = None

# Git SDKs
try:
    import gitlab
except ImportError:
    gitlab = None

try:
    from github import Github
except ImportError:
    Github = None

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# ============================================================
# CONFIGURACIÓN DE SALIDA
# ============================================================

OUT_DIR = os.environ.get("OUT_DIR", "./out/inventory")
os.makedirs(OUT_DIR, exist_ok=True)

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

# ============================================================
# CLASE PRINCIPAL DEL AGENTE DE INVENTARIO
# ============================================================

class InventoryAgent:
    """
    Agente inteligente para consolidar inventario de aplicaciones
    desde múltiples fuentes: repositorios, CMDB, documentación y jobs
    """
    
    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        """
        Inicializar el agente con configuración
        
        Args:
            config: Diccionario con configuración (o usar kwargs)
                - source_type: 'gitlab', 'github', 'bitbucket', 'azure'
                - source_url: URL del repositorio/CMDB
                - token: Token de autenticación
                - project_path: Ruta del proyecto
                - use_ai_analysis: Boolean para usar LLM
                - output_dir: Directorio de salida
        """
        # Soportar ambos: diccionario o kwargs
        if config is None:
            config = kwargs
        elif kwargs:
            config = {**config, **kwargs}
        
        self.config = config
        self.source_type = config.get('source_type', 'gitlab')
        self.source_url = config.get('source_url') or config.get('url', 'https://gitlab.com')
        self.token = config.get('token')
        self.project_path = config.get('project_path') or os.getenv('PROJECT_PATH')
        self.output_dir = config.get('output_dir', OUT_DIR)
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Almacenamiento de datos
        self.repositories = []
        self.applications = []
        self.cmdb_services = []
        self.documentation = {}
        self.jobs = []
        self.issues = []
        self.catalog = {}
        
        # Inicializar cliente
        self.repo_client = None
        self._init_repo_client()
        
        # Inicializar LLM si está habilitado
        self.llm = None
        use_ai = config.get('use_ai_analysis', True)
        if use_ai:
            self._init_llm()
        
        logger.info(f"✅ Agente de Inventario inicializado para {self.source_type}")
    
    def _init_repo_client(self):
        """Inicializar cliente del repositorio"""
        try:
            if self.source_type == 'gitlab':
                if not gitlab:
                    raise ImportError("python-gitlab no está instalado")
                self.repo_client = gitlab.Gitlab(
                    self.source_url,
                    private_token=self.token
                )
                self.repo_client.auth()
                logger.info("✅ Conectado a GitLab")
            
            elif self.source_type == 'github':
                if not Github:
                    raise ImportError("PyGithub no está instalado")
                self.repo_client = Github(self.token)
                logger.info("✅ Conectado a GitHub")
            
            else:
                logger.warning(f"⚠️ Tipo de fuente no completamente soportado: {self.source_type}")
        
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
    # MÉTODOS DE ANÁLISIS - REPOSITORIOS
    # ============================================================
    
    def scan_repositories(self) -> List[Dict[str, Any]]:
        """
        Escanear repositorios de código
        Extrae: nombre, URL, rama, tags, versiones, metadatos
        """
        logger.info("📋 Escaneando repositorios...")
        
        try:
            if self.source_type == 'gitlab':
                return self._scan_gitlab_repos()
            elif self.source_type == 'github':
                return self._scan_github_repos()
            else:
                logger.warning(f"⚠️ Fuente no soportada: {self.source_type}")
                return []
        
        except Exception as e:
            logger.error(f"❌ Error escaneando repositorios: {e}")
            self.issues.append({
                'type': 'scan_error',
                'severity': 'high',
                'message': f'Error escaneando repositorios: {str(e)}'
            })
            return []
    
    def _scan_gitlab_repos(self) -> List[Dict[str, Any]]:
        """Escanear repositorios en GitLab"""
        repos = []
        
        try:
            if self.project_path:
                # Escanear proyecto específico
                try:
                    # No usar lazy=True para obtener datos inicializados
                    project = self.repo_client.projects.get(self.project_path)
                    repos.append(self._extract_repo_metadata(project, 'gitlab'))
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo obtener proyecto {self.project_path}: {e}")
            else:
                # Escanear todos los proyectos accesibles
                projects = self.repo_client.projects.list(get_all=True)
                for project in projects:
                    repos.append(self._extract_repo_metadata(project, 'gitlab'))
            
            logger.info(f"   ✅ {len(repos)} repositorios encontrados en GitLab")
            return repos
        
        except Exception as e:
            logger.error(f"❌ Error en GitLab: {e}")
            return repos
    
    def _scan_github_repos(self) -> List[Dict[str, Any]]:
        """Escanear repositorios en GitHub"""
        repos = []
        
        try:
            if self.repo_client:
                user = self.repo_client.get_user()
                for repo in user.get_repos():
                    repos.append(self._extract_repo_metadata(repo, 'github'))
            
            logger.info(f"   ✅ {len(repos)} repositorios encontrados en GitHub")
            return repos
        
        except Exception as e:
            logger.error(f"❌ Error en GitHub: {e}")
            return repos
    
    def _extract_repo_metadata(self, repo, source: str) -> Dict[str, Any]:
        """Extraer metadatos de un repositorio"""
        try:
            if source == 'gitlab':
                # Usar atributos seguros que siempre están disponibles
                repo_id = getattr(repo, 'id', 'unknown')
                name = getattr(repo, 'name_with_namespace', getattr(repo, 'name', f'repo_{repo_id}'))
                
                return {
                    'id': repo_id,
                    'name': name,
                    'url': getattr(repo, 'web_url', f"gitlab/repo_{repo_id}"),
                    'source': 'gitlab',
                    'description': getattr(repo, 'description', ''),
                    'owner': getattr(repo, 'owner', 'Unknown'),
                    'created_at': str(getattr(repo, 'created_at', 'N/A')),
                    'last_activity': str(getattr(repo, 'last_activity_at', 'N/A')),
                    'visibility': getattr(repo, 'visibility', 'unknown'),
                    'default_branch': getattr(repo, 'default_branch', 'main'),
                    'star_count': getattr(repo, 'star_count', 0),
                    'fork_count': getattr(repo, 'forks_count', 0),
                    'language': getattr(repo, 'language', None),
                    'archived': getattr(repo, 'archived', False)
                }
            
            elif source == 'github':
                return {
                    'id': repo.id,
                    'name': repo.name,
                    'url': repo.html_url,
                    'source': 'github',
                    'description': repo.description,
                    'owner': repo.owner.login if repo.owner else 'Unknown',
                    'created_at': str(repo.created_at),
                    'last_activity': str(repo.pushed_at),
                    'visibility': 'private' if repo.private else 'public',
                    'default_branch': repo.default_branch,
                    'star_count': repo.stargazers_count,
                    'fork_count': repo.forks_count,
                    'language': repo.language,
                    'archived': repo.archived
                }
        
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo metadata: {e}")
            traceback.print_exc()
            return {}
    
    # ============================================================
    # MÉTODOS DE ANÁLISIS - APLICACIONES
    # ============================================================
    
    def extract_applications(self) -> List[Dict[str, Any]]:
        """
        Extraer aplicaciones correlacionando repositorios
        Intenta identificar aplicaciones por patrones en nombres/estructura
        """
        logger.info("🔍 Extrayendo aplicaciones del inventario...")
        
        applications = []
        
        # Agrupar repos por patrón similar (mismo prefijo o similar)
        repo_groups = self._group_repositories()
        
        for group_name, group_repos in repo_groups.items():
            app = {
                'id': f"app-{len(applications) + 1:03d}",
                'name': group_name,
                'repositories': group_repos,
                'repo_count': len(group_repos),
                'status': 'active',  # Inferido
                'owner': 'Unknown',  # Será rellenado por CMDB o documentación
                'team': 'Unknown',
                'business_unit': 'Unknown',
                'cmdb_reference': None,
                'health_score': self._calculate_health_score(group_repos),
                'detected_at': datetime.now(timezone.utc).isoformat(),
            }
            applications.append(app)
        
        logger.info(f"   ✅ {len(applications)} aplicaciones identificadas")
        return applications
    
    def _group_repositories(self) -> Dict[str, List[Dict]]:
        """Agrupar repositorios por aplicación"""
        groups = defaultdict(list)
        
        for repo in self.repositories:
            # Intentar extraer nombre de app del nombre del repo
            # Ejemplo: "app-backend" y "app-frontend" → agrupar como "app"
            name_parts = repo.get('name', '').split('-')
            
            # Usar primeras 2-3 palabras como agrupador
            if len(name_parts) >= 2:
                group_key = '-'.join(name_parts[:2])
            else:
                group_key = name_parts[0] if name_parts else 'unknown'
            
            groups[group_key].append(repo)
        
        return dict(groups)
    
    def _calculate_health_score(self, repos: List[Dict]) -> int:
        """Calcular score de salud basado en repositorios"""
        if not repos:
            return 0
        
        score = 100
        
        # Restar puntos por repositorios archivados
        archived_count = sum(1 for r in repos if r.get('archived', False))
        score -= archived_count * 10
        
        # Restar puntos por falta de actividad reciente
        # (esto se refinaría con fechas reales)
        
        return max(0, min(100, score))
    
    # ============================================================
    # MÉTODOS DE CONSOLIDACIÓN
    # ============================================================
    
    def build_unified_catalog(self) -> Dict[str, Any]:
        """
        Construir catálogo unificado consolidando todas las fuentes
        """
        logger.info("📚 Construyendo catálogo unificado...")
        
        self.catalog = {
            'metadata': {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'version': '1.0.0',
                'source_type': self.source_type,
                'source_url': self.source_url,
            },
            'summary': {
                'total_applications': len(self.applications),
                'total_repositories': len(self.repositories),
                'total_services': len(self.cmdb_services),
                'total_jobs': len(self.jobs),
                'health_score': self._calculate_catalog_health_score(),
            },
            'applications': self.applications,
            'repositories': self.repositories,
            'cmdb_services': self.cmdb_services,
            'jobs': self.jobs,
            'issues_detected': self.issues,
            'statistics': self._generate_statistics(),
        }
        
        logger.info(f"   ✅ Catálogo generado con {len(self.applications)} aplicaciones")
        return self.catalog
    
    def _calculate_catalog_health_score(self) -> int:
        """Calcular score de salud del catálogo completo"""
        if not self.applications:
            return 0
        
        avg_health = sum(app.get('health_score', 0) for app in self.applications) / len(self.applications)
        
        # Restar puntos por issues detectados
        critical_issues = sum(1 for i in self.issues if i.get('severity') == 'critical')
        high_issues = sum(1 for i in self.issues if i.get('severity') == 'high')
        
        score = int(avg_health) - (critical_issues * 5) - (high_issues * 2)
        
        return max(0, min(100, score))
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """Generar estadísticas del inventario"""
        return {
            'repos_by_source': self._count_by_source(),
            'repos_by_language': self._count_by_language(),
            'archived_repos': sum(1 for r in self.repositories if r.get('archived', False)),
            'active_repos': sum(1 for r in self.repositories if not r.get('archived', False)),
            'total_stars': sum(r.get('star_count', 0) for r in self.repositories),
            'total_forks': sum(r.get('fork_count', 0) for r in self.repositories),
        }
    
    def _count_by_source(self) -> Dict[str, int]:
        """Contar repositorios por fuente"""
        counts = defaultdict(int)
        for repo in self.repositories:
            counts[repo.get('source', 'unknown')] += 1
        return dict(counts)
    
    def _count_by_language(self) -> Dict[str, int]:
        """Contar repositorios por lenguaje"""
        counts = defaultdict(int)
        for repo in self.repositories:
            lang = repo.get('language') or 'Unknown'
            counts[lang] += 1
        return dict(counts)
    
    def detect_issues(self):
        """
        Detectar problemas en el inventario:
        - Apps sin dueño
        - Repos huérfanos
        - Módulos desactualizados
        """
        logger.info("🔎 Detectando problemas...")
        
        self.issues = []
        
        # Detectar repos sin aplicación asociada
        repo_ids = {r.get('id') for r in self.repositories}
        app_repo_ids = set()
        for app in self.applications:
            for repo in app.get('repositories', []):
                app_repo_ids.add(repo.get('id'))
        
        orphaned_repos = repo_ids - app_repo_ids
        for repo_id in orphaned_repos:
            repo = next((r for r in self.repositories if r.get('id') == repo_id), None)
            if repo:
                self.issues.append({
                    'type': 'orphaned_repository',
                    'severity': 'high',
                    'repository': repo.get('name'),
                    'url': repo.get('url'),
                    'message': 'Repositorio sin vinculación a aplicación conocida',
                    'recommendation': 'Verificar si aún está en uso o archivar'
                })
        
        # Detectar apps sin dueño
        for app in self.applications:
            if app.get('owner') == 'Unknown':
                self.issues.append({
                    'type': 'missing_owner',
                    'severity': 'critical',
                    'application': app.get('name'),
                    'message': 'Aplicación sin dueño asignado',
                    'recommendation': 'Asignar propietario inmediatamente'
                })
        
        logger.info(f"   ✅ {len(self.issues)} problemas detectados")
    
    # ============================================================
    # MÉTODO PRINCIPAL
    # ============================================================
    
    def analyze(self) -> Dict[str, Any]:
        """
        Ejecutar análisis completo de inventario
        
        Returns:
            Dict con resultados del análisis
        """
        logger.info("🚀 Iniciando análisis de inventario...")
        
        try:
            # Paso 1: Escanear repositorios
            logger.info("📋 Paso 1: Escaneando repositorios...")
            self.repositories = self.scan_repositories()
            
            if not self.repositories:
                logger.warning("⚠️ No se encontraron repositorios")
                return {
                    'success': False,
                    'status': 'no_repositories_found',
                    'message': 'No se encontraron repositorios para analizar'
                }
            
            # Paso 2: Extraer aplicaciones
            logger.info("📱 Paso 2: Extrayendo aplicaciones...")
            self.applications = self.extract_applications()
            
            # Paso 3: Detectar problemas
            logger.info("🔎 Paso 3: Detectando problemas...")
            self.detect_issues()
            
            # Paso 4: Construir catálogo
            logger.info("📚 Paso 4: Construyendo catálogo unificado...")
            self.build_unified_catalog()
            
            # Paso 5: Guardar resultados
            logger.info("💾 Paso 5: Guardando resultados...")
            catalog_path = save_json(self.catalog, 'inventory_catalog.json', self.output_dir)
            
            logger.info("✅ Análisis completado exitosamente")
            
            return {
                'success': True,
                'status': 'completed',
                'repositories_found': len(self.repositories),
                'applications_found': len(self.applications),
                'issues_detected': len(self.issues),
                'catalog_path': catalog_path,
                'summary': self.catalog.get('summary', {})
            }
        
        except Exception as e:
            logger.error(f"❌ Error en análisis: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'status': 'error',
                'error': str(e),
                'message': f'Error durante el análisis: {str(e)}'
            }
    
    def run(self) -> Dict[str, Any]:
        """Alias para analyze() - compatible con API"""
        return self.analyze()


# ============================================================
# COMPATIBILIDAD CON CÓDIGO ANTERIOR
# ============================================================

class RepositoryAgent(InventoryAgent):
    """Alias para compatibilidad con código anterior"""
    pass
