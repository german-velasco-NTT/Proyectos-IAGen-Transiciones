/**
 * app.js - Frontend para Application Inventory Agent
 * Maneja polling de jobs, visualización de inventario y análisis inteligente
 */

const API = 'http://127.0.0.1:8001';
const POLLING_INTERVAL = 2000; // ms entre polls
const CACHE_BUSTER = Date.now();

let currentJob = null;
let pollingInterval = null;

// Guardar job en localStorage para recuperarlo si se cierra la ventana
function saveJobId(jobId) {
  currentJob = jobId;
  localStorage.setItem('lastJobId', jobId);
  localStorage.setItem('lastJobTime', Date.now().toString());
}

function getLastJobId() {
  const saved = localStorage.getItem('lastJobId');
  const time = parseInt(localStorage.getItem('lastJobTime') || '0');
  // Considerar válido si fue en los últimos 24 horas
  if (saved && (Date.now() - time) < 86400000) {
    return saved;
  }
  return currentJob;
}

/**
 * UTILIDADES
 */

function log(msg, type = 'info') {
  const prefix = {
    'info': '📋',
    'success': '✅',
    'error': '❌',
    'warn': '⚠️',
    'loading': '⏳'
  }[type] || '•';
  
  console.log(`${prefix} ${msg}`);
}

function showStatus(msg, type = 'info') {
  const statusEl = document.getElementById('status');
  if (!statusEl) return;
  
  const icons = {
    'info': '📋',
    'success': '✅',
    'error': '❌',
    'warn': '⚠️',
    'loading': '⏳'
  };
  
  statusEl.innerHTML = `<p class="${type}">${icons[type]} ${msg}</p>`;
  statusEl.style.display = 'block';
}

function clearStatus() {
  const statusEl = document.getElementById('status');
  if (statusEl) {
    statusEl.innerHTML = '';
    statusEl.style.display = 'none';
  }
}

function formatDate(dateStr) {
  if (!dateStr || dateStr === 'unknown') return 'N/A';
  try {
    return new Date(dateStr).toLocaleString('es-ES');
  } catch {
    return dateStr;
  }
}

/**
 * JOB MANAGEMENT
 */

async function submitAnalysis(formData) {
  try {
    log('Enviando solicitud de análisis...', 'loading');
    showStatus('Enviando solicitud de análisis...', 'loading');
    
    console.log('Enviando a:', `${API}/api/v1/analyze`);
    console.log('Datos:', formData);
    
    const response = await fetch(`${API}/api/v1/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    
    if (!response.ok) {
      try {
        const error = await response.json();
        throw new Error(error.detail || `HTTP ${response.status}`);
      } catch (e) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    }
    
    const result = await response.json();
    log(`Job creado: ${result.job_id}`, 'success');
    
    saveJobId(result.job_id);
    startJobPolling(result.job_id);
    
    return result.job_id;
  } catch (error) {
    console.error('Error completo:', error);
    log(`Error en análisis: ${error.message}`, 'error');
    showStatus(`❌ Error: ${error.message}. Verifica que el backend esté corriendo en ${API}`, 'error');
    throw error;
  }
}

async function pollJobStatus(jobId) {
  try {
    const response = await fetch(`${API}/api/v1/jobs/${jobId}?v=${CACHE_BUSTER}`);
    
    if (!response.ok) {
      log(`Error al obtener status: HTTP ${response.status}`, 'warn');
      return null;
    }
    
    return await response.json();
  } catch (error) {
    log(`Error polling: ${error.message}`, 'warn');
    return null;
  }
}

function startJobPolling(jobId) {
  log(`Iniciando polling para job ${jobId}`, 'info');
  
  // Limpiar intervalo anterior si existe
  if (pollingInterval) clearInterval(pollingInterval);
  
  // Hacer primera búsqueda inmediata
  checkJobStatus(jobId);
  
  // Luego hacer polling periódico
  pollingInterval = setInterval(() => checkJobStatus(jobId), POLLING_INTERVAL);
}

async function checkJobStatus(jobId) {
  const status = await pollJobStatus(jobId);
  
  if (!status) {
    showStatus('No se pudo obtener status del job', 'warn');
    return;
  }
  
  log(`Job ${jobId}: ${status.status} (${status.progress || 0}%)`, 'info');
  
  // Actualizar UI con progreso
  const statusEl = document.getElementById('status');
  if (statusEl) {
    const progress = status.progress || 0;
    const msg = status.message || `Analizando... ${progress}%`;
    
    // Crear barra de progreso visual
    const progressHTML = `
      <p style="margin-bottom: 10px; font-weight: bold;">⏳ ${msg}</p>
      <div style="width:100%;height:20px;background:#1e293b;border-radius:4px;overflow:hidden;border:1px solid #334155;">
        <div style="width:${progress}%;height:100%;background:#6366f1;transition:width 0.3s ease;display:flex;align-items:center;justify-content:center;color:white;font-size:11px;font-weight:bold;">
          ${progress > 5 ? progress + '%' : ''}
        </div>
      </div>
    `;
    statusEl.innerHTML = progressHTML;
    statusEl.style.display = 'block';
  }
  
  // Cuando se complete
  if (status.status === 'completed') {
    log(`✅ Job completado!`, 'success');
    clearInterval(pollingInterval);
    
    // Mostrar dashboard
    showDashboard(jobId);
    return;
  }
  
  // Si falla
  if (status.status === 'failed') {
    log(`❌ Job falló`, 'error');
    clearInterval(pollingInterval);
    const error = status.error || 'Error desconocido';
    showStatus(`Error en análisis: ${error}`, 'error');
    return;
  }
}

async function showDashboard(jobId) {
  try {
    log(`Cargando dashboard para job ${jobId}`, 'loading');
    showStatus('Cargando dashboard...', 'loading');
    
    // Obtener análisis completo
    const response = await fetch(`${API}/api/v1/jobs/${jobId}/analysis?v=${CACHE_BUSTER}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: No se pueden cargar los datos`);
    }
    
    const data = await response.json();
    log(`Dashboard cargado`, 'success');
    
    // Renderizar dashboard
    renderDashboard(data, jobId);
    
    // Mostrar secciones
    const formSection = document.getElementById('form-section');
    const dashboard = document.getElementById('dashboard');
    
    // Ocultar formulario y mostrar dashboard
    if (formSection) formSection.style.display = 'none';
    if (dashboard) dashboard.classList.remove('hidden');
    
    clearStatus();
  } catch (error) {
    log(`Error loading dashboard: ${error.message}`, 'error');
    showStatus(`Error: ${error.message}`, 'error');
  }
}

/**
 * RENDERIZAR DASHBOARD DE INVENTARIO
 */

function renderDashboard(inventoryData, jobId) {
  const data = inventoryData.inventory || inventoryData;
  const summary = data.summary || {};
  const applications = data.applications || [];
  const repositories = data.repositories || [];
  const issues = data.issues_detected || [];
  
  // ===== RESUMEN EJECUTIVO =====
  const summaryEl = document.getElementById('summary');
  if (summaryEl) {
    const metrics = [
      { label: 'Aplicaciones', value: applications.length, emoji: '📦' },
      { label: 'Repositorios', value: repositories.length, emoji: '🗂️' },
      { label: 'Problemas', value: issues.length, emoji: '⚠️' },
      { label: 'Índice Salud', value: summary.health_score ? summary.health_score + '%' : 'N/A', emoji: '💊' },
    ];
    
    summaryEl.innerHTML = `
      <h2>📊 Resumen del Inventario</h2>
      <div class="metrics-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin-top:1rem;">
        ${metrics.map(m => `
          <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:2rem;margin-bottom:0.5rem;">${m.emoji}</div>
            <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:0.5rem;">${m.label}</div>
            <div style="color:#6366f1;font-size:1.5rem;font-weight:bold;">${m.value}</div>
          </div>
        `).join('')}
      </div>
      ${summary.executive_summary ? `
        <div style="margin-top:1.5rem;padding:1rem;background:#0f172a;border-left:4px solid #6366f1;border-radius:4px;">
          <p style="color:#cbd5e1;line-height:1.6;">${summary.executive_summary}</p>
        </div>
      ` : ''}
    `;
  }
  
  // ===== CATÁLOGO DE APLICACIONES =====
  const appsContainer = document.getElementById('applications-container');
  if (appsContainer && applications.length > 0) {
    appsContainer.innerHTML = applications.map(app => `
      <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:1rem;">
        <h3 style="color:#6366f1;margin-bottom:0.5rem;">${app.name || 'Sin nombre'}</h3>
        <div style="color:#94a3b8;font-size:0.85rem;line-height:1.6;">
          <p><strong>Dueño:</strong> ${app.owner || 'No asignado'}</p>
          <p><strong>Estado:</strong> <span style="color:${app.status === 'Active' ? '#10b981' : '#f59e0b'}">${app.status || 'Desconocido'}</span></p>
          <p><strong>Repositorios:</strong> ${(app.repositories || []).length}</p>
          ${app.version ? `<p><strong>Versión:</strong> ${app.version}</p>` : ''}
          ${app.description ? `<p><strong>Descripción:</strong> ${app.description}</p>` : ''}
        </div>
      </div>
    `).join('');
  }
  
  // ===== TABLA DE REPOSITORIOS =====
  const tbody = document.getElementById('repositories-tbody');
  if (tbody && repositories.length > 0) {
    tbody.innerHTML = repositories.map(repo => `
      <tr style="border-bottom:1px solid #334155;">
        <td style="padding:0.5rem;"><strong>${repo.name || 'N/A'}</strong></td>
        <td style="padding:0.5rem;">${repo.tags ? repo.tags.length : 0}</td>
        <td style="padding:0.5rem;font-size:0.85rem;">${repo.last_commit ? formatDate(repo.last_commit) : 'N/A'}</td>
        <td style="padding:0.5rem;">${repo.owner || 'N/A'}</td>
      </tr>
    `).join('');
  }
  
  // ===== PROBLEMAS DETECTADOS =====
  const issuesContainer = document.getElementById('issues-container');
  if (issuesContainer && issues.length > 0) {
    issuesContainer.innerHTML = issues.map(issue => {
      const colorMap = {
        'critical': '#ef4444',
        'high': '#f59e0b',
        'medium': '#eab308',
        'low': '#10b981'
      };
      const color = colorMap[issue.severity] || '#94a3b8';
      return `
        <div style="background:#0f172a;border-left:4px solid ${color};border-radius:4px;padding:1rem;color:#cbd5e1;">
          <strong style="color:${color};text-transform:uppercase;font-size:0.85rem;">${issue.severity || 'INFO'}</strong>
          <p style="margin-top:0.5rem;margin-bottom:0;">${issue.message || 'Problema detectado'}</p>
          ${issue.details ? `<p style="margin-top:0.5rem;color:#94a3b8;font-size:0.85rem;">${issue.details}</p>` : ''}
        </div>
      `;
    }).join('');
  }
  
  // Guardar datos globales
  window.inventoryData = inventoryData;
}

/**
 * DETECCIÓN AUTOMÁTICA DE TIPO DE FUENTE
 */

function detectSourceType(url) {
  if (!url) return null;
  
  const urlLower = url.toLowerCase();
  
  // GitLab: gitlab.com, gitlab.*, cualquier dominio con gitlab
  if (urlLower.includes('gitlab.com') || urlLower.includes('gitlab')) {
    return 'gitlab';
  }
  
  // GitHub: github.com, github.*
  if (urlLower.includes('github.com') || urlLower.includes('github')) {
    return 'github';
  }
  
  // Azure DevOps: dev.azure.com, *.visualstudio.com
  if (urlLower.includes('dev.azure.com') || urlLower.includes('visualstudio.com') || urlLower.includes('azure.com')) {
    return 'azure';
  }
  
  // Bitbucket: bitbucket.org, bitbucket.*
  if (urlLower.includes('bitbucket.org') || urlLower.includes('bitbucket')) {
    return 'bitbucket';
  }
  
  // Por defecto, intentar GitLab si no se puede detectar
  return 'gitlab';
}

function getSourceTypeName(sourceType) {
  const names = {
    'gitlab': 'GitLab',
    'github': 'GitHub',
    'azure': 'Azure DevOps',
    'bitbucket': 'Bitbucket'
  };
  return names[sourceType] || sourceType;
}

/**
 * FORMULARIO
 */

function resetForm() {
  const formSection = document.getElementById('form-section');
  const dashboard = document.getElementById('dashboard');
  
  if (formSection) formSection.style.display = 'block';
  if (dashboard) dashboard.classList.add('hidden');
  
  clearStatus();
  clearInterval(pollingInterval);
  currentJob = null;
}

function handleFormSubmit(event) {
  event.preventDefault();
  
  const form = event.target;
  const formData = new FormData(form);
  
  const sourceUrl = formData.get('source_url');
  
  // Detectar tipo de fuente automáticamente
  const detectedType = detectSourceType(sourceUrl);
  
  if (!detectedType) {
    showStatus('No se pudo detectar el tipo de fuente. Por favor verifica la URL.', 'error');
    return;
  }
  
  // Recolectar datos del formulario
  const config = {
    source_type: detectedType,
    source_url: sourceUrl,
    token: formData.get('token'),
    project_path: formData.get('project_path') || undefined,
    auto_discover_groups: formData.get('auto_discover_groups') === 'true',
    include_cmdb: formData.get('include_cmdb') === 'true',
    include_documentation: formData.get('include_documentation') === 'true',
    include_jobs: formData.get('include_jobs') === 'true',
    use_ai_analysis: formData.get('use_ai_analysis') === 'true'
  };
  
  // Validar
  if (!config.source_url) {
    showStatus('Debes ingresar la URL de fuente', 'error');
    return;
  }
  
  if (!config.token) {
    showStatus('Debes ingresar el token de autenticación', 'error');
    return;
  }
  
  // Limpiar valores vacíos
  Object.keys(config).forEach(key => {
    if (config[key] === undefined || config[key] === '') {
      delete config[key];
    }
  });
  
  log(`Configuración detectada: ${getSourceTypeName(detectedType)} - ${JSON.stringify(config)}`, 'info');
  showStatus(`🔍 Detectado: ${getSourceTypeName(detectedType)}. Iniciando análisis...`, 'info');
  submitAnalysis(config);
}

/**
 * DESCARGA
 */

function downloadJsonZip() {
  const jobId = currentJob || getLastJobId();
  
  if (!jobId) {
    showStatus('No hay job activo', 'warn');
    return;
  }
  
  log(`Descargando catálogo para job ${jobId}...`, 'loading');
  showStatus('Descargando archivo...', 'info');
  
  // Crear link temporal para descarga
  const link = document.createElement('a');
  link.href = `${API}/api/v1/download/${jobId}`;
  link.download = `inventory-${jobId.slice(0, 8)}.zip`;
  link.target = '_blank';
  document.body.appendChild(link);
  
  // Esperar un poco y luego click
  setTimeout(() => {
    link.click();
    document.body.removeChild(link);
    log('Descarga iniciada', 'success');
    showStatus('Archivo descargando...', 'success');
  }, 100);
}

/**
 * ANÁLISIS CON IA
 */

async function performLLMAnalysis(jobId, analysisType, title) {
  if (!jobId) {
    log('No hay job activo', 'error');
    return;
  }

  showStatus(`⏳ Procesando ${title}...`, 'loading');
  const resultsContainer = document.getElementById('llm-results-container');
  const resultTitle = document.getElementById('llm-results-title');
  const resultContent = document.getElementById('llm-results-content');

  // Mostrar contenedor con indicador de carga
  resultsContainer.style.display = 'block';
  resultTitle.textContent = title;
  resultContent.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem;gap:1rem;">
      <div style="font-size:3rem;">⏳</div>
      <div>Analizando con IA...</div>
      <div style="width:100%;max-width:300px;">
        <div style="height:4px;background:#334155;border-radius:2px;overflow:hidden;">
          <div style="height:100%;background:linear-gradient(90deg,#6366f1,#8b5cf6);width:100%;animation:shimmer 1.5s infinite;"></div>
        </div>
      </div>
    </div>
  `;

  try {
    const response = await fetch(`${API}/api/v1/jobs/${jobId}/llm/${analysisType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    
    if (data.success || data.analysis) {
      resultTitle.textContent = title;
      resultContent.innerHTML = `<div style="white-space:pre-wrap;line-height:1.6;">${data.analysis || JSON.stringify(data, null, 2)}</div>`;
      resultsContainer.style.display = 'block';
      log(`${title} completado`, 'success');
      showStatus(`✅ ${title} completado`, 'success');
    } else {
      throw new Error(data.error || 'Error desconocido');
    }
  } catch (error) {
    log(`Error en ${title}: ${error.message}`, 'error');
    resultTitle.textContent = `❌ Error en ${title}`;
    resultContent.innerHTML = `<div style="color:#ef4444;"><strong>Error:</strong> ${error.message}<br><br><em>Por favor intenta de nuevo o verifica que el análisis se completó correctamente.</em></div>`;
    resultsContainer.style.display = 'block';
    showStatus(`Error: ${error.message}`, 'error');
  }
}

/**
 * INICIALIZACIÓN
 */

document.addEventListener('DOMContentLoaded', () => {
  log('App inicializada', 'success');
  
  // Verificar si hay job_id en URL (para cargar dashboard directo)
  const params = new URLSearchParams(window.location.search);
  const jobFromUrl = params.get('job') || params.get('job_id');
  
  if (jobFromUrl) {
    log(`Detectado job en URL: ${jobFromUrl}`, 'info');
    currentJob = jobFromUrl;
    showDashboard(jobFromUrl);
  }
  
  // Atacher handlers - Formulario
  const form = document.getElementById('analyze-form');
  if (form) {
    form.addEventListener('submit', handleFormSubmit);
  }
  
  // Detectar tipo de fuente mientras el usuario escribe
  const sourceUrlInput = document.getElementById('source_url');
  const sourceTypeHint = document.getElementById('source-type-hint');
  if (sourceUrlInput && sourceTypeHint) {
    sourceUrlInput.addEventListener('input', (e) => {
      const url = e.target.value;
      if (url && url.length > 5) {
        const detectedType = detectSourceType(url);
        if (detectedType) {
          sourceTypeHint.textContent = `🔍 Detectado: ${getSourceTypeName(detectedType)}`;
          sourceTypeHint.style.display = 'block';
          sourceTypeHint.style.color = '#6366f1';
        } else {
          sourceTypeHint.textContent = '⚠️ No se pudo detectar el tipo de fuente';
          sourceTypeHint.style.display = 'block';
          sourceTypeHint.style.color = '#f59e0b';
        }
      } else {
        sourceTypeHint.style.display = 'none';
      }
    });
  }
  
  const backBtn = document.getElementById('backBtn');
  if (backBtn) {
    backBtn.addEventListener('click', resetForm);
  }
  
  const reloadBtn = document.getElementById('reloadBtn');
  if (reloadBtn) {
    reloadBtn.addEventListener('click', () => {
      if (currentJob) showDashboard(currentJob);
    });
  }
  
  const downloadJsonZipBtn = document.getElementById('downloadJsonZipBtn');
  if (downloadJsonZipBtn) {
    downloadJsonZipBtn.addEventListener('click', downloadJsonZip);
  }
  
  // LLM Analysis Buttons
  document.querySelectorAll('.analyze-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const analysisType = e.target.getAttribute('data-analysis');
      const titleMap = {
        'health': '💊 Salud del Inventario',
        'duplicates': '🔀 Análisis de Duplicados',
        'orphans': '👤 Aplicaciones Huérfanas',
        'dependencies': '🔗 Análisis de Dependencias',
        'recommendations': '💡 Recomendaciones',
        'consolidation': '📋 Plan de Consolidación'
      };
      performLLMAnalysis(currentJob, analysisType, titleMap[analysisType] || 'Análisis');
    });
  });

  const closeLlmResultsBtn = document.getElementById('closeLlmResultsBtn');
  if (closeLlmResultsBtn) {
    closeLlmResultsBtn.addEventListener('click', () => {
      const container = document.getElementById('llm-results-container');
      if (container) container.style.display = 'none';
    });
  }
  
  log('Handlers attached', 'info');
});
