import os
import json
import logging
from typing import Dict, Any, Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

# Configurar logger
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class DependencyLLMAnalyzer:
    """
    Analizador on-demand para dependencias usando Azure OpenAI.
    Usa configuración manual para coincidir con LLMAnalyzer.py y bypass Proxy si es necesario.
    """
    
    def __init__(self):
        # Cargar explicitamente variables como en el referente
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini") # Fallback default
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        # Si no hay endpoint directo, intentar fallback a API_BASE pero preferir ENDPOINT
        if not self.endpoint and os.getenv("AZURE_API_BASE"):
             self.endpoint = os.getenv("AZURE_API_BASE")

        if not self.api_key or not self.endpoint:
            logger.warning(f"⚠️ Credenciales Azure OpenAI faltantes. Endpoint: {self.endpoint}")
            self.llm = None
            return

        try:
            self.llm = AzureChatOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.endpoint,
                deployment_name=self.deployment,
                api_version=self.api_version,
                temperature=0.3,
                max_tokens=2000
            )
            logger.info(f"✅ LLM Analyzer inicializado: {self.deployment} @ {self.endpoint}")
        except Exception as e:
            logger.error(f"❌ Error inicializando LLM: {e}")
            self.llm = None

    def analyze_security(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza riesgos de seguridad en las dependencias"""
        if not self.llm:
            return self._fallback_error("LLM no disponible")

        prompt = ChatPromptTemplate.from_template("""
        Eres un experto en ciberseguridad aplicada a arquitecturas de software.
        Analiza el siguiente contexto de dependencias y servicios:
        
        📊 DATOS:
        {data}
        
        Identifica vectores de ataque y riesgos.
        Tu respuesta debe ser un JSON estrictamente con este formato:
        {{
            "risk_level": "CRÍTICO|ALTO|MEDIO|BAJO",
            "score": 0-100,
            "findings": [
                {{ "title": "...", "description": "...", "severity": "..." }}
            ],
            "recommendations": ["..."]
        }}
        """)
        
        return self._invoke_chain(prompt, {"data": json.dumps(context_data, indent=2)})

    def analyze_architecture(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza la calidad arquitectónica"""
        if not self.llm:
            return self._fallback_error("LLM no disponible")
            
        prompt = ChatPromptTemplate.from_template("""
        Eres un arquitecto de software senior.
        Evalúa la calidad arquitectónica (acoplamiento, cohesión, complejidad) de este grafo de dependencias:
        
        📊 DATOS:
        {data}
        
        Tu respuesta debe ser un JSON estrictamente con este formato:
        {{
            "quality_score": 0-100,
            "assessment": "Resumen ejecutivo...",
            "strengths": ["..."],
            "weaknesses": ["..."],
            "design_patterns_detected": ["..."]
        }}
        """)
        
        return self._invoke_chain(prompt, {"data": json.dumps(context_data, indent=2)})
        
    def analyze_improvements(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sugiere oportunidades de mejora tecnológica"""
        if not self.llm:
            return self._fallback_error("LLM no disponible")
            
        prompt = ChatPromptTemplate.from_template("""
        Eres un consultor tecnológico experto.
        Sugiere mejoras, modernización de stack u optimizaciones para este proyecto:
        
        📊 DATOS:
        {data}
        
        Tu respuesta debe ser un JSON estrictamente con este formato:
        {{
            "opportunities": [
                {{
                    "title": "...",
                    "impact": "ALTO|MEDIO|BAJO",
                    "effort": "ALTO|MEDIO|BAJO",
                    "rationale": "..."
                }}
            ]
        }}
        """)
        
        return self._invoke_chain(prompt, {"data": json.dumps(context_data, indent=2)})

    def _invoke_chain(self, prompt, inputs):
        """Helper para invocar el LLM y parsear JSON"""
        try:
            chain = prompt | self.llm | JsonOutputParser()
            return chain.invoke(inputs)
        except Exception as e:
            logger.error(f"Error invocando LLM: {e}")
            return self._fallback_error(str(e))

    def _fallback_error(self, msg):
        return {"error": True, "message": msg}

# Instancia global
analyzer = DependencyLLMAnalyzer()
