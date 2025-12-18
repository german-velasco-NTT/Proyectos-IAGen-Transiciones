"""
AS_langgraphEnabler.py - Runbook Generator Orchestrator

Motor de orquestación basado en LangGraph que convierte tickets de soporte
en Runbooks operativos estandarizados utilizando LLMs.
"""

import os
import json
from typing import Dict, List, Optional, Any, TypedDict
from dataclasses import dataclass, asdict
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# LangGraph & LangChain
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN & MODELOS
# ============================================================

@dataclass
class RunbookConfig:
    input_text: str
    context: Optional[str] = None
    output_dir: str = "./outputs"
    
class RunbookState(TypedDict):
    """Estado del grafo de generación de runbooks"""
    config: RunbookConfig
    raw_tickets: str
    identified_issues: List[Dict[str, Any]]
    clustered_patterns: List[Dict[str, Any]]
    runbook_draft: str
    runbook_content: str
    status: str
    error: Optional[str]

# ============================================================
# PROVIDER AZURE (Simplificado)
# ============================================================

def get_llm():
    """Obtiene instancia de AzureChatOpenAI desde variables de entorno"""
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4"),
        openai_api_version=os.getenv("AZURE_API_VERSION", "2023-05-15"),
        azure_endpoint=os.getenv("AZURE_API_BASE"),
        api_key=os.getenv("AZURE_API_KEY"),
        temperature=0.2
    )

# ============================================================
# NODOS DEL GRAFO
# ============================================================

def node_ingest_data(state: RunbookState) -> RunbookState:
    """Nodo 1: Ingesta y limpieza básica"""
    logger.info("📝 Ingestando datos...")
    try:
        raw = state["config"].input_text
        context = state["config"].context or ""
        
        # Aquí se podría añadir lógica de limpieza, anonimización básica, etc.
        combined_input = f"CONTEXTO:\n{context}\n\nDATOS CRUDOS:\n{raw}"
        
        state["raw_tickets"] = combined_input
        state["status"] = "ingested"
    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        
    return state

def node_analyze_patterns(state: RunbookState) -> RunbookState:
    """Nodo 2: Identificar patrones y agrupación de incidentes"""
    logger.info("🔍 Analizando patrones en tickets...")
    if state.get("status") == "failed": return state
    
    try:
        llm = get_llm()
        input_text = state["raw_tickets"][:15000] # Truncar para evitar limites de tokens por ahora
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Eres un experto Analista de Soporte Técnico (SRE). Tu trabajo es analizar logs de tickets y detectar el problema raíz recurrente."),
            ("human", """
            Analiza el siguiente texto proveniente de tickets de soporte o documentación dispersa.
            Identifica el problema principal (Root Cause) y los síntomas comunes.
            
            Entrada:
            {input_text}
            
            Salida JSON esperada:
            {{
                "main_issue": "Título descriptivo del problema",
                "symptoms": ["síntoma 1", "síntoma 2"],
                "root_cause_analysis": "Explicación técnica de la causa probable",
                "affected_components": ["componente A", "componente B"]
            }}
            """)
        ])
        
        chain = prompt | llm
        response = chain.invoke({"input_text": input_text})
        
        # Parseo simple (asumiendo que el modelo devuelve JSON en el contenido)
        content = response.content.replace("```json", "").replace("```", "").strip()
        try:
            analysis = json.loads(content)
        except:
             # Fallback simple
            analysis = {"main_issue": "Análisis IA (Raw)", "root_cause_analysis": content}
        
        state["identified_issues"] = [analysis] # Por ahora lista de 1, ampliable a multiples
        state["status"] = "analyzed"
        
    except Exception as e:
        logger.error(f"Error analizando patrones: {e}")
        # Fallback manual
        state["identified_issues"] = [{
            "main_issue": "Error desconocido detectado en logs",
            "symptoms": ["Indeterminado"],
            "root_cause_analysis": "No se pudo determinar con IA",
            "affected_components": []
        }]
    
    return state

def node_generate_runbook(state: RunbookState) -> RunbookState:
    """Nodo 3: Generar contenido Markdown del Runbook (SOP)"""
    logger.info("✍️ Generando Runbook SOP...")
    if state.get("status") == "failed": return state
    
    try:
        llm = get_llm()
        issue_data = state["identified_issues"][0]
        original_text = state["raw_tickets"][:10000]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Eres un Ingeniero de DevOps Senior redactando documentación operativa (Runbooks)."),
            ("human", """
            Basado en el análisis del problema: {issue_json}
            
            Y teniendo en cuenta los detalles técnicos crudos:
            {raw_text}
            
            Genera un RUNBOOK OPERATIVO PROFESIONAL en formato Markdown.
            
            Estructura requerida:
            # [Título del Runbook]
            
            ## 1. Descripción del Incidente
            (Qué sucede, síntomas, severidad)
            
            ## 2. Diagnóstico Inicial
            (Comandos para verificar el estado, logs a revisar)
            
            ## 3. Solución Paso a Paso (SOP)
            (Lista numerada precisa de comandos o acciones guiadas)
            
            ## 4. Validación
            (Cómo saber que se arregló)
            
            ## 5. Rollback
            (Qué hacer si falla la solución)
            
            Usa bloques de código para comandos. Sé directo y técnico.
            """)
        ])
        
        chain = prompt | llm
        response = chain.invoke({
            "issue_json": json.dumps(issue_data),
            "raw_text": original_text
        })
        
        state["runbook_content"] = response.content
        state["status"] = "generated"
        
    except Exception as e:
        logger.error(f"Error generando runbook: {e}")
        state["error"] = str(e)
        state["status"] = "failed"
        
    return state

# ============================================================
# ORQUESTADOR
# ============================================================

class RunbookGeneratorOrchestrator:
    def __init__(self):
        # Definir Grafo
        workflow = StateGraph(RunbookState)
        
        workflow.add_node("ingest", node_ingest_data)
        workflow.add_node("analyze", node_analyze_patterns)
        workflow.add_node("generator", node_generate_runbook)
        
        workflow.set_entry_point("ingest")
        workflow.add_edge("ingest", "analyze")
        workflow.add_edge("analyze", "generator")
        workflow.add_edge("generator", END)
        
        self.app = workflow.compile()
        
    def run(self, config: RunbookConfig) -> Dict[str, Any]:
        """Ejecuta el flujo completo"""
        initial_state = RunbookState(
            config=config,
            raw_tickets="",
            identified_issues=[],
            clustered_patterns=[],
            runbook_draft="",
            runbook_content="",
            status="pending",
            error=None
        )
        
        final_state = self.app.invoke(initial_state)
        
        return {
            "status": final_state["status"],
            "runbook_content": final_state.get("runbook_content"),
            "issues_detected": final_state.get("identified_issues"),
            "error": final_state.get("error")
        }
