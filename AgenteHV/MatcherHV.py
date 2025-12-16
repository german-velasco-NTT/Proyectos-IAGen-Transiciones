"""
Esqueleto de un agente en LangGraph para sugerir CVs de SharePoint dados
un perfil objetivo. Incluye stubs de tools, estado, nodos y grafo.

▶️ INSTRUCCIONES DE INTEGRACIÓN (resumen)
- Reemplaza los stubs de tools (sp_* / pdf_* / index_*) con implementaciones reales
  contra Microsoft Graph/SharePoint y tu índice (BM25 + embeddings).
- Sustituye LLMStub por un cliente real (p. ej., langchain_openai.ChatOpenAI).
- Agrega autenticación, logging estructurado y trazas según tu plataforma.

Requisitos mínimos:
    pip install langgraph langchain langchain-openai typing_extensions
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, TypedDict, Annotated
from datetime import datetime, timedelta
import math

# LangGraph core
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# ---------------------------------------------------------------------------
# 0) STUBS / TOOLS (reemplazar por integraciones reales)
# ---------------------------------------------------------------------------

def sp_search_cvs(query_text: str, top_k: int = 50, filters: Optional[Dict] = None) -> List[Dict]:
    """Búsqueda híbrida en el índice (STUB). Devuelve candidatos iniciales.
    Cada item: {file_id, name, url, score_init}
    """
    # TODO: Integrar con tu índice (Azure Cognitive Search/Elasticsearch + embeddings)
    return [
        {"file_id": "cv_001", "name": "Maria_Perez.pdf", "url": "https://sharepoint/site/cv_001", "score_init": 0.72},
        {"file_id": "cv_002", "name": "Juan_Lopez.pdf", "url": "https://sharepoint/site/cv_002", "score_init": 0.69},
        {"file_id": "cv_003", "name": "Ana_Ruiz.pdf", "url": "https://sharepoint/site/cv_003", "score_init": 0.66},
    ][:top_k]


def sp_get_metadata(file_id: str) -> Dict:
    """Obtiene metadatos desde SharePoint (STUB)."""
    # TODO: Usar Microsoft Graph API para leer metadatos personalizados
    meta = {
        "cv_001": {"candidate_name": "María Pérez", "location": "Bogotá", "languages": ["ES", "EN-B2"],
                    "certifications": ["DP-203"], "years_experience": 6,
                    "updated_at": (datetime.utcnow() - timedelta(days=120)).isoformat()},
        "cv_002": {"candidate_name": "Juan López", "location": "Medellín", "languages": ["ES", "EN-B1"],
                    "certifications": [], "years_experience": 5,
                    "updated_at": (datetime.utcnow() - timedelta(days=420)).isoformat()},
        "cv_003": {"candidate_name": "Ana Ruiz", "location": "Bogotá", "languages": ["ES", "EN-C1"],
                    "certifications": ["AZ-900"], "years_experience": 4,
                    "updated_at": (datetime.utcnow() - timedelta(days=60)).isoformat()},
    }
    return meta.get(file_id, {})


def index_highlight(profile_text: str, file_id: str, top_passages: int = 5) -> List[Dict]:
    """Regresa pasajes relevantes (página + snippet) (STUB)."""
    # TODO: Implementar con tu motor de búsqueda/índice con posiciones por página
    return [
        {"page": 2, "snippet": "Experiencia con Spark y Databricks en Azure (3 años)", "match_terms": ["Spark", "Databricks", "Azure"]},
        {"page": 3, "snippet": "Inglés B2 certificado", "match_terms": ["Inglés B2"]},
    ][:top_passages]


def pdf_read_pages(file_id: str, pages: List[int], ocr: bool = False) -> List[Dict]:
    """Lee texto de páginas específicas del PDF (STUB)."""
    # TODO: Integrar con lector PDF + OCR si escaneado (Azure Form Recognizer, Tesseract, etc.)
    return [{"page": p, "text": f"[Texto simulado de la página {p} del {file_id}]"} for p in pages]


def open_in_sharepoint(file_id: str) -> Dict:
    """Devuelve URL abrible (STUB)."""
    return {"url": f"https://sharepoint/site/{file_id}"}


def feedback_log(record: Dict) -> str:
    """Persiste feedback (STUB)."""
    # TODO: Guardar en base/telemetría
    return "ok"


# ---------------------------------------------------------------------------
# 1) UTILIDADES
# ---------------------------------------------------------------------------

def parse_cefr(level: str) -> float:
    """Mapea niveles de idioma (CEFR aproximado) a escala 0..1."""
    m = level.upper().strip()
    order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    return (order.index(m) / (len(order) - 1)) if m in order else 0.0


def days_since(iso_dt: str) -> int:
    try:
        dt = datetime.fromisoformat(iso_dt)
        return (datetime.utcnow() - dt).days
    except Exception:
        return 10_000


def normalize_skills(text: str) -> Set[str]:
    """Normaliza skills simples desde el perfil. (Ejemplo mínimo)"""
    raw = {t.strip().lower() for t in text.replace(";", ",").split(",") if t.strip()}
    # Sinónimos básicos (extiende esta tabla en producción)
    synonyms = {
        "pyspark": "spark",
        "azure data factory": "adf",
        "adf": "adf",
        "microsoft azure": "azure",
        "azure synapse": "synapse",
    }
    out = set()
    for r in raw:
        out.add(synonyms.get(r, r))
    return out


# ---------------------------------------------------------------------------
# 2) ESTADO DEL GRAFO
# ---------------------------------------------------------------------------
class Criterios(TypedDict, total=False):
    must_have: Set[str]
    nice_to_have: Set[str]
    years_min: Optional[int]
    idioma_min: Optional[str]   # p.ej. "B2"
    ubicacion: Optional[str]
    pesos: Dict[str, float]     # {skills, experiencia, industria, idiomas, certs}
    top_k: int
    umbral: float


class State(TypedDict, total=False):
    perfil_texto: str
    criterios: Criterios
    candidatos_iniciales: List[Dict]
    candidatos_filtrados: List[Dict]
    evidencias: Dict[str, List[Dict]]
    rankeados: List[Dict]
    respuesta: Dict
    needs_clarification: bool
    errores: List[str]
    # opcional: historial de mensajes si quieres hacerlo conversacional
    messages: Annotated[List, add_messages]


# ---------------------------------------------------------------------------
# 3) LLM (STUB) – reemplazar por ChatOpenAI u otro
# ---------------------------------------------------------------------------
class LLMStub:
    def invoke(self, prompt: str) -> str:
        # En producción: usa ChatOpenAI(model="gpt-4o-mini").invoke([...])
        return "Explicación generada (stub) basada en evidencias y pesos."


llm = LLMStub()


# ---------------------------------------------------------------------------
# 4) NODOS DEL GRAFO
# ---------------------------------------------------------------------------

def nodo_entender_perfil(state: State) -> State:
    """Extrae requisitos desde el texto del perfil y setea defaults."""
    perfil = state.get("perfil_texto", "")
    must = normalize_skills(perfil)

    # Heurísticas simples para extraer años e idioma
    years_min = None
    for tok in perfil.split():
        if tok.endswith("+años") or tok.endswith("+años,"):
            try:
                years_min = int(tok.split("+")[0])
            except Exception:
                pass
        if tok.endswith("años"):
            try:
                years_min = int(tok.split("años")[0])
            except Exception:
                pass

    idioma_min = None
    for lvl in ["C2", "C1", "B2", "B1", "A2", "A1"]:
        if lvl.lower() in perfil.lower():
            idioma_min = lvl
            break

    criterios: Criterios = state.get("criterios", {})
    criterios.setdefault("must_have", must)
    criterios.setdefault("nice_to_have", set())
    criterios.setdefault("years_min", years_min)
    criterios.setdefault("idioma_min", idioma_min)
    criterios.setdefault("pesos", {"skills": 0.45, "experiencia": 0.25, "industria": 0.10, "idiomas": 0.10, "certs": 0.10})
    criterios.setdefault("top_k", 5)
    criterios.setdefault("umbral", 0.65)

    return {"criterios": criterios}


def nodo_recuperar_inicial(state: State) -> State:
    criterios = state["criterios"]
    filtros = {k: criterios.get(k) for k in ("ubicacion", "idioma_min") if criterios.get(k)}
    candidatos = sp_search_cvs(query_text=state.get("perfil_texto", ""), top_k=50, filters=filtros)
    return {"candidatos_iniciales": candidatos}


def nodo_filtrar_duro(state: State) -> State:
    criterios = state["criterios"]
    years_min = criterios.get("years_min")
    idioma_min = criterios.get("idioma_min")

    filtrados = []
    for c in state.get("candidatos_iniciales", []):
        meta = sp_get_metadata(c["file_id"])
        c["meta"] = meta

        # Filtro por años de experiencia (si existe dato)
        if years_min is not None and meta.get("years_experience", 0) < years_min:
            continue

        # Filtro por idioma mínimo
        if idioma_min:
            has_level = 0.0
            for lang in meta.get("languages", []):
                if "EN" in lang.upper() and "-" in lang:
                    has_level = max(has_level, parse_cefr(lang.split("-")[-1]))
            if has_level < parse_cefr(idioma_min):
                continue

        # Filtro por recencia (ej.: 12 meses)
        if days_since(meta.get("updated_at", "")) > 365:
            # puedes excluir o solo penalizar en el ranking; aquí excluimos en filtro duro
            continue

        filtrados.append(c)

    return {"candidatos_filtrados": filtrados}


def nodo_recolectar_evidencias(state: State) -> State:
    evidencias: Dict[str, List[Dict]] = {}
    # Limitar a top ~15 para eficiencia
    for c in state.get("candidatos_filtrados", [])[:15]:
        evidencias[c["file_id"]] = index_highlight(state.get("perfil_texto", ""), c["file_id"], top_passages=5)
    return {"evidencias": evidencias}


def _score_from_evidencias(must_have: Set[str], evids: List[Dict]) -> float:
    if not evids:
        return 0.0
    text = " ".join(e.get("snippet", "").lower() for e in evids)
    hits = sum(1 for m in must_have if m in text)
    return hits / max(1, len(must_have))


def nodo_rerank_y_explicar(state: State) -> State:
    criterios = state["criterios"]
    pesos = criterios.get("pesos", {})
    must = criterios.get("must_have", set())

    out = []
    for c in state.get("candidatos_filtrados", []):
        meta = c.get("meta", {})
        evids = state.get("evidencias", {}).get(c["file_id"], [])

        # Sub-scores simples
        s_skills = _score_from_evidencias(must, evids)
        s_exp = min(1.0, meta.get("years_experience", 0) / max(1, (criterios.get("years_min") or 5)))
        s_lang = 0.0
        for lang in meta.get("languages", []):
            if "EN" in lang.upper() and "-" in lang:
                s_lang = max(s_lang, parse_cefr(lang.split("-")[-1]))
        s_certs = min(1.0, len(meta.get("certifications", [])) / 2)
        # Bonificación por recencia (<= 180 días => +10%)
        recency_bonus = 1.1 if days_since(meta.get("updated_at", "")) <= 180 else 1.0

        score = (
            pesos.get("skills", 0.45) * s_skills +
            pesos.get("experiencia", 0.25) * s_exp +
            pesos.get("idiomas", 0.10) * s_lang +
            pesos.get("certs", 0.10) * s_certs
        ) * recency_bonus
        score = min(score, 1.0)

        # Razones breves con páginas
        razones = []
        for ev in evids[:3]:
            razones.append(f"p.{ev['page']}: {ev['snippet']}")

        out.append({
            "file_id": c["file_id"],
            "name": c.get("name"),
            "url": c.get("url"),
            "score_final": round(score, 3),
            "razones": razones,
            "meta": meta,
        })

    out.sort(key=lambda x: x["score_final"], reverse=True)
    return {"rankeados": out}


def nodo_decidir_suficiencia(state: State) -> State:
    k = state["criterios"]["top_k"]
    umbral = state["criterios"]["umbral"]
    rank = state.get("rankeados", [])
    suficiente = len(rank) >= k and (rank[k-1]["score_final"] >= umbral if len(rank) >= k else False)
    return {"needs_clarification": not suficiente}


def nodo_aclarar(state: State) -> State:
    """Estrategia mínima: relajar umbral en 0.1 para siguiente iteración.
    En producción: preguntar al usuario qué criterio relajar.
    """
    crit = state["criterios"].copy()
    crit["umbral"] = max(0.0, crit.get("umbral", 0.65) - 0.10)
    return {"criterios": crit}


def nodo_responder(state: State) -> State:
    k = state["criterios"]["top_k"]
    topk = state.get("rankeados", [])[:k]
    payload = []
    for item in topk:
        link = open_in_sharepoint(item["file_id"])['url']
        payload.append({
            "candidato": item["meta"].get("candidate_name", item["name"]),
            "score": item["score_final"],
            "razones": item["razones"],
            "ubicacion": item["meta"].get("location"),
            "idiomas": item["meta"].get("languages"),
            "certificaciones": item["meta"].get("certifications"),
            "actualizado": item["meta"].get("updated_at"),
            "url": link,
        })
    return {"respuesta": {"top": payload, "total_evaluados": len(state.get("rankeados", []))}}


def nodo_feedback(state: State) -> State:
    # En producción: recoger selección del usuario y persistir
    for item in state.get("rankeados", [])[: state["criterios"]["top_k"]]:
        feedback_log({"file_id": item["file_id"], "label": "maybe"})
    return {}


# ---------------------------------------------------------------------------
# 5) CONSTRUCCIÓN DEL GRAFO
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(State)
    g.add_node("EntenderPerfil", nodo_entender_perfil)
    g.add_node("RecuperarInicial", nodo_recuperar_inicial)
    g.add_node("FiltrarDuro", nodo_filtrar_duro)
    g.add_node("RecolectarEvidencias", nodo_recolectar_evidencias)
    g.add_node("ReRankYExplicar", nodo_rerank_y_explicar)
    g.add_node("DecidirSuficiencia", nodo_decidir_suficiencia)
    g.add_node("Aclarar", nodo_aclarar)
    g.add_node("Responder", nodo_responder)
    g.add_node("RegistrarFeedback", nodo_feedback)

    # Flujo básico
    g.add_edge(START, "EntenderPerfil")
    g.add_edge("EntenderPerfil", "RecuperarInicial")
    g.add_edge("RecuperarInicial", "FiltrarDuro")
    g.add_edge("FiltrarDuro", "RecolectarEvidencias")
    g.add_edge("RecolectarEvidencias", "ReRankYExplicar")
    g.add_edge("ReRankYExplicar", "DecidirSuficiencia")

    # Bifurcación condicional: suficiente? -> Responder ; si no -> Aclarar -> RecuperarInicial
    def cond(state: State) -> str:
        return "Responder" if not state.get("needs_clarification", True) else "Aclarar"

    g.add_conditional_edges(
        "DecidirSuficiencia",
        cond,
        {
            "Responder": "Responder",
            "Aclarar": "Aclarar",
        },
    )

    g.add_edge("Aclarar", "RecuperarInicial")
    g.add_edge("Responder", "RegistrarFeedback")
    g.add_edge("RegistrarFeedback", END)

    return g


# ---------------------------------------------------------------------------
# 6) EJEMPLO DE EJECUCIÓN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    perfil_demo = (
        "Data Engineer, 5+ años, Spark, Databricks, Azure, inglés B2+; banca es un plus."
    )

    criterios_demo: Criterios = {
        "top_k": 3,
        "umbral": 0.65,
        # Puedes fijar must_have explícitamente o dejar que se extraiga del perfil
        # "must_have": {"spark", "databricks", "azure"},
    }

    app = build_graph().compile()

    init_state: State = {
        "perfil_texto": perfil_demo,
        "criterios": criterios_demo,
        "candidatos_iniciales": [],
        "candidatos_filtrados": [],
        "evidencias": {},
        "rankeados": [],
        "errores": [],
    }

    result = app.invoke(init_state)

    # Render mínimo del resultado
    print("\n=== RESULTADO TOP ===")
    for i, cand in enumerate(result.get("respuesta", {}).get("top", []), start=1):
        print(f"#{i} {cand['candidato']} — score={cand['score']} — {cand['url']}")
        for r in cand["razones"]:
            print("  ·", r)
