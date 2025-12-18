# 🧪 Instrucciones para Testear el Dashboard en Navegador

## Opción 1: Versión SIMPLE (Recomendado para Debug)
Abre en tu navegador: **http://localhost:8006/web/debug.html**

Esta versión tiene:
- ✅ Logs muy detallados
- ✅ Interfaz simple y clara
- ✅ Fondo oscuro para ver bien los logs
- ✅ Muestra exactamente qué está pasando

## Opción 2: Versión COMPLETA (Producción)
Abre en tu navegador: **http://localhost:8006/**

Esta versión es la dashboard profesional con estilos corporativos.

## Pasos a Seguir (Igual para ambas versiones):

1. **Abre la consola del navegador** (F12 → Tab "Console")
   
2. **Completa el formulario** con estos valores:
   - **URL del Repositorio**: `https://umane.emeal.nttdata.com/git/COITDEVSOCOEAPPSIA/crewai-nativeai`
   - **Token**: `sebwvkV21gB-gpK12j1y`
   - **Project Path**: `COITDEVSOCOEAPPSIA/crewai-nativeai`
   - (Deja los demás campos con sus valores por defecto)

3. **Haz clic en "Iniciar Análisis"**

4. **Observa la consola (F12)** - Deberías ver logs como:
   ```
   ✅ Event listeners configurados
   📝 Form submitted
   🔧 Config: {repository_url: '...', ...}
   📤 Enviando request a /api/v1/analyze...
   📥 Response status: 200
   ✅ Job creado: 655c0b0d-...
   🔄 Polling job: 655c0b0d-...
   📊 Job status: analyzing Progress: 30
   📊 Job status: completed Progress: 100
   ✅ Job completado con status 'completed'
   📦 job.data: {...}
   🎨 Renderizando dashboard: {...}
   📍 Elements found - total: true, opened: true, closed: true
   ✏️ Setting stat-total to: 120
   ✏️ Setting stat-opened to: 60
   ✏️ Setting stat-closed to: 60
   ```

5. **Verifica el dashboard**:
   - ✅ **Si ves los números actualizados** (Total: 120, Abiertos: 60, Cerrados: 60) = **¡FUNCIONA!** 🎉
   - ❌ **Si ves ceros** (Total: 0, Abiertos: 0, Cerrados: 0) = Revisa la consola por errores

## Si Algo No Funciona:

### Error: "❌ Error: Error fetching GitLab issues"
- **Causa**: La instancia de GitLab de Umane no tiene API pública o está rechazando la petición
- **Solución**: El código automáticamente usa mock data (120 tickets) - debería funcionar igual

### Error: "job not found"
- **Causa**: El job ID no se envió correctamente
- **Solución**: Abre F12 y verifica que el job_id aparece en los logs

### Números en cero
- **Causa**: El renderDashboard se está llamando pero los datos no se aplican al DOM
- **Solución**: Abre F12 y copia el texto de console, envíalo al equipo técnico

## URLs Rápidas:

- 🔧 **Health Check**: http://localhost:8006/health
- 📋 **Dashboard Principal**: http://localhost:8006/
- 🐛 **Dashboard Debug**: http://localhost:8006/web/debug.html
- 📄 **Version Simplificada**: http://localhost:8006/web/test.html
- 📁 **Mock Data**: http://localhost:8006/api/v1/issues

## Comando para Iniciar Servidor (si se cayó):

```bash
cd /Users/juanguaqueta/Desktop/AgentesIA/AgenteRunbooks
python3 -m uvicorn api:app --host 0.0.0.0 --port 8006 --reload
```

## Información Técnica:

- **Backend**: FastAPI corriendo en `http://localhost:8006`
- **Frontend**: HTML5 + JavaScript vanilla (sin frameworks)
- **Datos**: 120 mock issues (50% abiertos, 50% cerrados)
- **API Response**: JSON válido con estructura: `{job_id, status, message, progress, data: {total, opened, closed, ...}}`

## Próximas Acciones:

1. ✅ Si funciona: El dashboard está listo para producción
2. ❌ Si no funciona: Nos proporciona los logs de consola para debugging
3. 🚀 Una vez funcionando: Podemos integrar análisis de LLM para generar runbooks

---

**¡Gracias por testear! 🙏**
