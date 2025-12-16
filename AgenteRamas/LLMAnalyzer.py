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
from collections import Counter

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

class AzureOpenAICompat:
    """
    Adaptador para exponer la interfaz OpenAI (chat.completions.create) usando AzureChatOpenAI vía AzureLLMProvider.
    """
    class Chat:
        def __init__(self, azure_llm):
            self.completions = self.Completions(azure_llm)

        class Completions:
            def __init__(self, azure_llm):
                self.azure_llm = azure_llm

            def create(self, model, messages, temperature=0.1, max_tokens=None, **kwargs):
                # AzureChatOpenAI espera una lista de mensajes en formato [{"role": ..., "content": ...}]
                # y devuelve un objeto con .content (o .generations[0].text)
                # Simulamos la respuesta de OpenAI
                prompt = ""
                for m in messages:
                    if m["role"] == "system":
                        prompt += f"SYSTEM: {m['content']}\n"
                    elif m["role"] == "user":
                        prompt += f"USER: {m['content']}\n"
                    elif m["role"] == "assistant":
                        prompt += f"ASSISTANT: {m['content']}\n"
                # Llama al modelo de Azure
                response = self.azure_llm.invoke(messages, temperature=temperature)
                # Simula la estructura de respuesta de OpenAI
                class Choice:
                    def __init__(self, content):
                        self.message = type("msg", (), {"content": content})
                class Response:
                    def __init__(self, content):
                        self.choices = [Choice(content)]
                        self.usage = None  # Opcional: puedes mapear tokens si lo necesitas
                return Response(response.content if hasattr(response, "content") else str(response))
    def __init__(self, azure_llm):
        self.chat = self.Chat(azure_llm)

class LLMAnalyzer:
    """Analizador que usa LLM para generar insights y recomendaciones"""
    
    def __init__(self, llm_provider: Optional[Any] = None):
        if llm_provider is not None:
            self.llm = AzureOpenAICompat(llm_provider)
        else:
            self.llm = None
    
    def generate_executive_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera un resumen ejecutivo por grupo/proyecto
        Incluye: estado general, top riesgos, acciones inmediatas
        """
        branches = state.get("branches", [])
        maintenance = state.get("maintenance_report")

        if not self.llm:
            return self._fallback_summary(state)
        
        try:            
            # Preparar datos para el LLM
            inactive_branches = len([b for b in branches if b.get('status') == 'INACTIVA'])
            total_branches = len(branches)
            obsolete_tags = len(maintenance.get('tags_obsoletos', []))
            expiring_artifacts = len(maintenance.get('artefactos_por_expirar', []))
            expired_artifacts = len(maintenance.get('artefactos_expirados', []))
            
            inactivity_rate = (inactive_branches / total_branches * 100) if total_branches > 0 else 0
            role = "Eres un experto en gestión de repositorios Git."
            prompt = """
Analiza los siguientes datos y genera un resumen ejecutivo:

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
  "executive_summary": "Genera un resumen ejecutivo conciso (1–2 párrafos) con KPIs clave y 3 recomendaciones de alto nivel. 
  Indica claramente las fuentes de datos utilizadas (ramas, artefactos, versiones) si es posible.",
  "risk_level": "🔴 CRÍTICO|🟠 ALTO|🟡 MEDIO|🟢 BAJO",
  "top_risks": ["riesgo 1 con explicación", "riesgo 2...", ...],
  "immediate_actions": ["acción 1 con prioridad", "acción 2...", ...],
  "health_score": 0-100,
  "recommendations": ["recomendación 1", "recomendación 2", ...]
}}
"""
            
            # Contar ramas inactivas por proyecto
            inactive_counts = Counter()

            for item in branches:
                status = (item.get("status") or "").upper()
                if status == "INACTIVA":
                    # Usamos (project_id, project) como clave para identificar un proyecto
                    key = (item["project_id"], item["project"])
                    inactive_counts[key] += 1

            # Obtener los 3 proyectos con más ramas inactivas
            top_projects_list = inactive_counts.most_common(3)
            
            top_projects_str = "\n".join([f"  - {name}: {count} inactivas" for name, count in top_projects_list])
            
            header = f"Informe de análisis de repositorio - caso: Genera un resumen ejecutivo por grupo/proyecto\n"
            data_summary = {
                "num_projects": len(state.get('project_ids', [])),
                "total_branches": total_branches,
                "inactive_branches": inactive_branches,
                "inactivity_rate": inactivity_rate,
                "obsolete_tags": obsolete_tags,
                "expiring_artifacts": expiring_artifacts,
                "expired_artifacts": expired_artifacts,
                "top_projects": top_projects_str,
            }
            body = "\nDatos relevantes:\n" + json.dumps(data_summary)

            prompt = (
                header
                + prompt
                + body
            )

            content = self._call_llm(role, prompt)

            # chain = prompt | self.llm
            # result = chain.invoke({
            #     "num_projects": len(state.get('project_ids', [])),
            #     "total_branches": total_branches,
            #     "inactive_branches": inactive_branches,
            #     "inactivity_rate": inactivity_rate,
            #     "obsolete_tags": obsolete_tags,
            #     "expiring_artifacts": expiring_artifacts,
            #     "expired_artifacts": expired_artifacts,
            #     "top_projects": top_projects_str,
            # })
            
            # Parsear JSON
            #content = result.content
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    summary = json.loads(json_str)
                    logger.warning("✅ Executive summary generado por LLM")
                    return summary
            except json.JSONDecodeError:
                logger.warning("⚠️ Error parseando JSON del LLM")
                return self._fallback_summary(state)
        
        except Exception as e:
            logger.error(f"❌ Error generando executive summary: {e}")
            return self._fallback_summary(state)
    
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
            
            role = "Eres un experto en limpieza de repositorios"
            prompt = """
Analiza esta rama Git:

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
"""
            header = f"Informe de análisis de repositorio - caso: Analiza la salud de una rama individual\n"
            data_summary = {
                "branch_name": branch.get("name", "unknown"),
                "project_name": project_name,
                "status": status,
                "last_commit": last_commit,
                "days_since_commit": days_since_commit,
            }
            body = "\nDatos relevantes:\n" + json.dumps(data_summary)

            prompt = (
                header
                + prompt
                + body
            )

            content = self._call_llm(role, prompt)
            # chain = prompt | self.llm
            # result = chain.invoke({
            #     "branch_name": branch.get("name", "unknown"),
            #     "project_name": project_name,
            #     "status": status,
            #     "last_commit": last_commit,
            #     "days_since_commit": days_since_commit,
            # })
            
            # content = result.content
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
            
            role = "Eres un experto en DevOps limpieza de repositorios."
            prompt = """
Genera un plan de limpieza del repositorio priorizado, teniendo en cuenta las siguientes directrices. Proporciona un análisis detallado y justificaciones claras para cada acción recomendada.

Consideraciones Previas:
📋 Ramas que han sido inactivas por más de X meses: {branches_summary}

Plan de Limpieza JSON:
{{
  "phase_1_delete_now": {{
    "priority": "🔴 CRÍTICA",
    "branches": ["rama1 - justificación", ...],
    "rationale": "Por qué hacer esto ahora",
    "risks": ["riesgo 1", ...],
    "estimated_time": "X minutos",
    "backup_required": true, // Indica si se requiere un respaldo previo
    "dependencies": ["rama2", ...]  // Otras ramas que dependen de estas
  }},
  "phase_2_review": {
    "priority": "🟠 ALTA",
    "branches": ["rama1 - justificación", ...],
    "rationale": "Por qué revisar primero",
    "steps": ["paso 1", "paso 2", ...],
    "review_criteria": ["criterio 1", ...], // Criterios específicos para la revisión
    "stakeholders_involved": ["persona1", "equipo B"] // Responsables de la revisión
  }},
  "phase_3_archive": {{
    "priority": "🟡 MEDIA",
    "branches": ["rama1 - justificación", ...],
    "rationale": "Por qué archivar en lugar de eliminar",
    "automation": "Script recomendado",
    "retention_policy": "Periodo de retención en el archivo"
  }}
}}
Instrucciones Adicionales:

- Incluye métricas recientes de uso y actividad del repositorio.
- Considera el impacto potencial en el desarrollo en curso.
- Asegura la documentación adecuada de los cambios propuestos.
"""
            header = f"Informe de análisis de repositorio - caso: Genera un plan de limpieza priorizado\n"
            data_summary = {
                "branches_summary": branches_summary,
            }
            body = "\nDatos relevantes:\n" + json.dumps(data_summary)
            prompt = (
                header
                + prompt
                + body
            )
            content = self._call_llm(role, prompt)
            # chain = prompt | self.llm
            # result = chain.invoke({
            #     "branches_summary": branches_summary,
            # })
            
            # content = result.content
            try:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    plan = json.loads(json_str)
                    logger.warning("✅ Cleanup plan generado por LLM")
                    return plan
            except json.JSONDecodeError:
                return self._fallback_cleanup_plan(analysis_data)
        
        except Exception as e:
            logger.error(f"❌ Error generando cleanup plan: {e}")
            return self._fallback_cleanup_plan(analysis_data)
    
    def _call_llm(self, role: str, prompt: str) -> str:
        """
        Llama al proveedor de LLM si está disponible.
        En modo desarrollo sin proveedor, devuelve una versión "mock" basada en el prompt.
        """
        logger.info("llamado a análisis")
        if self.llm is None:
            # Desarrollo: devuelve un mock razonable sin exponer datos sensibles.
            return (
                "Respuesta simulada del LLM (modo desarrollo): "
                "Este resultado sirve como placeholder para pruebas de integración. "
                "La respuesta real deberá ser generada por un servicio LLM cuando esté disponible."
            )

        # Intentar un acceso seguro al proveedor
        try:
            messages = [
                {"role": "system", "content": role},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                temperature=0.1
            )

            # Limpiar respuesta para obtener solo JSON
            content = response.choices[0].message.content.strip()

            logger.info(f"RESPUESTA LLM: {content}")
            
            return content
        except Exception as e:
            logger.error(f"Error invoking LLM: {e}")
            return f"Error invoking LLM: {e}"

    # ============ FALLBACK (sin LLM) ============
    
    def _fallback_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Resumen fallback sin LLM"""
        branches = state.get("branches", [])
        maintenance = state.get("maintenance_report")

        inactive = len([b for b in branches if b.get('status') == 'INACTIVA'])
        total = len(branches)
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
                f"📦 {len(maintenance.get('tags_obsoletos', []))} tags obsoletos sin limpieza",
                f"⏰ {len(maintenance.get('artefactos_por_expirar', []))} artefactos por expirar",
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
    
def _call_llm(self, prompt: str) -> str:
        """
        Llama al proveedor de LLM si está disponible.
        En modo desarrollo sin proveedor, devuelve una versión "mock" basada en el prompt.
        """
        logger.info("llamado a análisis")
        if self.client is None:
            # Desarrollo: devuelve un mock razonable sin exponer datos sensibles.
            return (
                "Respuesta simulada del LLM (modo desarrollo): "
                "Este resultado sirve como placeholder para pruebas de integración. "
                "La respuesta real deberá ser generada por un servicio LLM cuando esté disponible."
            )

        # Intentar un acceso seguro al proveedor
        try:
            messages = [
                {"role": "system", "content": "Eres un experto en análisis de documentos técnicos. Extrae información estructurada de documentos AF. Devuelve SOLO JSON válido."},
                {"role": "user", "content": prompt}
            ]
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                temperature=0.1
            )

            # Limpiar respuesta para obtener solo JSON
            content = response.choices[0].message.content.strip()

            logger.info(f"RESPUESTA LLM: {content}")
            
            return content
        except Exception as e:
            logger.error(f"Error invoking LLM: {e}")
            return f"Error invoking LLM: {e}"


def get_llm_analyzer(llm_provider: Optional[Any] = None) -> LLMAnalyzer:
    """Factory para obtener instancia del analizador"""
    return LLMAnalyzer(llm_provider)
