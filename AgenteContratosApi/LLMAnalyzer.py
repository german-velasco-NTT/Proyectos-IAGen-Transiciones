"""
LLM Analyzer - Genera insights y recomendaciones inteligentes usando LLM
Convierte datos brutos en decisiones accionables con explicaciones detalladas
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import threading
import time

# Azure OpenAI via LangChain
from langchain_openai import AzureChatOpenAI
try:
    from langchain.prompts import ChatPromptTemplate
except ImportError:
    from langchain_core.prompts import ChatPromptTemplate
try:
    from langchain.output_parsers import JsonOutputParser
except ImportError:
    from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)
load_dotenv()

class LLMAnalyzer:
    """Analizador que usa LLM para generar insights y recomendaciones"""
    
    def __init__(self):
        """Inicializar el cliente LLM"""
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        
        if not api_key or not endpoint:
            logger.warning("⚠️ Credenciales de Azure OpenAI no configuradas. LLM deshabilitado.")
            self.llm = None
            return
        
        try:
            self.llm = AzureChatOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint,
                deployment_name=deployment,
                temperature=0.3,  # Determinístico para análisis
                max_tokens=2000,
            )
            logger.info(f"✅ LLM inicializado: {deployment}")
        except Exception as e:
            logger.warning(f"⚠️ Error inicializando LLM: {e}")
            self.llm = None
    
    def generate_executive_summary(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera un resumen ejecutivo por grupo/proyecto
        Incluye: estado general, top riesgos, acciones inmediatas
        """
        if not self.llm:
            return self._fallback_summary(analysis_data)
        
        try:
            analysis = analysis_data.get("analysis", {})
            projects = analysis_data.get("projects", [])
            
            # Preparar datos para el LLM
            inactive_branches = analysis.get("total_inactive_branches", 0)
            total_branches = analysis.get("total_branches", 1)
            obsolete_tags = analysis.get("total_obsolete_tags", 0)
            expiring_artifacts = analysis.get("artifacts_expiring_soon", 0)
            expired_artifacts = analysis.get("artifacts_expired", 0)
            
            inactivity_rate = (inactive_branches / total_branches * 100) if total_branches > 0 else 0
            
            prompt = ChatPromptTemplate.from_template("""
Eres un experto en gestión de repositorios Git. Analiza los siguientes datos y genera un resumen ejecutivo:

📊 DATOS:
- Total de proyectos: {num_projects}
- Total de ramas: {total_branches}
- Ramas inactivas: {inactive_branches} ({inactivity_rate:.1f}%)
- Releases/Tags obsoletos: {obsolete_tags}
- Artefactos por expirar: {expiring_artifacts}
- Artefactos expirados: {expired_artifacts}

Proyectos con más ramas inactivas:
{top_projects}

Genera un JSON con:
{{
  "executive_summary": "2 párrafos describiendo el estado general",
  "risk_level": "🔴 CRÍTICO|🟠 ALTO|🟡 MEDIO|🟢 BAJO",
  "top_risks": ["riesgo 1 con explicación", "riesgo 2...", ...],
  "immediate_actions": ["acción 1 con prioridad", "acción 2...", ...],
  "health_score": 0-100,
  "recommendations": ["recomendación 1", "recomendación 2", ...]
}}
""")
            
            # Top 3 proyectos con más ramas inactivas
            top_projects_list = sorted(
                [(p["name"], len([b for b in p.get("branches", []) if b.get("status") == "INACTIVA"])) 
                 for p in projects],
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            top_projects_str = "\n".join([f"  - {name}: {count} inactivas" for name, count in top_projects_list])
            
            chain = prompt | self.llm
            result = chain.invoke({
                "num_projects": len(projects),
                "total_branches": total_branches,
                "inactive_branches": inactive_branches,
                "inactivity_rate": inactivity_rate,
                "obsolete_tags": obsolete_tags,
                "expiring_artifacts": expiring_artifacts,
                "expired_artifacts": expired_artifacts,
                "top_projects": top_projects_str,
            })
            
            # Parsear JSON
            content = result.content
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    summary = json.loads(json_str)
                    logger.info("✅ Executive summary generado por LLM")
                    return summary
            except json.JSONDecodeError:
                logger.warning("⚠️ Error parseando JSON del LLM")
                return self._fallback_summary(analysis_data)
        
        except Exception as e:
            logger.error(f"❌ Error generando executive summary: {e}")
            return self._fallback_summary(analysis_data)
    
    def analyze_branch_health(self, branch: Dict[str, Any], project_name: str) -> Dict[str, Any]:
        """
        Analiza la salud de una rama individual
        Retorna: riesgo, justificación, acciones recomendadas
        """
        if not self.llm:
            return self._fallback_branch_analysis(branch)
        
        try:
            status = branch.get("status", "DESCONOCIDO")
            days_since_commit = branch.get("days_since_last_commit", -1)
            last_commit = branch.get("last_commit_date", "desconocido")
            
            prompt = ChatPromptTemplate.from_template("""
Eres un experto en limpieza de repositorios. Analiza esta rama Git:

🌿 RAMA: {branch_name}
📁 PROYECTO: {project_name}
📊 ESTADO: {status}
📅 ÚLTIMO COMMIT: {last_commit}
⏰ DÍAS SIN ACTIVIDAD: {days_since_commit}

Genera un JSON con:
{{
  "risk_score": 0-100,
  "risk_level": "🔴 CRÍTICO|🟠 ALTO|🟡 MEDIO|🟢 BAJO|🟢 SEGURA",
  "reason": "Explicación clara de por qué esta rama es riesgosa o segura",
  "evidence": ["evidencia 1", "evidencia 2", ...],
  "recommended_action": "ELIMINAR|REVISAR|MANTENER|ARCHIVAR",
  "priority": 1-5,
  "estimated_impact": "Impacto de la acción recomendada"
}}
""")
            
            chain = prompt | self.llm
            result = chain.invoke({
                "branch_name": branch.get("name", "unknown"),
                "project_name": project_name,
                "status": status,
                "last_commit": last_commit,
                "days_since_commit": days_since_commit,
            })
            
            content = result.content
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    analysis = json.loads(json_str)
                    return analysis
            except json.JSONDecodeError:
                return self._fallback_branch_analysis(branch)
        
        except Exception as e:
            logger.error(f"❌ Error analizando rama {branch.get('name')}: {e}")
            return self._fallback_branch_analysis(branch)
    
    def generate_cleanup_recommendations(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera un plan de limpieza priorizado
        Incluye: qué eliminar ya, qué esperar, por qué, riesgos
        """
        if not self.llm:
            return self._fallback_cleanup_plan(analysis_data)
        
        try:
            projects = analysis_data.get("projects", [])
            
            # Recopilar ramas inactivas
            inactive_branches = []
            for project in projects:
                for branch in project.get("branches", []):
                    if branch.get("status") == "INACTIVA":
                        inactive_branches.append({
                            "name": branch.get("name"),
                            "project": project.get("name"),
                            "days": branch.get("days_since_last_commit", -1),
                            "last_commit": branch.get("last_commit_date"),
                        })
            
            # Top 10 más inactivas
            top_inactive = sorted(
                inactive_branches,
                key=lambda x: x.get("days", 0),
                reverse=True
            )[:10]
            
            branches_summary = json.dumps(top_inactive, ensure_ascii=False, indent=2)
            
            prompt = ChatPromptTemplate.from_template("""
Eres un experto en DevOps limpieza de repositorios. Genera un plan de limpieza priorizado:

📋 RAMAS INACTIVAS A CONSIDERAR:
{branches_summary}

Genera un JSON con un plan de 3 fases:
{{
  "phase_1_delete_now": {{
    "priority": "🔴 CRÍTICA",
    "branches": ["rama1 - justificación", ...],
    "rationale": "Por qué hacer esto ahora",
    "risks": ["riesgo 1", ...],
    "estimated_time": "X minutos"
  }},
  "phase_2_review": {{
    "priority": "🟠 ALTA",
    "branches": ["rama1 - justificación", ...],
    "rationale": "Por qué revisar primero",
    "steps": ["paso 1", "paso 2", ...]
  }},
  "phase_3_archive": {{
    "priority": "🟡 MEDIA",
    "branches": ["rama1 - justificación", ...],
    "rationale": "Por qué archivar en lugar de eliminar",
    "automation": "Script recomendado"
  }}
}}
""")
            
            chain = prompt | self.llm
            result = chain.invoke({
                "branches_summary": branches_summary,
            })
            
            content = result.content
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    plan = json.loads(json_str)
                    logger.info("✅ Cleanup plan generado por LLM")
                    return plan
            except json.JSONDecodeError:
                return self._fallback_cleanup_plan(analysis_data)
        
        except Exception as e:
            logger.error(f"❌ Error generando cleanup plan: {e}")
            return self._fallback_cleanup_plan(analysis_data)
    
    # ============ FALLBACK (sin LLM) ============
    
    def _fallback_summary(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Resumen fallback sin LLM"""
        analysis = analysis_data.get("analysis", {})
        inactive = analysis.get("total_inactive_branches", 0)
        total = analysis.get("total_branches", 1)
        rate = (inactive / total * 100) if total > 0 else 0
        
        if rate > 50:
            risk_level = "🔴 CRÍTICO"
            health_score = 20
        elif rate > 30:
            risk_level = "🟠 ALTO"
            health_score = 40
        elif rate > 10:
            risk_level = "🟡 MEDIO"
            health_score = 60
        else:
            risk_level = "🟢 BAJO"
            health_score = 80
        
        return {
            "executive_summary": f"El repositorio tiene {rate:.1f}% de ramas inactivas ({inactive}/{total}). Esto indica {['buena salud', 'salud regular', 'baja salud'][min(2, int(rate/33))]}.",
            "risk_level": risk_level,
            "top_risks": [
                f"🌿 {inactive} ramas inactivas acumulan deuda técnica",
                f"📦 {analysis.get('total_obsolete_tags', 0)} tags obsoletos sin limpieza",
                f"⏰ {analysis.get('artifacts_expiring_soon', 0)} artefactos por expirar",
            ],
            "immediate_actions": [
                "1️⃣ Revisar ramas inactivas > 90 días",
                "2️⃣ Limpiar tags obsoletos",
                "3️⃣ Planificar expiración de artefactos",
            ],
            "health_score": health_score,
            "recommendations": [
                "Establecer política de limpieza de ramas",
                "Automatizar notificaciones de ramas inactivas",
                "Documentar criterios de retención",
            ]
        }
    
    def _fallback_branch_analysis(self, branch: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis fallback de rama sin LLM"""
        days = branch.get("days_since_last_commit", -1)
        status = branch.get("status", "DESCONOCIDO")
        
        if status == "INACTIVA" and days > 180:
            risk_level = "🔴 CRÍTICO"
            risk_score = 90
            action = "ELIMINAR"
        elif status == "INACTIVA" and days > 90:
            risk_level = "🟠 ALTO"
            risk_score = 70
            action = "REVISAR"
        elif status == "INACTIVA":
            risk_level = "🟡 MEDIO"
            risk_score = 40
            action = "ARCHIVAR"
        else:
            risk_level = "🟢 SEGURA"
            risk_score = 10
            action = "MANTENER"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "reason": f"Rama {status.lower()} con {days} días sin actividad",
            "evidence": [f"Último commit: {branch.get('last_commit_date')}"],
            "recommended_action": action,
            "priority": 5 - min(4, int(risk_score / 25)),
            "estimated_impact": f"Reduce deuda técnica en {min(100, days//30)}%"
        }
    
    def _fallback_cleanup_plan(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan fallback sin LLM"""
        return {
            "phase_1_delete_now": {
                "priority": "🔴 CRÍTICA",
                "branches": ["Ramas inactivas > 180 días"],
                "rationale": "Eliminar deuda técnica inmediata",
                "risks": ["Revisar MRs pendientes primero"],
                "estimated_time": "30 minutos"
            },
            "phase_2_review": {
                "priority": "🟠 ALTA",
                "branches": ["Ramas inactivas 90-180 días"],
                "rationale": "Validar que no hay trabajo en progreso",
                "steps": ["Listar PRs/MRs", "Contactar dueños", "Marcar para eliminación"]
            },
            "phase_3_archive": {
                "priority": "🟡 MEDIA",
                "branches": ["Ramas inactivas 30-90 días"],
                "rationale": "Archivar en repositorio histórico",
                "automation": "Usar script git-archive"
            }
        }
    
    def analyze_api_catalog(self, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analiza el catálogo de APIs y genera insights inteligentes
        Con timeout automático y fallback
        """
        if not self.llm:
            return self._fallback_api_insights(catalog)
        
        # Intentar con timeout de 10 segundos
        result = [None]
        exception = [None]
        
        def call_llm():
            try:
                specs_count = len(catalog.get("specs", []))
                code_files = catalog.get("total_code_files", 0)
                total_endpoints = catalog.get("total_endpoints", 0)
                
                prompt = ChatPromptTemplate.from_template("""
Eres un experto en arquitectura de APIs. Analiza el siguiente catálogo de APIs y proporciona insights:

📊 CATÁLOGO:
- Especificaciones encontradas: {specs_count}
- Archivos con APIs en código: {code_files}
- Total de endpoints: {total_endpoints}

Genera un JSON con una lista de insights en formato:
[
  {{
    "title": "Título del insight",
    "category": "Seguridad|Performance|Arquitectura|Documentación|Testing",
    "priority": "🔴 CRÍTICA|🟠 ALTA|🟡 MEDIA|🟢 BAJA",
    "description": "Descripción detallada",
    "impact": "Impacto de implementar este insight"
  }},
  ...
]

Genera entre 5 y 8 insights basados en los datos. Sé específico y accionable.
""")
                
                chain = prompt | self.llm | JsonOutputParser()
                output = chain.invoke({
                    "specs_count": specs_count,
                    "code_files": code_files,
                    "total_endpoints": total_endpoints
                })
                
                result[0] = output if isinstance(output, list) else [output]
            except Exception as e:
                logger.error(f"Error en LLM: {e}")
                exception[0] = e
        
        # Ejecutar en thread con timeout
        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()
        thread.join(timeout=10)  # Timeout de 10 segundos
        
        # Si se completó, retornar resultado
        if result[0] is not None:
            logger.info("✅ Insights generados por LLM")
            return result[0]
        
        # Si falló o se agotó el timeout, usar fallback
        logger.warning("⚠️ LLM timeout o error, usando fallback")
        return self._fallback_api_insights(catalog)
    
    def generate_cleanup_plan(self, catalog: Dict[str, Any], topology: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Genera plan de limpieza y optimización de APIs
        Con timeout automático y fallback
        """
        if not self.llm:
            return self._fallback_api_recommendations(catalog, topology)
        
        # Intentar con timeout de 10 segundos
        result = [None]
        exception = [None]
        
        def call_llm():
            try:
                specs = catalog.get("specs", [])
                code_files = catalog.get("total_code_files", 0)
                
                # Análisis de dependencias desde topología
                dependencies = topology.get("dependencies", {})
                dep_count = len(dependencies) if isinstance(dependencies, dict) else 0
                
                prompt = ChatPromptTemplate.from_template("""
Eres un experto en optimización de APIs y arquitectura. Genera un plan de limpieza y mejora:

📊 ANÁLISIS:
- APIs documentadas (specs): {specs_count}
- APIs en código: {code_files}
- Dependencias identificadas: {dep_count}

Genera un JSON con un array de recomendaciones en formato:
[
  {{
    "id": "rec-1",
    "title": "Título de la recomendación",
    "priority": "🔴 CRÍTICA|🟠 ALTA|🟡 MEDIA|🟢 BAJA",
    "effort": "Bajo|Medio|Alto",
    "impact": "Bajo|Medio|Alto",
    "description": "Descripción detallada",
    "steps": ["Paso 1", "Paso 2", ...],
    "owner": "Equipo|Rol responsable"
  }},
  ...
]

Genera entre 4 y 6 recomendaciones priorizadas. Sé específico y medible.
""")
                
                chain = prompt | self.llm | JsonOutputParser()
                output = chain.invoke({
                    "specs_count": len(specs),
                    "code_files": code_files,
                    "dep_count": dep_count
                })
                
                result[0] = output if isinstance(output, list) else [output]
            except Exception as e:
                logger.error(f"Error en LLM: {e}")
                exception[0] = e
        
        # Ejecutar en thread con timeout
        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()
        thread.join(timeout=10)  # Timeout de 10 segundos
        
        # Si se completó, retornar resultado
        if result[0] is not None:
            logger.info("✅ Recomendaciones generadas por LLM")
            return result[0]
        
        # Si falló o se agotó el timeout, usar fallback
        logger.warning("⚠️ LLM timeout o error, usando fallback")
        return self._fallback_api_recommendations(catalog, topology)
    
    def _fallback_api_insights(self, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Insights fallback para APIs sin LLM"""
        specs_count = len(catalog.get("specs", []))
        code_files = catalog.get("total_code_files", 0)
        endpoints = catalog.get("total_endpoints", 0)
        
        insights = []
        
        if specs_count == 0:
            insights.append({
                "title": "Falta documentación de especificaciones",
                "category": "Documentación",
                "priority": "🟠 ALTA",
                "description": f"No se encontraron especificaciones OpenAPI/Swagger. {code_files} APIs en código sin documentar.",
                "impact": "Mejorar documentación y descubrimiento de APIs"
            })
        
        if endpoints > 500:
            insights.append({
                "title": "Gran superficie de API",
                "category": "Arquitectura",
                "priority": "🟡 MEDIA",
                "description": f"Se identificaron {endpoints} endpoints. Considerar agrupar por dominio.",
                "impact": "Mejor mantenibilidad y control de versiones"
            })
        
        if code_files > 5 and specs_count == 0:
            insights.append({
                "title": "APIs no documentadas en código",
                "category": "Documentación",
                "priority": "🟠 ALTA",
                "description": f"Hay {code_files} archivos con APIs pero sin especificaciones formales.",
                "impact": "Generar especificaciones OpenAPI automáticas"
            })
        
        insights.append({
            "title": "Auditoría de seguridad recomendada",
            "category": "Seguridad",
            "priority": "🟠 ALTA",
            "description": "Revisar autenticación, autorización y validación en endpoints públicos.",
            "impact": "Reducir vulnerabilidades y exposición"
        })
        
        insights.append({
            "title": "Pruebas de integración",
            "category": "Testing",
            "priority": "🟡 MEDIA",
            "description": f"Implementar tests de integración para los {endpoints} endpoints.",
            "impact": "Mejorar confiabilidad y prevenir regresiones"
        })
        
        return insights
    
    def _fallback_api_recommendations(self, catalog: Dict[str, Any], topology: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recomendaciones fallback para APIs sin LLM"""
        return [
            {
                "id": "rec-1",
                "title": "Documentar APIs no especificadas",
                "priority": "🔴 CRÍTICA",
                "effort": "Alto",
                "impact": "Alto",
                "description": "Generar especificaciones OpenAPI para todas las APIs en código.",
                "steps": ["Auditar APIs", "Documentar especificaciones", "Validar con equipo"],
                "owner": "Arquitectura"
            },
            {
                "id": "rec-2",
                "title": "Establecer versionado de APIs",
                "priority": "🟠 ALTA",
                "effort": "Medio",
                "impact": "Alto",
                "description": "Implementar estrategia de versionado (v1, v2, etc).",
                "steps": ["Definir política", "Marcar endpoints", "Comunicar a clientes"],
                "owner": "Backend"
            },
            {
                "id": "rec-3",
                "title": "Implementar validación y sanitización",
                "priority": "🟠 ALTA",
                "effort": "Medio",
                "impact": "Alto",
                "description": "Validar inputs y sanitizar outputs en todos los endpoints.",
                "steps": ["Auditar validación actual", "Implementar schema validation", "Tests"],
                "owner": "Seguridad"
            },
            {
                "id": "rec-4",
                "title": "Consolidar endpoints duplicados",
                "priority": "🟡 MEDIA",
                "effort": "Medio",
                "impact": "Medio",
                "description": "Identificar y unificar APIs con funcionalidad similar.",
                "steps": ["Análisis de topología", "Propuesta", "Migración"],
                "owner": "Arquitectura"
            }
        ]

    def generate_insights(self, context: str) -> str:
        """Genera insights inteligentes basados en contexto de APIs"""
        if not self.llm:
            return self._fallback_insights(context)
        
        try:
            prompt = ChatPromptTemplate.from_template("""
Eres un experto en análisis de arquitecturas de APIs. 

Contexto: {context}

Genera 3-4 insights clave sobre este conjunto de APIs. Sé conciso pero profundo.
Formato: Usa viñetas con emojis relevantes. No uses JSON, devuelve texto plano.""")
            
            chain = prompt | self.llm
            result = chain.invoke({"context": context})
            return result.content if hasattr(result, 'content') else str(result)
        except Exception as e:
            logger.error(f"Error generando insights: {e}")
            return self._fallback_insights(context)
    
    def generate_recommendations(self, context: str) -> str:
        """Genera recomendaciones accionables"""
        if not self.llm:
            return self._fallback_recommendations(context)
        
        try:
            prompt = ChatPromptTemplate.from_template("""
Eres un arquitecto de APIs experimentado.

Contexto: {context}

Genera 3-4 recomendaciones prácticas para mejorar esta arquitectura de APIs.
Cada recomendación debe ser accionable y incluir beneficio esperado.
Formato: Usa viñetas numeradas. No uses JSON, devuelve texto plano.""")
            
            chain = prompt | self.llm
            result = chain.invoke({"context": context})
            return result.content if hasattr(result, 'content') else str(result)
        except Exception as e:
            logger.error(f"Error generando recomendaciones: {e}")
            return self._fallback_recommendations(context)
    
    def generate_risks(self, context: str) -> str:
        """Genera análisis de riesgos y vulnerabilidades"""
        if not self.llm:
            return self._fallback_risks(context)
        
        try:
            prompt = ChatPromptTemplate.from_template("""
Eres un especialista en seguridad de APIs.

Contexto: {context}

Identifica 3-4 riesgos potenciales en esta arquitectura de APIs.
Para cada riesgo: descripción, probabilidad (Alta/Media/Baja), impacto potencial.
Formato: Usa viñetas con nivel de riesgo (🔴 Alto/🟠 Medio/🟡 Bajo). Texto plano, sin JSON.""")
            
            chain = prompt | self.llm
            result = chain.invoke({"context": context})
            return result.content if hasattr(result, 'content') else str(result)
        except Exception as e:
            logger.error(f"Error analizando riesgos: {e}")
            return self._fallback_risks(context)
    
    def _fallback_insights(self, context: str) -> str:
        """Insights fallback sin LLM"""
        return """📊 Insights Basados en Datos:
• La arquitectura tiene múltiples endpoints que pueden ser optimizados
• Se detectan potenciales oportunidades de consolidación
• Recomendable realizar auditoría de documentación de APIs
• Considerar implementar rate limiting y validación de inputs"""
    
    def _fallback_recommendations(self, context: str) -> str:
        """Recomendaciones fallback sin LLM"""
        return """✅ Recomendaciones Prioritarias:
1. Implementar documentación OpenAPI completa para todas las APIs
2. Establecer versionado consistente (v1, v2, etc.)
3. Consolidar endpoints duplicados o funcionalidad solapada
4. Implementar validación y sanitización de inputs en todos los endpoints"""
    
    def _fallback_risks(self, context: str) -> str:
        """Análisis de riesgos fallback sin LLM"""
        return """⚠️ Riesgos Identificados:
🔴 Alto: APIs no documentadas pueden llevar a uso incorrecto
🟠 Medio: Falta de versionado podría romper clientes en actualizaciones
🟠 Medio: Endpoints duplicados generan mantenimiento innecesario
🟡 Bajo: Documentación incompleta afecta onboarding de desarrolladores"""


def get_llm_analyzer() -> LLMAnalyzer:
    """Factory para obtener instancia del analizador"""
    return LLMAnalyzer()
