"""
Insights Engine for repository analytics powered by LLMs.

This module provides a lightweight, pluggable way to generate high-level insights
from the data produced by the repository analysis (branches, tags, releases,
artifacts, maintenance reports, etc.). It is designed to work even if an LLM
provider is not available (for development), returning well-structured prompts
and placeholder responses that can be swapped with a real LLM later.

Key ideas:
- Data source agnostic: consumes the state/data produced by AS_langgraphEnabler.py / api.py.
- Prompts are separated from execution: easy to adapt prompts without touching orchestration logic.
- Pluggable LLM provider: if a provider is passed in, it will be used; otherwise, returns deterministic placeholders.
- Output contracts: functions return dictionaries with predictable shapes for easy integration.

Usage (example):
    engine = InsightsEngine(llm_provider=azure_provider)  # provider optional
    summary = engine.executive_summary(state)
    risks = engine.risk_assessment(state)
    plan = engine.maintenance_plan(state)
    insights = engine.generate_all_insights(state)

Classes
- InsightsEngine: core orchestration + simple prompt templates.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import json

logger = logging.getLogger(__name__)

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

class InsightsEngine:
    """
    Engine to generate insights from a repository analysis state.

    Parameters:
      llm_provider: Optional object exposing a compatible LLM interface. If not provided, the engine will
                    return deterministic placeholder responses suitable for development and UX flows.
    """

    def __init__(self, llm_provider: Optional[Any] = None):
        self.client = AzureOpenAICompat(llm_provider)

    # Internal helpers
    @staticmethod
    def _to_plain_text(state: Dict[str, Any]) -> str:
        """
        Simple helper to render the state in a compact, human-readable form
        to be embedded into prompts. This avoids dumping huge payloads in prompts.
        """
        lines = []
        lines.append(f"Proyectos: {len(state.get('projects_meta', []))}")
        lines.append(f"Ramas: {len(state.get('branches', []))}")
        lines.append(f"Tags: {len(state.get('tags', []))}")
        lines.append(f"Artefactos: {len(state.get('artifacts', []))}")
        if state.get("maintenance_report"):
            lines.append("Mantenimiento reportado: disponible")
        else:
            lines.append("Mantenimiento reportado: no disponible")
        return "\n".join(lines)

    def _build_prompt(self, kind: str, state: Dict[str, Any]) -> str:
        """
        Build a simple, case-specific prompt for the given kind of insight.
        kind can be: 'executive_summary', 'risk_assessment', 'maintenance_plan'
        """
        header = f"Informe de análisis de repositorio - caso: {kind}\n"
        data_summary = self._to_plain_text(state)
        body = "\nDatos relevantes:\n" + data_summary

        if kind == "executive_summary":
            prompt = (
                header
                + "Genera un resumen ejecutivo conciso (1–2 párrafos) con KPIs clave y 3 recomendaciones de alto nivel. "
                + "Indica claramente las fuentes de datos utilizadas (ramas, artefactos, versiones) si es posible.\n"
                + body
            )
        elif kind == "risk_assessment":
            prompt = (
                header
                + "Identifica riesgos principales basados en ramas inactivas, artefactos próximos a expirar y versiones obsoletas. "
                + "Asigna una prioridad (alta/media/baja) y propone mitigaciones accionables para cada ítem relevante. "
                + "Presenta una lista estructurada con título, riesgo, impacto, probabilidad y plan de mitigación.\n"
                + body
            )
        elif kind == "maintenance_plan":
            prompt = (
                header
                + "Genera un plan de mantenimiento por proyecto con tareas priorizadas, responsables tentativos y fechas de entrega. "
                + "Incluye dependencias y dependencias críticas identificadas durante el análisis. \n"
                + body
            )
        else:
            prompt = header + body
        return prompt

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

    # Public factory methods
    def executive_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Devuelve un resumen ejecutivo como diccionario con la clave 'content'.
        """
        logger.warning("llamado a executive_summary")
        prompt = self._build_prompt("executive_summary", state)
        content = self._call_llm(prompt)
        return {"type": "executive_summary", "content": content}

    def risk_assessment(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Devuelve un dict con el análisis de riesgos.
        """
        logger.warning("llamado a risk_assessment")
        prompt = self._build_prompt("risk_assessment", state)
        content = self._call_llm(prompt)
        
        return {"type": "risk_assessment", "content": content}

    def maintenance_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Devuelve un plan de mantenimiento por proyecto.
        """
        logger.warning("llamado a maintenance_plan")
        prompt = self._build_prompt("maintenance_plan", state)
        content = self._call_llm(prompt)
        return {"type": "maintenance_plan", "content": content}

    def generate_all_insights(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera todos los insights (executive_summary, risk_assessment, maintenance_plan)
        y los devuelve en una estructura consolidada.
        """
        return {
            "executive_summary": self.executive_summary(state),
            "risk_assessment": self.risk_assessment(state),
            "maintenance_plan": self.maintenance_plan(state),
        }


__all__ = ["InsightsEngine"]
