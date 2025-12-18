# AgenteRunbooks - Runbook Generator

## 🎯 Descripción

**AgenteRunbooks** es un agente inteligente que analiza tickets históricos de soporte e incidencias para generar **Runbooks operativos estandarizados**, SOPs (Standard Operating Procedures) y checklists reutilizables.

Funciona de manera **idéntica a AgenteDependencias** pero enfocado en:
- Análisis de tickets históricos  
- Identificación de patrones de resolución
- Clasificación por severidad y categoría
- Generación de procesos operativos documentados

## 🏗️ Arquitectura

```
Repository (GitLab/GitHub/Azure DevOps)
    ↓
AgenteRunbooks API (8006)
    ├── Fetch Issues
    ├── Analyze Patterns
    ├── Classify & Categorize
    └── Generate SOPs/Runbooks
    ↓
Dashboard (Web UI)
    ├── Real-time Status
    ├── Analysis Results
    ├── Severity Distribution
    └── Download Results
```

## 🚀 Instalación & Uso

### 1. Instalación

```bash
cd AgenteRunbooks
pip install -r requirements.txt
```

### 2. Iniciar el Servidor

```bash
python3 api.py
# Servidor escucha en http://localhost:8006
```

### 3. Usar el Dashboard

Abre en tu navegador:
```
http://localhost:8006
```

## 📊 Endpoints API

### Análisis de Tickets

**POST** `/api/v1/analyze`

```json
{
  "config": {
    "repository_url": "https://umane.emeal.nttdata.com/git/NAMESPACE/proyecto",
    "token": "tu_token_aqui",
    "project_path": "NAMESPACE/proyecto",
    "ticket_states": ["opened", "closed"],
    "min_tickets": 5
  }
}
```

**Response:**
```json
{
  "job_id": "uuid-xxxx",
  "status": "pending",
  "message": "Inicializando...",
  "progress": 0,
  "created_at": "2025-12-15T10:30:00",
  "updated_at": "2025-12-15T10:30:00",
  "data": null
}
```

### Obtener Estado del Job

**GET** `/api/v1/jobs/{job_id}`

Retorna el estado actual, progreso y datos del análisis.

### Descargar Resultados

**GET** `/api/v1/jobs/{job_id}/download`

Descarga el análisis en formato JSON.

### Issues Mock (para testing)

**GET** `/api/v1/issues`

Retorna los 120 tickets de ejemplo para testing.

## 📈 Flujo Completo

1. **Usuario inicia análisis** con URL del repositorio y token
2. **API detecta plataforma** (GitLab, GitHub, Azure DevOps)
3. **Obtiene tickets históricos** del repositorio
4. **Analiza cada ticket:**
   - Extrae estado (abierto/cerrado)
   - Detecta severidad (crítica/alta/media/baja)
   - Identifica categorías por labels
   - Busca patrones de resolución
5. **Genera dashboard** con:
   - Estadísticas por estado
   - Distribución de severidad
   - Categorías identificadas
   - Top 10 problemas resueltos
   - Indicadores de calidad (tasa de resolución, cobertura)
6. **Usuario descarga** análisis en JSON para post-procesamiento

## 📋 Estructura del Análisis

```json
{
  "total": 120,
  "opened": 15,
  "closed": 105,
  "severity_distribution": {
    "critical": 5,
    "high": 20,
    "medium": 60,
    "low": 35
  },
  "categories": {
    "bug": 45,
    "enhancement": 30,
    "documentation": 25,
    "performance": 20
  },
  "top_issues": [
    {
      "id": 123,
      "title": "Error 500 en login",
      "severity": "critical",
      "labels": ["bug", "urgent"]
    }
  ],
  "resolution_patterns": []
}
```

## 🎨 Dashboard Features

- ✅ **Estadísticas en tiempo real**
- 🔄 **Polling automático** cada 2 segundos
- 📊 **Gráficos y métricas** de severidad
- 🏷️ **Categorías detectadas** interactivas
- 🔝 **Top 10 problemas** resueltos
- 📈 **Indicadores de calidad** (tasa resolución, cobertura)
- ⬇️ **Descarga de resultados** en JSON

## 🔌 Plataformas Soportadas

- ✅ **GitLab** (https://umane.emeal.nttdata.com/git)
- ⚠️ **GitHub** (en desarrollo)
- ⚠️ **Azure DevOps** (en desarrollo)

## 🧪 Testing

Los 120 tickets reales ya están creados en GitLab:
- **Proyecto**: COITDEVSOCOEAPPSIA/crewai-nativeai (ID: 44875)
- **Issues creados**: #21 a #140
- **Labels**: "testing", "agente-ia"

### Ejemplo de Uso

```bash
# 1. Abrir dashboard
open http://localhost:8006

# 2. Completar formulario:
# - URL: https://umane.emeal.nttdata.com/git/COITDEVSOCOEAPPSIA/crewai-nativeai
# - Token: sebwvkV21gB-gpK12j1y

# 3. Click "Iniciar Análisis"

# 4. Ver dashboard con resultados
```

## 📝 Configuración

Edita `api.py` para cambiar:
- `OUTPUT_DIR`: Directorio de salida
- `jobs_store`: Almacenamiento (mem/DB/Redis)
- Puertos y hosts de escucha

## 🔧 Troubleshooting

### Error "Plataforma no soportada"
- Verifica que la URL tenga formato correcto
- Asegúrate que GitLab está disponible

### Error 403 (Token inválido)
- Verifica que el token tiene permisos en el proyecto
- Comprueba que no ha expirado

### Port 8006 already in use
```bash
lsof -i :8006  # Encuentra el proceso
kill -9 <PID>   # Mata el proceso
```

## 📚 Documentación Adicional

Ver también:
- `AgenteDependencias/README.md` - Análisis de dependencias
- `AgenteOrquestador/README.md` - Orquestación
- `PAYLOADS_EJEMPLOS.json` - Ejemplos de payloads

## 👨‍💻 Autor

Generado como parte del suite de Agentes IA para automatización operacional.

**Versión**: 2.0.0  
**Estado**: Production-Ready  
**Última actualización**: 15 de Diciembre, 2025
