/**
 * app.js - Frontend logic for API Analysis Dashboard
 * Maneja polling de jobs, visualización de datos y generación de reports
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
 * ══════════════════════════════════════════════════════════════════════
 * UTILIDADES
 * ══════════════════════════════════════════════════════════════════════
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
 * ══════════════════════════════════════════════════════════════════════
 * JOB MANAGEMENT
 * ══════════════════════════════════════════════════════════════════════
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
  
  // Actualizar UI con progreso - Mantener formulario visible
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
    
    // Ir al dashboard pero mantener el formulario visible
    showDashboard(jobId);
    return;
  }
  
  // Si falla
  if (status.status === 'failed') {
    log(`❌ Job falló`, 'error');
    clearInterval(pollingInterval);
    const error = status.error || 'Error desconocido';
    showStatus(`Error en análisis: ${error}`, 'error');
    
    // Mostrar botón para volver a intentar
    const statusEl = document.getElementById('status');
    if (statusEl) {
      const html = `
        <p class="error">❌ El análisis falló: ${error}</p>
        <p style="margin-top:10px;font-size:14px;color:#94a3b8;">
          Verifica las credenciales de GitLab y vuelve a intentar.
        </p>
        <button onclick="resetForm()" style="margin-top:10px;">← Volver</button>
      `;
      statusEl.innerHTML = html;
      statusEl.style.display = 'block';
    }
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

function renderDashboard(analysisData, jobId) {
  const analysis = analysisData.analysis_data || analysisData;
  const summary = analysis.api_summary || {};
  
  // Renderizar resumen
  const summaryEl = document.getElementById('summary');
  if (summaryEl) {
    const metrics = [
      { label: 'Especificaciones', value: summary.total_specs || 0 },
      { label: 'APIs en Código', value: summary.total_code_apis || 0 },
      { label: 'Endpoints', value: summary.total_endpoints || 0 },
      { label: 'REST APIs', value: summary.api_types?.rest || 0 },
      { label: 'GraphQL', value: summary.api_types?.graphql || 0 },
    ];
    
    summaryEl.innerHTML = `
      <h2>📊 Resumen Ejecutivo</h2>
      <div class="metrics-grid">
        ${metrics.map(m => `
          <div class="metric">
            <div class="metric-label">${m.label}</div>
            <div class="metric-value">${m.value}</div>
          </div>
        `).join('')}
      </div>
    `;
  }
  
  // Renderizar tabla de especificaciones
  if (analysis.specs && analysis.specs.length > 0) {
    const tbody = document.querySelector('#specs-table tbody');
    if (tbody) {
      tbody.innerHTML = analysis.specs.map(spec => `
        <tr>
          <td>${spec.file_path || 'Especificación'}</td>
          <td>${spec.spec_type || 'OpenAPI'}</td>
          <td>${spec.api_title || '-'}</td>
          <td>${(spec.endpoints || []).length}</td>
          <td>${spec.api_version || '-'}</td>
        </tr>
      `).join('');
    }
    document.getElementById('specs-section').style.display = 'block';
  }
  
  // Renderizar tabla de APIs en código
  if (analysis.code_apis && analysis.code_apis.length > 0) {
    const tbody = document.querySelector('#code-apis-table tbody');
    if (tbody) {
      tbody.innerHTML = analysis.code_apis.map(api => `
        <tr>
          <td>${api.file_path || '-'}</td>
          <td>${api.language || '-'}</td>
          <td>${api.total_endpoints || 0}</td>
          <td>${(api.authentication || []).join(', ') || 'Ninguna'}</td>
        </tr>
      `).join('');
    }
    document.getElementById('code-apis-section').style.display = 'block';
  }
  
  // Mostrar sección de insights
  const insightsSection = document.getElementById('insights-section');
  if (insightsSection) {
    insightsSection.classList.remove('hidden');
  }
  
  // Guardar datos globales
  window.analysisData = analysisData;
}

/**
 * ══════════════════════════════════════════════════════════════════════
 * FORMULARIO
 * ══════════════════════════════════════════════════════════════════════
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
  
  // Recolectar datos del formulario
  const config = {
    gitlab_url: formData.get('repository_url') || formData.get('gitlab_url'),
    gitlab_token: formData.get('token') || formData.get('gitlab_token'),
    project_path: formData.get('project_path') || undefined,
    auto_discover_groups: formData.get('auto_discover_groups') === 'true',
    analysis_mode: formData.get('analysis_mode') || 'basic',
    use_ai_analysis: true
  };
  
  // Validar
  if (!config.gitlab_url) {
    showStatus('Debes ingresar la URL del repositorio', 'error');
    return;
  }
  
  if (!config.gitlab_token) {
    showStatus('Debes ingresar el token de GitLab', 'error');
    return;
  }
  
  // Limpiar valores vacíos
  Object.keys(config).forEach(key => {
    if (config[key] === undefined || config[key] === '') {
      delete config[key];
    }
  });
  
  log(`Configuración: ${JSON.stringify(config)}`, 'info');
  submitAnalysis(config);
}

/**
 * ══════════════════════════════════════════════════════════════════════
 * DESCARGA
 * ══════════════════════════════════════════════════════════════════════
 */

function downloadJsonZip() {
  const jobId = currentJob || getLastJobId();
  
  if (!jobId) {
    showStatus('No hay job activo', 'warn');
    return;
  }
  
  log(`Descargando ZIP para job ${jobId}...`, 'loading');
  showStatus('Descargando archivo...', 'info');
  
  // Crear link temporal para descarga
  const link = document.createElement('a');
  link.href = `${API}/api/v1/download/${jobId}`;
  link.download = `api-analysis-${jobId.slice(0, 8)}.zip`;
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
 * ══════════════════════════════════════════════════════════════════════
 * LLM ANALYSIS
 * ══════════════════════════════════════════════════════════════════════
 */

async function loadInsights() {
  if (!currentJob || !window.analysisData) {
    showStatus('No hay datos de análisis', 'warn');
    return;
  }
  
  try {
    log('Generando insights...', 'loading');
    
    const analysis = window.analysisData.analysis_data || window.analysisData;
    const summary = analysis.api_summary || {};
    
    const response = await fetch(`${API}/api/v1/jobs/${currentJob}/llm-analysis?v=${CACHE_BUSTER}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        context: `Especificaciones: ${summary.total_specs}, APIs en Código: ${summary.total_code_apis}, Endpoints: ${summary.total_endpoints}`
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const result = await response.json();
    
    const insightsContent = document.getElementById('insights-content');
    if (insightsContent) {
      insightsContent.innerHTML = `
        <div style="background:#0f172a;padding:15px;border-radius:6px;border-left:4px solid #8b5cf6;">
          <div style="white-space:pre-wrap;line-height:1.6;color:#cbd5e1;font-size:14px;">
            ${result.insights || 'Sin insights disponibles'}
          </div>
        </div>
      `;
    }
    
    log('Insights generados', 'success');
  } catch (error) {
    log(`Error generando insights: ${error.message}`, 'error');
    const insightsContent = document.getElementById('insights-content');
    if (insightsContent) {
      insightsContent.innerHTML = `<p style="color:#ef4444;">Error: ${error.message}</p>`;
    }
  }
}

/**
 * Ejecuta análisis LLM para un tipo específico
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
          <div style="height:100%;background:linear-gradient(90deg,#6366f1,#8b5cf6);width:100%;animation:shimmer 1.5s infinite;">
          </div>
        </div>
      </div>
      <style>
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      </style>
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
    
    if (data.success) {
      resultTitle.textContent = title;
      resultContent.innerHTML = `<div style="white-space:pre-wrap;line-height:1.6;">${data.analysis || 'Análisis completado sin resultados'}</div>`;
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
 * ══════════════════════════════════════════════════════════════════════
 * INICIALIZACIÓN
 * ══════════════════════════════════════════════════════════════════════
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
  
  // Atacher handlers
  const form = document.getElementById('analyze-form');
  if (form) {
    form.addEventListener('submit', handleFormSubmit);
  }
  
  const backBtn = document.getElementById('backBtn');
  if (backBtn) {
    backBtn.addEventListener('click', resetForm);
  }
  
  const reloadBtn = document.getElementById('reloadBtn');
  if (reloadBtn && currentJob) {
    reloadBtn.addEventListener('click', () => showDashboard(currentJob));
  }
  
  const downloadJsonZipBtn = document.getElementById('downloadJsonZipBtn');
  if (downloadJsonZipBtn) {
    downloadJsonZipBtn.addEventListener('click', downloadJsonZip);
  }
  
  // LLM Analysis Buttons - Sin verificar currentJob aqui, ya que performLLMAnalysis lo verifica
  const analyzeArchitectureBtn = document.getElementById('analyzeArchitectureBtn');
  if (analyzeArchitectureBtn) {
    analyzeArchitectureBtn.addEventListener('click', () => performLLMAnalysis(currentJob, 'architecture', 'Analisis de Arquitectura'));
  }
  
  const analyzeSecurityBtn = document.getElementById('analyzeSecurityBtn');
  if (analyzeSecurityBtn) {
    analyzeSecurityBtn.addEventListener('click', () => performLLMAnalysis(currentJob, 'security', 'Analisis de Seguridad'));
  }
  
  const analyzePerformanceBtn = document.getElementById('analyzePerformanceBtn');
  if (analyzePerformanceBtn) {
    analyzePerformanceBtn.addEventListener('click', () => performLLMAnalysis(currentJob, 'performance', 'Optimizacion de Rendimiento'));
  }
  
  const analyzeCompatibilityBtn = document.getElementById('analyzeCompatibilityBtn');
  if (analyzeCompatibilityBtn) {
    analyzeCompatibilityBtn.addEventListener('click', () => performLLMAnalysis(currentJob, 'compatibility', 'Analisis de Compatibilidad'));
  }
  
  const generateDocumentationBtn = document.getElementById('generateDocumentationBtn');
  if (generateDocumentationBtn) {
    generateDocumentationBtn.addEventListener('click', () => performLLMAnalysis(currentJob, 'documentation', 'Generacion de Documentacion'));
  }
  
  const generateMigrationPlanBtn = document.getElementById('generateMigrationPlanBtn');
  if (generateMigrationPlanBtn) {
    generateMigrationPlanBtn.addEventListener('click', () => performLLMAnalysis(currentJob, 'migration', 'Plan de Migracion'));
  }

  const closeLlmResultsBtn = document.getElementById('closeLlmResultsBtn');
  if (closeLlmResultsBtn) {
    closeLlmResultsBtn.addEventListener('click', () => {
      const container = document.getElementById('llm-results-container');
      if (container) container.style.display = 'none';
    });
  }
  
  log('Handlers attached', 'info');
});
