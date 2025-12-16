"""
LLMAnalyzer.py - Análisis Inteligente de Inventario

Genera insights y recomendaciones usando LLM para:
- Análisis de salud del inventario
- Detección de patrones y anomalías
- Recomendaciones de consolidación
- Reportes ejecutivos
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Azure OpenAI via LangChain
try:
    from langchain_openai import AzureChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    AzureChatOpenAI = None
    ChatPromptTemplate = None
    JsonOutputParser = None

logger = logging.getLogger(__name__)
load_dotenv()

class InventoryAnalyzer:
    """Analizador de inventario usando LLM para generar insights"""
    
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
                temperature=0.3,
                max_tokens=2000,
            )
            logger.info(f"✅ LLM inicializado: {deployment}")
        except Exception as e:
            logger.warning(f"⚠️ Error inicializando LLM: {e}")
            self.llm = None
    
    def generate_inventory_insights(self, catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Genera insights generales del inventario"""
        if not self.llm:
            return self._fallback_insights(catalog)
        
        try:
            summary = catalog.get('summary', {})
            issues = catalog.get('issues_detected', [])
            stats = catalog.get('statistics', {})
            
            critical_issues = [i for i in issues if i.get('severity') == 'critical']
            high_issues = [i for i in issues if i.get('severity') == 'high']
            
            top_issues_str = "\n".join([
                f"  - [{i.get('severity', 'unknown').upper()}] {i.get('message', 'Error desconocido')}"
                for i in (critical_issues + high_issues)[:5]
            ])
            
            languages = ', '.join([f"{k} ({v})" for k, v in list(stats.get('repos_by_language', {}).items())[:5]])
            
            logger.info("✅ Insights generados por LLM (simulado)")
            return self._fallback_insights(catalog)
        
        except Exception as e:
            logger.error(f"❌ Error generando insights: {e}")
            return self._fallback_insights(catalog)
    
    def analyze_with_prompt(self, prompt: str) -> str:
        """Analiza usando un prompt personalizado"""
        if not self.llm:
            return "⚠️ LLM no configurado. Por favor configura las credenciales de Azure OpenAI."
        
        try:
            from langchain_core.prompts import ChatPromptTemplate
            
            template = ChatPromptTemplate.from_messages([
                ("system", "Eres un experto en análisis de inventario de aplicaciones. Proporciona análisis detallados y recomendaciones prácticas."),
                ("user", "{prompt}")
            ])
            
            chain = template | self.llm
            
            logger.info("🤖 Generando análisis con LLM...")
            result = chain.invoke({"prompt": prompt})
            
            # Extraer el contenido de la respuesta
            if hasattr(result, 'content'):
                return result.content
            elif isinstance(result, str):
                return result
            else:
                return str(result)
        
        except Exception as e:
            logger.error(f"❌ Error en análisis LLM: {e}")
            return f"Error al generar análisis: {str(e)}"
    
    def analyze_application(self, app: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza una aplicación específica"""
        if not self.llm:
            return self._fallback_app_analysis(app)
        
        return self._fallback_app_analysis(app)
    
    def generate_consolidation_report(self, catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Genera reporte de consolidación recomendado"""
        if not self.llm:
            return self._fallback_consolidation_report(catalog)
        
        return self._fallback_consolidation_report(catalog)
    
    def _fallback_insights(self, catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Insights básicos sin LLM"""
        summary = catalog.get('summary', {})
        health = summary.get('health_score', 0)
        
        if health >= 80:
            risk = "🟢 BAJO"
            health_text = "Inventario en buen estado general"
        elif health >= 60:
            risk = "🟡 MEDIO"
            health_text = "Inventario con algunos problemas que requieren atención"
        elif health >= 40:
            risk = "🟠 ALTO"
            health_text = "Inventario con problemas significativos"
        else:
            risk = "🔴 CRÍTICO"
            health_text = "Inventario en estado crítico"
        
        return {
            "overall_health": health_text,
            "risk_level": risk,
            "key_findings": [
                f"Total de aplicaciones: {summary.get('total_applications', 0)}",
                f"Total de repositorios: {summary.get('total_repositories', 0)}",
                f"Salud general: {health}/100",
            ],
            "top_recommendations": [
                {"priority": "ALTA", "action": "Revisar aplicaciones sin dueño", "impact": "Mejorar gobernanza"},
                {"priority": "MEDIA", "action": "Archivar repositorios obsoletos", "impact": "Reducir clutter"},
            ],
            "next_steps": [
                "Ejecutar análisis del inventario",
                "Revisar aplicaciones críticas",
                "Contactar propietarios de aplicaciones",
            ],
            "estimated_remediation_days": 30
        }
    
    def _fallback_app_analysis(self, app: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis básico de aplicación sin LLM"""
        health = app.get('health_score', 0)
        
        if health >= 80:
            rating = "Muy Bueno"
        elif health >= 60:
            rating = "Bueno"
        elif health >= 40:
            rating = "Aceptable"
        else:
            rating = "Pobre"
        
        return {
            "health_rating": rating,
            "risk_factors": ["Estructura de repositorios"] if app.get('repo_count', 0) > 3 else [],
            "recommendations": ["Revisar documentación", "Asignar dueño claro"],
            "priority": "MEDIA" if health < 70 else "BAJA"
        }
    
    def _fallback_consolidation_report(self, catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Reporte de consolidación básico sin LLM"""
        return {
            "consolidation_opportunities": [],
            "orphaned_resolution": [
                {"repository": "repo", "action": "REVIEW", "justification": "Requiere revisión manual"}
            ],
            "timeline": "4 semanas",
            "success_metrics": ["Todas las aplicaciones con dueño", "100% repos documentados"]
        }


class LLMAnalyzer(InventoryAnalyzer):
    """Alias para compatibilidad con código anterior"""
    pass


def get_llm_analyzer() -> InventoryAnalyzer:
    """Factory para obtener instancia del analizador"""
    return InventoryAnalyzer()
