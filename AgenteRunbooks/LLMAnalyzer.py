"""
LLMAnalyzer.py - Análisis Inteligente de Runbooks

Genera insights y validaciones usando LLM sobre los Runbooks generados:
- Análisis de Seguridad
- Simplificación
- Traducción
- Validación de Pasos
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

class RunbookAnalyzer:
    """Analizador de Runbooks usando LLM"""
    
    def __init__(self):
        """Inicializar el cliente LLM"""
        api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_API_BASE")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o-mini")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv("AZURE_API_VERSION", "2025-01-01-preview")
        
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
    
    def analyze_with_prompt(self, prompt: str) -> str:
        """Analiza usando un prompt personalizado"""
        if not self.llm:
            return "⚠️ LLM no configurado. Por favor configura las credenciales de Azure OpenAI."
        
        try:
            from langchain_core.prompts import ChatPromptTemplate
            
            template = ChatPromptTemplate.from_messages([
                ("system", "Eres un experto SRE y DevOps. Analizas documentación operativa y runbooks."),
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
    
    def generate_security_audit(self, runbook_content: str) -> str:
        """Genera una auditoría de seguridad del runbook"""
        prompt = f"""
        Analiza el siguiente Runbook desde una perspectiva de SEGURIDAD:
        
        {runbook_content[:5000]}
        
        Identifica:
        1. Comandos peligrosos (rm -rf, etc)
        2. Manejo de credenciales inseguro
        3. Faltan validaciones pre/post ejecución
        
        Responde en Markdown.
        """
        return self.analyze_with_prompt(prompt)


class LLMAnalyzer(RunbookAnalyzer):
    """Alias para compatibilidad"""
    pass
