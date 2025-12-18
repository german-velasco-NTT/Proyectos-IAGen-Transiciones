# 📋 AgenteRunbooks - Generador de Runbooks Operativos

## Descripción

**AgenteRunbooks** es un agente inteligente que analiza tickets históricos de soporte e incidencias para **generar Runbooks operativos estandarizados** (SOPs - Standard Operating Procedures).

Transforma:
- ✅ Tickets históricos de soporte
- ✅ Pasos manuales dispersos en wikis/correos
- ✅ Instrucciones no documentadas

En:
- 📋 **Runbooks estandarizados** documentados
- ✅ **SOPs y checklists** reutilizables  
- 🏢 **Repositorio central** de guías operativas

---

## 🎯 Casos de Uso

### 1. **Análisis de Tickets Históricos**
Conecta a tu repositorio (GitLab, GitHub, Azure DevOps) y analiza automáticamente todos los tickets de soporte para identificar patrones.

### 2. **Estandarización de Procesos**
Detecta procedimientos repetitivos y los convierte en SOPs reutilizables con checklists validados.

### 3. **Documentación de Incidentes**
Transforma reportes de incidentes en guías paso a paso para prevenir futuras ocurrencias.

---

## 📊 Características Principales

### Dashboard Inteligente
- ✅ Estadísticas en tiempo real
- 📈 Distribución de severidad (Crítica, Alta, Media, Baja)
- 🏷️ Categorización automática de tickets
- 🔝 Top problemas resueltos
- 📉 Indicadores de calidad (tasa de resolución, cobertura)

### Análisis Profundo
- 🔍 Detección automática de plataforma (GitLab, GitHub, Azure DevOps)
- 📝 Análisis de patrones en tickets cerrados
- 🏢 Clasificación por categorías
- ⚠️ Evaluación de severidad

### Exportación de Resultados
- 📥 Descarga análisis en JSON
- 📊 Métricas detalladas
- 🎯 Datos listos para generar SOPs

---

## 🚀 Instalación y Ejecución

### Requisitos
- Python 3.10+
- FastAPI
- Requests
- GitLab/GitHub/Azure DevOps con acceso a issues

### Instalación
```bash
cd /Users/juanguaqueta/Desktop/AgentesIA/AgenteRunbooks

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
python3 api.py
```

El servidor estará disponible en: **http://localhost:8006**

---

## 💻 Interfaz de Usuario

### 1. Formulario de Análisis
```
URL del Repositorio: https://umane.emeal.nttdata.com/git/NAMESPACE/proyecto
Token de Autenticación: [Tu token de acceso]

Opciones Avanzadas:
- Proyecto Específico (opcional)
- Estados de Tickets (opened, closed)
- Mínimo de Tickets
```

### 2. Dashboard de Resultados
Muestra automáticamente:
- 📊 **Estadísticas**: Total, abiertos, cerrados
- ⚠️ **Severidad**: Distribución gráfica
- 🏷️ **Categorías**: Tags detectadas
- 🔝 **Top Issues**: Problemas más comunes resueltos
- 📈 **Indicadores**: Tasa de resolución, cobertura

---

## 🔌 API Endpoints

### Iniciar Análisis
```bash
POST /api/v1/analyze
Content-Type: application/json

{
  "config": {
    "repository_url": "https://umane.emeal.nttdata.com/git/COITDEVSOCOEAPPSIA/crewai-nativeai",
    "token": "sebwvkV21gB-gpK12j1y",
    "project_path": "optional/path",
    "ticket_states": ["opened", "closed"],
    "min_tickets": 5
  }
}
```

### Obtener Estado del Job
```bash
GET /api/v1/jobs/{job_id}

Response:
{
  "job_id": "uuid",
  "status": "completed|analyzing|pending|failed",
  "message": "Descripción del progreso",
  "progress": 85,
  "data": { ... análisis completo ... }
}
```

### Descargar Resultados
```bash
GET /api/v1/jobs/{job_id}/download
```

### Mock Issues (para pruebas)
```bash
GET /api/v1/issues
```

---

## 📈 Estructura de Respuesta del Análisis

```json
{
  "total": 120,
  "opened": 45,
  "closed": 75,
  "severity_distribution": {
    "critical": 12,
    "high": 28,
    "medium": 55,
    "low": 25
  },
  "categories": {
    "infrastructure": 32,
    "security": 18,
    "performance": 41,
    "documentation": 29
  },
  "top_issues": [
    {
      "id": 1,
      "title": "Error de autenticación OAuth2",
      "severity": "critical",
      "labels": ["security", "auth"]
    },
    ...
  ]
}
```

---

## 🎬 Ejemplo de Uso

### 1. **Abrir el Dashboard**
Ir a: http://localhost:8006

### 2. **Ingresar Credenciales**
```
URL: https://umane.emeal.nttdata.com/git
Token: sebwvkV21gB-gpK12j1y
Proyecto: COITDEVSOCOEAPPSIA/crewai-nativeai
```

### 3. **Iniciar Análisis**
Clic en "🚀 Iniciar Análisis"

### 4. **Ver Resultados**
El dashboard se actualiza automáticamente con:
- Tickets procesados: 120 ✅
- Tasa resolución: 62.5%
- Categorías: 8 detectadas
- Top issues: Mostrando los más críticos

### 5. **Descargar Datos**
Clic en "📥 Descargar Análisis" para obtener JSON

---

## 🔐 Autenticación

### GitLab Token
Genera un token personal en:
```
https://umane.emeal.nttdata.com/git/-/user_settings/personal_access_tokens
```

Permisos requeridos:
- ✅ `api` - Acceso general a API
- ✅ `read_api` - Lectura de datos
- ✅ `read_repository` - Lectura de repos

### GitHub Token
Genera en: https://github.com/settings/tokens

### Azure DevOps Token
Crea en: https://dev.azure.com/_usersettings/tokens

---

## 🛠️ Configuración

### Variables de Entorno
Crear archivo `.env`:
```
GITLAB_URL=https://umane.emeal.nttdata.com/git
GITLAB_TOKEN=tu_token_aqui
PROJECT_PATH=COITDEVSOCOEAPPSIA/crewai-nativeai
```

### Puerto Personalizado
Editar `api.py`:
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)  # Cambiar puerto aquí
```

---

## 🧪 Pruebas

### Health Check
```bash
curl http://localhost:8006/health
```

### Mock Data (120 tickets de prueba)
```bash
curl http://localhost:8006/api/v1/issues
```

---

## 📚 Arquitectura

```
AgenteRunbooks/
├── api.py                          # Servidor FastAPI principal
├── web/
│   ├── index.html                  # Dashboard UI
│   ├── app.js                      # Lógica del frontend
│   ├── style.css                   # Estilos corporativos
│   └── favicon.ico                 # Icono
├── outputs/                        # Resultados generados
├── mock_issues.json                # 120 tickets de prueba
├── requirements.txt                # Dependencias
└── README.md                       # Este archivo
```

---

## 🔄 Flujo de Datos

```
Cliente
  │
  ├─→ Ingresa URL + Token
  │
  ├─→ POST /api/v1/analyze
  │     ├─ Detecta plataforma
  │     ├─ Obtiene issues del repo
  │     ├─ Analiza tickets
  │     └─ Retorna job_id
  │
  ├─→ Polling GET /api/v1/jobs/{job_id}
  │     ├─ Status: analyzing (0-100%)
  │     └─ Data: análisis completo
  │
  └─→ Dashboard actualizado
        ├─ Estadísticas
        ├─ Gráficos
        ├─ Categorías
        └─ Top issues
```

---

## 🐛 Troubleshooting

### Error: "Job no encontrado"
- Verificar que el job_id es correcto
- Revisar logs del servidor

### Error: "403 Forbidden"
- Verificar token tiene permisos
- Verificar acceso al proyecto

### Dashboard no actualiza
- Abrir consola (F12) y revisar Network
- Verificar que `API_BASE` en app.js es correcto
- Limpiar caché del navegador

---

## 📞 Soporte

Para reportar issues o sugerencias:
- Crear issue en GitLab
- Contactar al equipo de IA

---

## 📄 Licencia

© 2025 NTT DATA EMIA. Todos los derechos reservados.

---

**Estado**: ✅ Listo para producción  
**Versión**: 2.0.0  
**Última actualización**: 15 de diciembre de 2025
