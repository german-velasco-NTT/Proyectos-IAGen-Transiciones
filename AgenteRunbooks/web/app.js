// ============================================================
// Runbook Generator Dashboard - JavaScript
// ============================================================

const API_BASE = "";
let currentJobId = null;

// ============================================================
// HELPERS
// ============================================================

function showStatus(message, isError = false) {
  const status = document.getElementById("status");
  if (status) {
    status.textContent = message;
    status.className = `status ${isError ? "error" : ""}`;
  }
}

function showSection(sectionId) {
  const formSection = document.getElementById("form-section");
  const dashboard = document.getElementById("dashboard");

  if (sectionId === "form-section") {
    if (formSection) formSection.classList.remove("hidden");
    if (dashboard) dashboard.classList.add("hidden");
  } else {
    if (formSection) formSection.classList.add("hidden");
    if (dashboard) dashboard.classList.remove("hidden");
  }
}

// ============================================================
// FORM SUBMISSION
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("analyze-form");
  if (form) {
    form.addEventListener("submit", handleFormSubmit);
  }

  const backBtn = document.getElementById("backBtn");
  if (backBtn) {
    backBtn.addEventListener("click", handleBack);
  }

  const reloadBtn = document.getElementById("reloadBtn");
  if (reloadBtn) {
    reloadBtn.addEventListener("click", handleReload);
  }

  const downloadBtn = document.getElementById("downloadJsonBtn");
  if (downloadBtn) {
    downloadBtn.addEventListener("click", handleDownload);
  }

  console.log("✅ Event listeners configurados");
});

async function handleFormSubmit(e) {
  e.preventDefault();

  console.log("📝 Form submitted");

  const form = e.target;
  const formData = new FormData(form);

  const config = {
    repository_url: formData.get("repository_url"),
    token: formData.get("token"),
    project_path: formData.get("project_path") || null,
    ticket_states: (formData.get("ticket_states") || "opened,closed").split(",").map(s => s.trim()),
    min_tickets: parseInt(formData.get("min_tickets")) || 5
  };

  console.log("🔧 Config:", config);

  if (!config.repository_url || !config.token) {
    showStatus("❌ Se requieren URL del repositorio y token", true);
    return;
  }

  showStatus("⏳ Iniciando análisis...");
  // NO mostrar dashboard todavía - esperar a que termine el análisis

  // Mostrar barra de progreso en el formulario
  showProgressBar();

  try {
    console.log("📤 Enviando request a /api/v1/analyze...");

    const response = await fetch(`${API_BASE}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config })
    });

    console.log("📥 Response status:", response.status);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `Error ${response.status}`);
    }

    const job = await response.json();
    currentJobId = job.job_id;

    console.log("✅ Job creado:", currentJobId);
    showStatus("⏳ Analizando tickets... (0%)");

    // Iniciar polling
    setTimeout(() => pollJobStatus(), 500);

  } catch (error) {
    console.error("❌ Error:", error);
    showStatus(`❌ Error: ${error.message}`, true);
    hideProgressBar();
  }
}

// ============================================================
// PROGRESS BAR
// ============================================================

function showProgressBar() {
  const progressDiv = document.getElementById("progress-container");
  if (progressDiv) {
    progressDiv.style.display = "block";
  }
}

function hideProgressBar() {
  const progressDiv = document.getElementById("progress-container");
  if (progressDiv) {
    progressDiv.style.display = "none";
  }
}

function updateProgressBar(progress) {
  const progressBar = document.getElementById("progress-bar");
  const progressText = document.getElementById("progress-text");

  if (progressBar) {
    progressBar.style.width = `${Math.min(progress, 100)}%`;
  }
  if (progressText) {
    progressText.textContent = `${Math.round(progress)}%`;
  }
}

// ============================================================
// POLLING
// ============================================================

function pollJobStatus() {
  if (!currentJobId) {
    console.error("❌ No job ID");
    return;
  }

  console.log("🔄 Polling job:", currentJobId);

  const pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/jobs/${currentJobId}`);

      if (!response.ok) {
        console.error("❌ Job not found");
        clearInterval(pollInterval);
        showStatus("❌ Job no encontrado", true);
        hideProgressBar();
        return;
      }

      const job = await response.json();
      console.log("📊 Job status:", job.status, "Progress:", job.progress);

      // Actualizar progreso en el formulario
      const progressText = `${job.message} (${Math.round(job.progress || 0)}%)`;
      showStatus(progressText);
      updateProgressBar(job.progress || 0);

      // Renderizar análisis SOLO si está completo
      if (job.status === "completed" && job.data) {
        console.log("✅ Job completado - mostrando dashboard");
        clearInterval(pollInterval);
        hideProgressBar();

        // AHORA SÍ mostrar el dashboard con todos los datos
        showSection("dashboard");
        renderDashboard(job.data);
        showStatus("✅ Análisis completado");
      } else if (job.status === "failed") {
        console.error("❌ Job failed");
        clearInterval(pollInterval);
        hideProgressBar();
        showStatus(`❌ Error: ${job.message}`, true);
      }

    } catch (error) {
      console.error("Error polling:", error);
      clearInterval(pollInterval);
      hideProgressBar();
      showStatus(`❌ Error: ${error.message}`, true);
    }
  }, 1000); // Poll cada segundo
}

// ============================================================
// RENDERING
// ============================================================

function renderDashboard(analysis) {
  try {
    console.log("🎨 Renderizando dashboard:", analysis);
    console.log("🔍 Analysis keys:", Object.keys(analysis || {}));

    const { total, opened, closed, severity_distribution, categories, top_issues } = analysis;

    // Estadísticas básicas
    const statTotal = document.getElementById("stat-total");
    const statOpened = document.getElementById("stat-opened");
    const statClosed = document.getElementById("stat-closed");

    console.log("📍 Elements found - total:", !!statTotal, "opened:", !!statOpened, "closed:", !!statClosed);

    if (statTotal) {
      console.log("✏️ Setting stat-total to:", total || 0);
      statTotal.textContent = total || 0;
    }
    if (statOpened) {
      console.log("✏️ Setting stat-opened to:", opened || 0);
      statOpened.textContent = opened || 0;
    }
    if (statClosed) {
      console.log("✏️ Setting stat-closed to:", closed || 0);
      statClosed.textContent = closed || 0;
    }

    // Severidad
    document.getElementById("severity-critical").textContent = severity_distribution?.critical || 0;
    document.getElementById("severity-high").textContent = severity_distribution?.high || 0;
    document.getElementById("severity-medium").textContent = severity_distribution?.medium || 0;
    document.getElementById("severity-low").textContent = severity_distribution?.low || 0;

    // Indicadores de calidad
    const resolutionRate = total > 0 ? Math.round((closed / total) * 100) : 0;
    document.getElementById("resolution-rate").textContent = `${resolutionRate}%`;
    document.getElementById("resolution-bar").style.width = `${resolutionRate}%`;

    const categoryCount = Object.keys(categories || {}).length;
    const categoryPercentage = categoryCount > 0 ? Math.min(100, categoryCount * 10) : 0;
    document.getElementById("category-coverage").textContent = `${categoryPercentage}%`;
    document.getElementById("category-bar").style.width = `${categoryPercentage}%`;

    // Categorías
    const categoriesDiv = document.getElementById("categories");
    if (categoriesDiv) {
      categoriesDiv.innerHTML = "";

      Object.entries(categories || {}).forEach(([label, count]) => {
        const badge = document.createElement("div");
        badge.style.cssText = `
          padding: 0.5rem 1rem;
          background: #1e293b;
          border: 1px solid #334155;
          border-radius: 6px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
        `;
        badge.onmouseover = () => {
          badge.style.borderColor = "#0052cc";
          badge.style.backgroundColor = "#0d1f3f";
        };
        badge.onmouseout = () => {
          badge.style.borderColor = "#334155";
          badge.style.backgroundColor = "#1e293b";
        };

        badge.innerHTML = `
          <div style="font-size: 1.2rem; font-weight: bold; color: #0052cc">${count}</div>
          <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem">${label}</div>
        `;
        categoriesDiv.appendChild(badge);
      });
    }

    // Top issues
    const topIssuesDiv = document.getElementById("top-issues");
    if (topIssuesDiv) {
      topIssuesDiv.innerHTML = "";

      (top_issues || []).forEach((issue, idx) => {
        const issueDiv = document.createElement("div");
        issueDiv.style.cssText = `
          padding: 1rem;
          background: #1e293b;
          border-left: 4px solid;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        `;

        const severityColors = {
          critical: "#ef4444",
          high: "#f97316",
          medium: "#eab308",
          low: "#22c55e"
        };
        issueDiv.style.borderLeftColor = severityColors[issue.severity] || "#94a3b8";

        issueDiv.onmouseover = () => {
          issueDiv.style.backgroundColor = "#334155";
          issueDiv.style.transform = "translateX(5px)";
        };
        issueDiv.onmouseout = () => {
          issueDiv.style.backgroundColor = "#1e293b";
          issueDiv.style.transform = "translateX(0)";
        };

        const labelsHTML = (issue.labels || [])
          .map(l => `<span style="display: inline-block; padding: 0.25rem 0.5rem; background: ${severityColors[issue.severity] || '#0052cc'}30; border-radius: 3px; font-size: 0.75rem; margin-right: 0.25rem; margin-top: 0.25rem">${l}</span>`)
          .join("");

        issueDiv.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <div>
              <h4 style="margin: 0 0 0.5rem 0; color: #e2e8f0">#${idx + 1}</h4>
              <p style="margin: 0 0 0.5rem 0; color: #cbd5e1; font-size: 0.9rem">${issue.title}</p>
              <div>${labelsHTML}</div>
            </div>
            <span style="padding: 0.25rem 0.75rem; background: ${severityColors[issue.severity] || '#94a3b8'}30; color: ${severityColors[issue.severity] || '#94a3b8'}; border-radius: 3px; font-size: 0.75rem; font-weight: bold">
              ${issue.severity.toUpperCase()}
            </span>
          </div>
        `;
        topIssuesDiv.appendChild(issueDiv);
      });
    }

    // Resumen
    const summaryDiv = document.getElementById("summary");
    if (summaryDiv) {
      summaryDiv.innerHTML = `
        <h3>📊 Resumen del Análisis</h3>
        <div style="color: #cbd5e1; line-height: 1.8;">
          <p><strong>Total de Tickets:</strong> ${total}</p>
          <p><strong>Resueltos:</strong> ${closed} (${resolutionRate}%)</p>
          <p><strong>Abiertos:</strong> ${opened}</p>
          <p><strong>Categorías Identificadas:</strong> ${categoryCount}</p>
          <p style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #334155; color: #94a3b8; font-size: 0.9rem">
            Este análisis identifica patrones en tickets históricos para estandarizar procesos operativos.
            Las categorías y severidades detectadas permiten generar SOPs (Standard Operating Procedures) eficaces.
          </p>
        </div>
      `;
    }

    // Runbook generado con IA
    const runbookContent = analysis.runbook_content;
    const runbookSection = document.getElementById("runbook-section");
    const runbookContentDiv = document.getElementById("runbook-content");

    if (runbookContent && runbookSection && runbookContentDiv) {
      console.log("📋 Renderizando runbook content...");
      runbookSection.style.display = "block";
      runbookContentDiv.textContent = runbookContent;
    } else {
      console.log("⚠️ No runbook content found in analysis");
      if (runbookSection) {
        runbookSection.style.display = "none";
      }
    }

    console.log("✅ Dashboard renderizado exitosamente");


  } catch (error) {
    console.error("❌ Error renderizando:", error);
    showStatus(`❌ Error en interfaz: ${error.message}`, true);
  }
}

// ============================================================
// BUTTON HANDLERS
// ============================================================

function handleBack() {
  console.log("← Volviendo al formulario");
  currentJobId = null;
  showSection("form-section");
  const form = document.getElementById("analyze-form");
  if (form) form.reset();
  showStatus("");
  hideProgressBar();
}

function handleReload() {
  console.log("🔄 Recargando...");
  if (currentJobId) {
    showStatus("🔄 Recargando...");
    showProgressBar();
    pollJobStatus();
  }
}

async function handleDownload() {
  if (!currentJobId) return;

  try {
    const response = await fetch(`${API_BASE}/api/v1/jobs/${currentJobId}/download`);
    if (!response.ok) throw new Error("No se puede descargar");

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analysis_${currentJobId}.json`;
    a.click();
    window.URL.revokeObjectURL(url);

    showStatus("✅ Descarga completada");
  } catch (error) {
    console.error("Download error:", error);
    showStatus(`❌ Error en descarga: ${error.message}`, true);
  }
}

// ============================================================
// LLM ANALYSIS
// ============================================================

async function analyzeLLM(analysisType) {
  if (!currentJobId) {
    showStatus("❌ No hay job activo", true);
    return;
  }

  const resultDiv = document.getElementById("llm-analysis-result");
  const titleDiv = document.getElementById("llm-analysis-title");
  const contentDiv = document.getElementById("llm-analysis-content");

  if (!resultDiv || !titleDiv || !contentDiv) return;

  // Mostrar loading
  resultDiv.style.display = "block";
  titleDiv.textContent = "⏳ Analizando...";
  contentDiv.textContent = "Procesando análisis con IA...";

  try {
    const response = await fetch(`${API_BASE}/api/v1/jobs/${currentJobId}/llm/${analysisType}`, {
      method: "POST"
    });

    if (!response.ok) {
      throw new Error(`Error ${response.status}`);
    }

    const result = await response.json();

    const titles = {
      'security': '🔒 Auditoría de Seguridad',
      'completeness': '✅ Verificación de Completitud',
      'simplification': '📋 Simplificación'
    };

    titleDiv.textContent = titles[analysisType] || 'Análisis';
    contentDiv.textContent = result.analysis || 'Sin resultados';

  } catch (error) {
    console.error("LLM Analysis error:", error);
    titleDiv.textContent = "❌ Error";
    contentDiv.textContent = `Error en análisis: ${error.message}`;
  }
}
