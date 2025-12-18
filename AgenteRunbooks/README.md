# 📘 Agente Generador de Runbooks

Agente inteligente diseñado para transformar **tickets históricos de soporte**, correos y wikis dispersas en **Runbooks Operativos Estandarizados**.

Utiliza **LangGraph** y **LLMs (Azure OpenAI)** para analizar patrones de incidentes y sintetizar guías paso a paso (SOPs).

## 📋 Características

✅ **Ingesta de Incidentes** - Procesa volcados de texto de tickets (ServiceNow, Jira, emails, etc.).
✅ **Clustering Inteligente** - Detecta problemas recurrentes y los agrupa.
✅ **Generación de Runbooks** - Crea documentos Markdown con:
  - Síntomas y Diagnóstico
  - Causa Raíz Probable
  - Pasos de Solución (Comandos, Validaciones)
  - Rollback
✅ **Biblioteca Centralizada** - Repositorio de conocimiento operativo.

## 🏗️ Arquitectura

### Estructura del proyecto

```
AgenteRunbooks/
├── api.py                      # Servidor FastAPI (Puerto 8006)
├── AS_langgraphEnabler.py      # Orquestador LangGraph (Generación de Texto)
├── AzureProvider.py            # Proveedor Azure LLM
├── outputs/                    # Runbooks generados
│   └── {job_id}/              
│       ├── runbook.md
│       └── analysis.json
└── web/                        # Interfaz Web de Generación
```

## 🚀 Instalación y ejecución

### 1. Instalar dependencias

```bash
cd AgenteRunbooks
pip install fastapi uvicorn pydantic langchain langgraph azure-identity python-dotenv
```

### 2. Configurar variables de entorno

Crea un archivo `.env`:

```bash
AZURE_API_BASE="https://your-instance.openai.azure.com/"
AZURE_API_VERSION="2023-05-15"
AZURE_DEPLOYMENT_NAME="gpt-4"
AZURE_API_KEY="your-key"
```

### 3. Ejecutar el servidor

```bash
# Ejecutar en el puerto 8006
uvicorn api:app --reload --port 8006
```

El servidor estará disponible en `http://localhost:8006`

## 📚 Uso

1. Abrir la interfaz web (`http://localhost:8006`).
2. Pegar el contenido "crudo" de tickets o incidentes resueltos.
3. Hacer clic en **"Generar Runbook"**.
4. Revisar y descargar el *Standard Operating Procedure* (SOP) generado.
