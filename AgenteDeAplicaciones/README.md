# 📦 Agente de Inventario de Aplicaciones v2.0

Un agente inteligente que consolida el inventario de aplicaciones desde múltiples fuentes (repositorios, CMDB, documentación, jobs) usando inteligencia artificial.

## 🎯 Propósito

Mantener un **catálogo unificado de aplicaciones** que integra información de:
- **Repositorios:** GitHub, GitLab, Bitbucket, Azure DevOps
- **CMDB:** Información de configuración y relaciones
- **Documentación:** Wikis (Confluence, SharePoint, Notion)
- **Jobs:** Planificadores (Control-M, Airflow, Jenkins, cron)

## 🚀 Inicio Rápido

### 1. Requisitos
- Python 3.9+
- FastAPI & Uvicorn
- LangChain & Azure OpenAI (opcional para IA)
- Python GitLab, PyGithub (para repos)

### 2. Instalar Dependencias
```bash
cd /Users/juanguaqueta/Desktop/AgentesIA/AgenteDeAplicaciones
pip install -r requirements.txt
# O instalar manualmente:
pip install fastapi uvicorn pydantic python-dotenv langchain langchain-openai python-gitlab PyGithub
```

### 3. Configurar Credenciales (`.env`)
```properties
# Repositorio
GITLAB_URL=https://umane.emeal.nttdata.com/git
GITLAB_TOKEN=tu_token_aqui
PROJECT_PATH=grupo/proyecto

# Azure OpenAI (para análisis IA)
AZURE_OPENAI_API_KEY=tu_key_aqui
AZURE_OPENAI_ENDPOINT=https://tu-instancia.openai.azure.com/
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

### 4. Levantar Servicios

**Terminal 1 - Backend API:**
```bash
cd /Users/juanguaqueta/Desktop/AgentesIA/AgenteDeAplicaciones
/Users/juanguaqueta/Library/Python/3.9/bin/uvicorn api:app --host 127.0.0.1 --port 8001
```

**Terminal 2 - Frontend:**
```bash
cd /Users/juanguaqueta/Desktop/AgentesIA/AgenteDeAplicaciones/web
python3 -m http.server 8000
```

### 5. Acceder
- 🌐 **Frontend:** http://127.0.0.1:8000/
- ⚙️  **API Docs:** http://127.0.0.1:8001/docs

---

## 📋 Uso

### Vía Web UI
1. Seleccionar **tipo de fuente** (GitLab, GitHub, etc.)
2. Ingresar **URL** y **token**
3. Seleccionar opciones de análisis (CMDB, documentación, jobs)
4. Hacer clic en **"Iniciar Análisis"**
5. Esperar a que se complete
6. Ver resultados en el dashboard
7. Descargar reporte en ZIP

### Vía API REST

**Iniciar análisis:**
```bash
curl -X POST http://127.0.0.1:8001/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "gitlab",
    "source_url": "https://umane.emeal.nttdata.com/git",
    "token": "tu_token",
    "project_path": "grupo/proyecto",
    "use_ai_analysis": true
  }'
```

**Obtener estado:**
```bash
curl http://127.0.0.1:8001/api/v1/jobs/{job_id}
```

**Obtener análisis completo:**
```bash
curl http://127.0.0.1:8001/api/v1/jobs/{job_id}/analysis
```

**Descargar reporte:**
```bash
curl http://127.0.0.1:8001/api/v1/download/{job_id} -o reporte.zip
```

---

## 📊 Estructura del Catálogo

```json
{
  "metadata": {
    "generated_at": "2025-12-03T...",
    "version": "1.0.0",
    "source_type": "gitlab"
  },
  "summary": {
    "total_applications": 15,
    "total_repositories": 42,
    "health_score": 78
  },
  "applications": [
    {
      "id": "app_001",
      "name": "App Web",
      "owner": "equipo-backend",
      "repositories": ["repo_1", "repo_2"],
      "health_score": 85
    }
  ],
  "repositories": [
    {
      "id": 123,
      "name": "backend-service",
      "url": "https://gitlab.com/...",
      "last_activity": "2025-12-03",
      "owner": "juan.pablo"
    }
  ],
  "issues_detected": [
    {
      "type": "orphan_repo",
      "severity": "high",
      "repository": "repo_viejo",
      "message": "Repositorio sin mantenimiento hace 6 meses"
    }
  ],
  "ai_insights": {
    "executive_summary": "...",
    "recommendations": [...]
  }
}
```

---

## 🧠 Inteligencia Artificial

El agente usa **Azure OpenAI (GPT-4o-mini)** para:
- 📝 Generar resumen ejecutivo
- 🎯 Identificar riesgos y problemas
- 💡 Proporcionar recomendaciones
- 📊 Calcular health scores

Si no está configurado, funciona en modo **fallback** con análisis básico.

---

## 🔍 Detección de Problemas

El agente detecta automáticamente:
- ❌ **Repos huérfanos:** Sin actividad en 90+ días
- 🚨 **Apps sin dueño:** Sin responsable asignado
- 📦 **Módulos desactualizados:** Dependencias obsoletas
- 🔄 **Inconsistencias:** Datos duplicados o contradictorios
- 🔐 **Falta de documentación:** Repos sin README/wiki

---

## 📁 Estructura del Proyecto

```
AgenteDeAplicaciones/
├── api.py                    # API REST (FastAPI)
├── AS_langgraphEnabler.py   # Agente de orquestación (LangGraph)
├── LLMAnalyzer.py           # Análisis inteligente con LLM
├── pyproject.toml           # Dependencias
├── .env                     # Configuración
├── web/
│   ├── index.html          # Dashboard
│   ├── app.js              # Lógica del frontend
│   ├── style.css           # Estilos
│   └── serve.py            # Servidor web
├── outputs/                 # Resultados de análisis
└── CAMBIOS_REALIZADOS.md   # Historial de cambios
```

---

## 🛠️ Desarrollo

### Estructura del Código

**api.py:**
- Endpoint `/api/v1/analyze` - Inicia análisis
- Endpoint `/api/v1/jobs/{id}` - Obtiene estado
- Endpoint `/api/v1/jobs/{id}/analysis` - Obtiene resultados
- Job management thread-safe en background

**AS_langgraphEnabler.py:**
- Clase `InventoryAgent` - Orquestador principal
- Métodos para cada fuente (GitLab, GitHub, etc.)
- Correlación de datos y construcción de catálogo

**LLMAnalyzer.py:**
- Clase `InventoryAnalyzer` - Análisis con IA
- Genera insights basados en el catálogo
- Fallback si LLM no está disponible

---

## 🐛 Troubleshooting

### Error: "Address already in use"
```bash
# Matar procesos anteriores
killall -9 python3
# O usar otro puerto:
uvicorn api:app --port 8002
```

### Error: "AttributeError: 'Project' object has no attribute"
Esto significa que GitLab retornó un objeto lazy. El código ahora maneja esto con `getattr()` seguro.

### Error: "LLM no inicializado"
Verificar que `.env` tiene `AZURE_OPENAI_API_KEY` y `AZURE_OPENAI_ENDPOINT`. Si no, el agente funciona en fallback.

### No se ven resultados en el dashboard
1. Verificar que el job tiene `status: 'completed'`
2. Verificar que existe `outputs/{job_id}/inventory_catalog.json`
3. Revisar logs del terminal de la API

---

## 📈 Rendimiento

- ✅ Soporta **50+ repositorios** sin problemas
- ⏱️ Análisis completo en **2-5 minutos** (dependiendo de tamaño)
- 💾 Catálogo típico: **50-200 KB** JSON
- 🔄 Polling: cada **2 segundos** en el frontend

---

## 🔐 Seguridad

- ✅ Tokens nunca se guardan en logs
- ✅ CORS habilitado para desarrollo (cambiar para producción)
- ✅ Validación de input con Pydantic
- ⚠️ Habilitar autenticación en producción

---

## 📝 Próximas Mejoras

- [ ] Integración real con CMDB (ServiceNow, etc.)
- [ ] Conectar con Confluence/SharePoint para documentación
- [ ] Soporte para planificadores de jobs
- [ ] Alertas automáticas en Teams/Slack
- [ ] Autenticación OAuth
- [ ] Auditoría de cambios
- [ ] Dashboard de Grafana/Power BI
- [ ] Reporte programado por email

---

## 📞 Soporte

Para reportar bugs o sugerir mejoras, contactar a: **Juan Pablo** (jpgua1)

---

**Versión:** 2.0.0  
**Última actualización:** 3 de diciembre de 2025  
**Estado:** ✅ En producción
