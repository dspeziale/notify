/**
 * Notification Gateway - Enterprise Administration Dashboard Client
 * Pure modern ES6+ vanilla implementation, no external dependencies.
 */

// Global State
const state = {
  adminKey: sessionStorage.getItem('ng_admin_key') || localStorage.getItem('ng_admin_key') || '',
  activeTab: 'overview',
  stats: null,
  health: null,
  applications: [],
  telegramConfigs: [],
  gmailConfigs: [],
  notifications: [],
  auditLogs: [],
};

// DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
  initKeyManagement();
  initNavigation();
  initDialogFallbacks();
  initFormHandlers();
  
  // Initial data load
  refreshAllData();

  // Auto-refresh stats every 30 seconds
  setInterval(() => {
    if (state.activeTab === 'overview') {
      loadStats();
      loadHealth();
    }
  }, 30000);
});

/* ==============================================================================
   API HELPER & AUTHENTICATION
   ============================================================================== */

function getHeaders(extraHeaders = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...extraHeaders
  };
  if (state.adminKey) {
    headers['X-Admin-API-Key'] = state.adminKey;
  }
  return headers;
}

async function apiCall(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : endpoint;
  const config = {
    ...options,
    headers: getHeaders(options.headers || {})
  };

  try {
    const res = await fetch(url, config);
    if (res.status === 401) {
      showToast('Autenticazione richiesta. Inserisci una Admin API Key valida in alto a destra.', 'error');
      updateAuthStatus(false);
      throw new Error('Unauthorized');
    }
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const errMsg = json?.error?.message || json?.message || `Errore HTTP ${res.status}`;
      showToast(errMsg, 'error');
      throw new Error(errMsg);
    }
    updateAuthStatus(true);
    return json;
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      console.error(`API Error on ${endpoint}:`, err);
    }
    throw err;
  }
}

function initKeyManagement() {
  const keyInput = document.getElementById('adminKeyInput');
  if (keyInput) {
    keyInput.value = state.adminKey;
    keyInput.addEventListener('change', (e) => {
      state.adminKey = e.target.value.trim();
      sessionStorage.setItem('ng_admin_key', state.adminKey);
      localStorage.setItem('ng_admin_key', state.adminKey);
      refreshAllData();
      showToast('Admin API Key aggiornata.', 'info');
    });
  }
}

function updateAuthStatus(isConnected) {
  const badge = document.getElementById('authStatusBadge');
  if (!badge) return;
  if (isConnected && state.adminKey) {
    badge.className = 'health-badge';
    badge.innerHTML = '<span class="health-dot"></span> Autenticato';
  } else {
    badge.className = 'badge badge-danger';
    badge.innerHTML = 'Non Autenticato';
  }
}

/* ==============================================================================
   NAVIGATION & TABS
   ============================================================================== */

function initNavigation() {
  const navLinks = document.querySelectorAll('.nav-link');
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = link.getAttribute('data-tab');
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  state.activeTab = tabId;
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

  const activeLink = document.querySelector(`.nav-link[data-tab="${tabId}"]`);
  const activePanel = document.getElementById(`tab-${tabId}`);
  if (activeLink) activeLink.classList.add('active');
  if (activePanel) activePanel.classList.add('active');

  const titles = {
    overview: 'Panoramica & Stato Gateway',
    applications: 'Applicazioni & API Key Client',
    telegram: 'Integrazioni Bot Telegram',
    gmail: 'Integrazioni Gmail & Server SMTP',
    dispatcher: 'Sandbox Invio Notifiche Live',
    notifications: 'Storico & Tracking Consegne',
    audit: 'Audit Log di Sicurezza',
  };
  const topTitle = document.getElementById('topbarTitle');
  if (topTitle && titles[tabId]) {
    topTitle.textContent = titles[tabId];
  }

  // Trigger tab data fetch
  if (tabId === 'overview') { loadStats(); loadHealth(); loadRecentNotifications(); }
  else if (tabId === 'applications') loadApplications();
  else if (tabId === 'telegram') loadTelegramConfigs();
  else if (tabId === 'gmail') loadGmailConfigs();
  else if (tabId === 'dispatcher') initDispatcherSelectors();
  else if (tabId === 'notifications') loadAllNotifications();
  else if (tabId === 'audit') loadAuditLogs();
}

function refreshAllData() {
  loadHealth();
  loadStats();
  loadApplications();
  loadTelegramConfigs();
  loadGmailConfigs();
}

/* ==============================================================================
   MODAL LIGHT-DISMISS FALLBACK (modern-web-guidance)
   ============================================================================== */

function initDialogFallbacks() {
  if (!('closedBy' in HTMLDialogElement.prototype)) {
    const outside = (e, dialog) => {
      const r = dialog.getBoundingClientRect();
      return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
    };
    for (const dialog of document.querySelectorAll('dialog[closedby="any"]')) {
      let pressedOutside = false;
      dialog.addEventListener('pointerdown', (e) => { pressedOutside = outside(e, dialog); });
      dialog.addEventListener('pointerup', (e) => { if (pressedOutside && outside(e, dialog)) dialog.close(); });
    }
  }

  // Close buttons
  document.querySelectorAll('[data-dialog-close]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const dialog = e.target.closest('dialog');
      if (dialog) dialog.close();
    });
  });
}

/* ==============================================================================
   OVERVIEW & HEALTH
   ============================================================================== */

async function loadHealth() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    state.health = data;
    
    document.getElementById('healthStatusText').textContent = data.status.toUpperCase();
    document.getElementById('healthUptimeText').textContent = formatSeconds(data.uptime_seconds);
    document.getElementById('healthEnvText').textContent = data.environment;
    document.getElementById('healthDbText').textContent = data.components?.database || 'N/A';
    document.getElementById('healthRedisText').textContent = data.components?.redis || 'N/A';
    document.getElementById('healthCryptoText').textContent = data.components?.encryption || 'N/A';
  } catch (err) {
    console.error('Failed to load health:', err);
  }
}

async function loadStats() {
  try {
    const res = await apiCall('/api/v1/admin/stats');
    if (res?.data) {
      state.stats = res.data;
      document.getElementById('statTotalApps').textContent = res.data.applications.total;
      document.getElementById('statActiveApps').textContent = `${res.data.applications.active} attive`;
      document.getElementById('statTelegramConfigs').textContent = res.data.telegram.total_configs;
      document.getElementById('statGmailConfigs').textContent = res.data.gmail.total_configs;
      document.getElementById('statTotalNotifs').textContent = res.data.notifications.total;
      document.getElementById('statSuccessRate').textContent = `${res.data.notifications.success_rate}% successo`;
    }
  } catch (err) {
    // handled in apiCall
  }
}

async function loadRecentNotifications() {
  try {
    const res = await apiCall('/api/v1/admin/notifications?limit=8');
    const container = document.getElementById('recentNotificationsTbody');
    if (!container) return;

    if (!res.data || res.data.length === 0) {
      container.innerHTML = `<tr><td colspan="6" class="empty-state">Nessuna notifica registrata finora.</td></tr>`;
      return;
    }

    container.innerHTML = res.data.map(n => `
      <tr>
        <td class="mono">${n.id.substring(0, 8)}...</td>
        <td><span class="badge ${n.provider === 'telegram' ? 'badge-active' : 'badge-neutral'}">${n.provider}</span></td>
        <td>${escapeHtml(n.recipient_summary || n.configuration_id.substring(0, 8))}</td>
        <td><span class="badge badge-${n.status}">${n.status}</span></td>
        <td>${n.attempts_count}</td>
        <td>${formatDate(n.created_at)}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load recent notifications:', err);
  }
}

/* ==============================================================================
   APPLICATIONS & API KEYS
   ============================================================================== */

async function loadApplications() {
  try {
    const res = await apiCall('/api/v1/admin/applications');
    state.applications = res.data || [];
    renderApplicationsTable();
    populateAppDropdowns();
  } catch (err) {
    console.error('Failed to load applications:', err);
  }
}

function renderApplicationsTable() {
  const tbody = document.getElementById('applicationsTbody');
  if (!tbody) return;

  if (state.applications.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Nessuna applicazione registrata. Clicca su "+ Nuova Applicazione" per iniziare.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.applications.map(app => {
    const permissions = (app.permissions || []).map(p => `<span class="badge badge-neutral">${p}</span>`).join(' ') || '<span class="text-muted">Nessuno</span>';
    const isActive = app.status === 'active';
    return `
      <tr>
        <td>
          <div style="font-weight: 600;">${escapeHtml(app.name)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(app.description || 'Nessuna descrizione')}</div>
        </td>
        <td class="mono">${app.id.substring(0, 8)}...</td>
        <td><span class="badge badge-${isActive ? 'active' : 'disabled'}">${app.status}</span></td>
        <td>${permissions}</td>
        <td>${app.rate_limit_per_minute} req/m</td>
        <td>${formatDate(app.created_at)}</td>
        <td>
          <div style="display: flex; gap: 0.35rem;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="promptRegenerateKey('${app.id}', '${escapeHtml(app.name)}')">Rigenera Key</button>
            <button type="button" class="btn ${isActive ? 'btn-danger' : 'btn-secondary'} btn-sm" onclick="toggleAppStatus('${app.id}', '${isActive ? 'disabled' : 'active'}')">
              ${isActive ? 'Disabilita' : 'Attiva'}
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function toggleAppStatus(appId, newStatus) {
  try {
    await apiCall(`/api/v1/admin/applications/${appId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: newStatus })
    });
    showToast(`Stato applicazione aggiornato a '${newStatus}'.`, 'success');
    loadApplications();
    loadStats();
  } catch (err) {
    // handled
  }
}

async function promptRegenerateKey(appId, appName) {
  if (!confirm(`Sei sicuro di voler rigenerare la API Key per l'applicazione "${appName}"? La chiave precedente smetterà immediatamente di funzionare.`)) {
    return;
  }
  try {
    const res = await apiCall(`/api/v1/admin/applications/${appId}/api-key/regenerate`, {
      method: 'POST'
    });
    if (res?.data?.raw_api_key) {
      showApiKeyRevealModal(appName, res.data.raw_api_key);
      loadApplications();
    }
  } catch (err) {
    // handled
  }
}

function showApiKeyRevealModal(appName, rawKey) {
  const dialog = document.getElementById('keyRevealDialog');
  const title = document.getElementById('revealAppName');
  const keyDisplay = document.getElementById('revealKeyDisplay');
  if (title) title.textContent = appName;
  if (keyDisplay) keyDisplay.textContent = rawKey;
  if (dialog) dialog.showModal();
}

/* ==============================================================================
   TELEGRAM INTEGRATIONS
   ============================================================================== */

async function loadTelegramConfigs() {
  try {
    const res = await apiCall('/api/v1/admin/telegram');
    state.telegramConfigs = res.data || [];
    renderTelegramTable();
  } catch (err) {
    console.error('Failed to load telegram configs:', err);
  }
}

function renderTelegramTable() {
  const tbody = document.getElementById('telegramTbody');
  if (!tbody) return;

  if (state.telegramConfigs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Nessuna configurazione Telegram creata.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.telegramConfigs.map(c => {
    const app = state.applications.find(a => a.id === c.application_id);
    const appName = app ? app.name : c.application_id.substring(0, 8);
    const isActive = c.is_active;

    return `
      <tr>
        <td>
          <div style="font-weight: 600;">${escapeHtml(c.name)}</div>
          <div class="mono" style="font-size: 0.75rem; color: var(--text-muted);">${c.id}</div>
        </td>
        <td>${escapeHtml(appName)}</td>
        <td class="mono">${escapeHtml(c.chat_id || 'Non specificato')}</td>
        <td><span class="badge badge-${isActive ? 'active' : 'disabled'}">${isActive ? 'Attivo' : 'Disattivato'}</span></td>
        <td>${formatDate(c.created_at)}</td>
        <td>
          <div style="display: flex; gap: 0.35rem;">
            <button type="button" class="btn btn-primary btn-sm" onclick="openTestTelegramModal('${c.id}', '${escapeHtml(c.name)}', '${c.chat_id || ''}')">Test Invia</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="toggleTelegramStatus('${c.id}', ${!isActive})">${isActive ? 'Disabilita' : 'Attiva'}</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function toggleTelegramStatus(configId, newActive) {
  try {
    await apiCall(`/api/v1/admin/telegram/${configId}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: newActive })
    });
    showToast(`Configurazione Telegram ${newActive ? 'attivata' : 'disattivata'}.`, 'success');
    loadTelegramConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

function openTestTelegramModal(configId, name, defaultChatId) {
  const dialog = document.getElementById('testTelegramDialog');
  document.getElementById('testTgConfigId').value = configId;
  document.getElementById('testTgConfigName').textContent = name;
  document.getElementById('testTgChatId').value = defaultChatId || '';
  document.getElementById('testTgMessage').value = `<b>Notifica di Test</b> dal Gateway!\nConfigurazione: ${name}\nData: ${new Date().toLocaleString()}`;
  document.getElementById('testTgResult').style.display = 'none';
  dialog.showModal();
}

/* ==============================================================================
   GMAIL & SMTP INTEGRATIONS
   ============================================================================== */

async function loadGmailConfigs() {
  try {
    const res = await apiCall('/api/v1/admin/gmail');
    state.gmailConfigs = res.data || [];
    renderGmailTable();
  } catch (err) {
    console.error('Failed to load gmail configs:', err);
  }
}

function renderGmailTable() {
  const tbody = document.getElementById('gmailTbody');
  if (!tbody) return;

  if (state.gmailConfigs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Nessuna configurazione Gmail/SMTP creata.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.gmailConfigs.map(c => {
    const app = state.applications.find(a => a.id === c.application_id);
    const appName = app ? app.name : c.application_id.substring(0, 8);
    const isActive = c.is_active;
    const authBadge = c.auth_type === 'app_password' 
      ? '<span class="badge badge-neutral">App Password (SMTP)</span>' 
      : '<span class="badge badge-active">Google OAuth2</span>';

    return `
      <tr>
        <td>
          <div style="font-weight: 600;">${escapeHtml(c.name)}</div>
          <div class="mono" style="font-size: 0.75rem; color: var(--text-muted);">${c.id}</div>
        </td>
        <td>${escapeHtml(appName)}</td>
        <td>${authBadge}</td>
        <td>${escapeHtml(c.username || c.from_email || 'N/A')}</td>
        <td class="mono">${escapeHtml(c.smtp_host || 'smtp.gmail.com')}:${c.smtp_port || 587}</td>
        <td><span class="badge badge-${isActive ? 'active' : 'disabled'}">${isActive ? 'Attivo' : 'Disattivato'}</span></td>
        <td>
          <div style="display: flex; gap: 0.35rem;">
            <button type="button" class="btn btn-primary btn-sm" onclick="openTestGmailModal('${c.id}', '${escapeHtml(c.name)}', '${c.username || c.from_email || ''}')">Test Invia</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="toggleGmailStatus('${c.id}', ${!isActive})">${isActive ? 'Disabilita' : 'Attiva'}</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function toggleGmailStatus(configId, newActive) {
  try {
    await apiCall(`/api/v1/admin/gmail/${configId}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: newActive })
    });
    showToast(`Configurazione Gmail/SMTP ${newActive ? 'attivata' : 'disattivata'}.`, 'success');
    loadGmailConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

function openTestGmailModal(configId, name, defaultEmail) {
  const dialog = document.getElementById('testGmailDialog');
  document.getElementById('testGmailConfigId').value = configId;
  document.getElementById('testGmailConfigName').textContent = name;
  document.getElementById('testGmailRecipient').value = defaultEmail || '';
  document.getElementById('testGmailSubject').value = `Test Notifica Email da Gateway: ${name}`;
  document.getElementById('testGmailBody').value = `<h1>Notifica Gateway</h1><p>Questa è un'email di prova inviata con successo tramite il Gateway!</p><p>Data: ${new Date().toLocaleString()}</p>`;
  document.getElementById('testGmailResult').style.display = 'none';
  dialog.showModal();
}

/* ==============================================================================
   DISPATCHER SANDBOX
   ============================================================================== */

function initDispatcherSelectors() {
  const providerSelect = document.getElementById('sandboxProvider');
  const configSelect = document.getElementById('sandboxConfig');
  const tgFields = document.getElementById('sandboxTelegramFields');
  const emailFields = document.getElementById('sandboxEmailFields');

  function updateFields() {
    const provider = providerSelect.value;
    if (provider === 'telegram') {
      tgFields.style.display = 'block';
      emailFields.style.display = 'none';
      configSelect.innerHTML = state.telegramConfigs.map(c => `
        <option value="${c.id}">${escapeHtml(c.name)} (${c.id.substring(0, 8)}...)</option>
      `).join('') || '<option value="">Nessun bot Telegram configurato</option>';
    } else {
      tgFields.style.display = 'none';
      emailFields.style.display = 'block';
      configSelect.innerHTML = state.gmailConfigs.map(c => `
        <option value="${c.id}">${escapeHtml(c.name)} (${c.username || 'SMTP'})</option>
      `).join('') || '<option value="">Nessuna config Gmail/SMTP presente</option>';
    }
  }

  providerSelect.onchange = updateFields;
  updateFields();
}

/* ==============================================================================
   NOTIFICATIONS HISTORY
   ============================================================================== */

async function loadAllNotifications() {
  try {
    const statusFilter = document.getElementById('filterNotifStatus')?.value || '';
    const providerFilter = document.getElementById('filterNotifProvider')?.value || '';
    
    let url = '/api/v1/admin/notifications?limit=50';
    if (statusFilter) url += `&status=${statusFilter}`;
    if (providerFilter) url += `&provider=${providerFilter}`;

    const res = await apiCall(url);
    state.notifications = res.data || [];
    renderNotificationsTable();
  } catch (err) {
    console.error('Failed to load notifications history:', err);
  }
}

function renderNotificationsTable() {
  const tbody = document.getElementById('notificationsTbody');
  if (!tbody) return;

  if (state.notifications.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Nessuna notifica trovata con i filtri selezionati.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.notifications.map(n => {
    return `
      <tr>
        <td class="mono">${n.id.substring(0, 8)}...</td>
        <td><span class="badge ${n.provider === 'telegram' ? 'badge-active' : 'badge-neutral'}">${n.provider}</span></td>
        <td>${escapeHtml(n.recipient_summary || n.configuration_id.substring(0, 8))}</td>
        <td><span class="badge badge-${n.status}">${n.status}</span></td>
        <td>${n.attempts_count}</td>
        <td>${formatDate(n.created_at)}</td>
        <td>
          <button type="button" class="btn btn-secondary btn-sm" onclick="inspectNotificationAttempts('${n.id}')">Dettagli & Tentativi</button>
        </td>
      </tr>
    `;
  }).join('');
}

async function inspectNotificationAttempts(notificationId) {
  try {
    const res = await apiCall(`/api/v1/admin/notifications/${notificationId}`);
    const n = res.data;
    const dialog = document.getElementById('notifDetailDialog');
    
    document.getElementById('notifDetailId').textContent = n.id;
    document.getElementById('notifDetailStatus').innerHTML = `<span class="badge badge-${n.status}">${n.status}</span>`;
    document.getElementById('notifDetailProvider').textContent = n.provider;
    document.getElementById('notifDetailSummary').textContent = n.recipient_summary || 'N/A';
    document.getElementById('notifDetailCreated').textContent = formatDate(n.created_at);
    document.getElementById('notifDetailSent').textContent = n.sent_at ? formatDate(n.sent_at) : 'Non ancora inviato';
    document.getElementById('notifDetailError').textContent = n.sanitized_error_message || 'Nessun errore';

    const attemptsTbody = document.getElementById('notifAttemptsTbody');
    if (n.attempts && n.attempts.length > 0) {
      attemptsTbody.innerHTML = n.attempts.map(a => `
        <tr>
          <td>#${a.attempt_number}</td>
          <td><span class="badge badge-${a.status}">${a.status}</span></td>
          <td>${a.response_code || '-'}</td>
          <td>${a.duration_ms ? `${a.duration_ms} ms` : '-'}</td>
          <td>${escapeHtml(a.error_message || 'OK')}</td>
          <td>${formatDate(a.attempted_at)}</td>
        </tr>
      `).join('');
    } else {
      attemptsTbody.innerHTML = `<tr><td colspan="6" class="text-muted" style="text-align: center;">Nessun tentativo registrato.</td></tr>`;
    }

    dialog.showModal();
  } catch (err) {
    // handled
  }
}

/* ==============================================================================
   AUDIT LOGS
   ============================================================================== */

async function loadAuditLogs() {
  try {
    const res = await apiCall('/api/v1/admin/audit-logs?limit=50');
    state.auditLogs = res.data || [];
    renderAuditTable();
  } catch (err) {
    console.error('Failed to load audit logs:', err);
  }
}

function renderAuditTable() {
  const tbody = document.getElementById('auditTbody');
  if (!tbody) return;

  if (state.auditLogs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Nessun evento registrato nell'audit log.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.auditLogs.map(a => {
    return `
      <tr>
        <td class="mono">${formatDate(a.created_at)}</td>
        <td style="font-weight: 600;">${escapeHtml(a.action)}</td>
        <td>${escapeHtml(a.actor)}</td>
        <td class="mono">${escapeHtml(a.resource_type || '-')} (${(a.resource_id || '').substring(0, 8)})</td>
        <td><span class="badge badge-${a.status === 'success' ? 'success' : 'danger'}">${a.status}</span></td>
        <td class="mono" style="font-size: 0.75rem;">${escapeHtml(JSON.stringify(a.details || {}))}</td>
      </tr>
    `;
  }).join('');
}

/* ==============================================================================
   FORM HANDLERS
   ============================================================================== */

function initFormHandlers() {
  // Create Application Form
  const appForm = document.getElementById('createAppForm');
  if (appForm) {
    appForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const permissions = [];
      if (document.getElementById('permTelegram').checked) permissions.push('telegram:send');
      if (document.getElementById('permGmail').checked) permissions.push('gmail:send');

      const payload = {
        name: document.getElementById('appName').value.trim(),
        description: document.getElementById('appDesc').value.trim(),
        rate_limit_per_minute: parseInt(document.getElementById('appRateLimit').value, 10) || 60,
        permissions: permissions
      };

      try {
        const res = await apiCall('/api/v1/admin/applications', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        document.getElementById('createAppDialog').close();
        appForm.reset();
        showToast('Applicazione creata con successo!', 'success');
        if (res?.data?.raw_api_key) {
          showApiKeyRevealModal(payload.name, res.data.raw_api_key);
        }
        loadApplications();
        loadStats();
      } catch (err) {
        // handled
      }
    });
  }

  // Create Telegram Config Form
  const tgForm = document.getElementById('createTgForm');
  if (tgForm) {
    tgForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        application_id: document.getElementById('tgAppId').value,
        name: document.getElementById('tgName').value.trim(),
        bot_token: document.getElementById('tgToken').value.trim(),
        chat_id: document.getElementById('tgChatId').value.trim() || null,
        is_active: document.getElementById('tgActive').checked
      };

      try {
        await apiCall('/api/v1/admin/telegram', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        document.getElementById('createTgDialog').close();
        tgForm.reset();
        showToast('Bot Telegram configurato con successo!', 'success');
        loadTelegramConfigs();
        loadStats();
      } catch (err) {
        // handled
      }
    });
  }

  // Create Gmail/SMTP Config Form
  const gmailForm = document.getElementById('createGmailForm');
  if (gmailForm) {
    gmailForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const authType = document.getElementById('gmailAuthType').value;
      const payload = {
        application_id: document.getElementById('gmailAppId').value,
        name: document.getElementById('gmailName').value.trim(),
        auth_type: authType,
        is_active: document.getElementById('gmailActive').checked,
        from_email: document.getElementById('gmailFromEmail').value.trim(),
        from_name: document.getElementById('gmailFromName').value.trim() || null
      };

      if (authType === 'app_password') {
        payload.smtp_host = document.getElementById('smtpHost').value.trim() || 'smtp.gmail.com';
        payload.smtp_port = parseInt(document.getElementById('smtpPort').value, 10) || 587;
        payload.use_tls = document.getElementById('smtpTls').checked;
        payload.username = document.getElementById('smtpUser').value.trim();
        payload.app_password = document.getElementById('smtpPass').value.trim();
      } else {
        payload.client_id = document.getElementById('oauthClientId').value.trim();
        payload.client_secret = document.getElementById('oauthClientSecret').value.trim();
      }

      try {
        await apiCall('/api/v1/admin/gmail', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        document.getElementById('createGmailDialog').close();
        gmailForm.reset();
        showToast('Integrazione Email/SMTP salvata con successo!', 'success');
        loadGmailConfigs();
        loadStats();
      } catch (err) {
        // handled
      }
    });
  }

  // Test Telegram Form Submit
  const testTgForm = document.getElementById('testTgForm');
  if (testTgForm) {
    testTgForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const configId = document.getElementById('testTgConfigId').value;
      const payload = {
        chat_id: document.getElementById('testTgChatId').value.trim(),
        message: document.getElementById('testTgMessage').value.trim(),
        parse_mode: 'HTML'
      };

      const btn = testTgForm.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Invio in corso...';
      const resultBox = document.getElementById('testTgResult');

      try {
        const res = await apiCall(`/api/v1/admin/telegram/${configId}/test`, {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        resultBox.style.display = 'block';
        resultBox.className = 'payload-preview';
        resultBox.textContent = `SUCCESS (HTTP 200):\n${JSON.stringify(res, null, 2)}`;
        showToast('Messaggio Telegram inviato con successo!', 'success');
      } catch (err) {
        resultBox.style.display = 'block';
        resultBox.className = 'payload-preview';
        resultBox.style.color = '#ef4444';
        resultBox.textContent = `FAILED:\n${err.message}`;
      } finally {
        btn.disabled = false;
        btn.textContent = 'Invia Messaggio Test';
      }
    });
  }

  // Test Gmail Form Submit
  const testGmailForm = document.getElementById('testGmailForm');
  if (testGmailForm) {
    testGmailForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const configId = document.getElementById('testGmailConfigId').value;
      const payload = {
        to: document.getElementById('testGmailRecipient').value.trim(),
        subject: document.getElementById('testGmailSubject').value.trim(),
        html: document.getElementById('testGmailBody').value.trim()
      };

      const btn = testGmailForm.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Invio email in corso...';
      const resultBox = document.getElementById('testGmailResult');

      try {
        const res = await apiCall(`/api/v1/admin/gmail/${configId}/test`, {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        resultBox.style.display = 'block';
        resultBox.className = 'payload-preview';
        resultBox.textContent = `SUCCESS (HTTP 200):\n${JSON.stringify(res, null, 2)}`;
        showToast('Email di test inviata con successo!', 'success');
      } catch (err) {
        resultBox.style.display = 'block';
        resultBox.className = 'payload-preview';
        resultBox.style.color = '#ef4444';
        resultBox.textContent = `FAILED:\n${err.message}`;
      } finally {
        btn.disabled = false;
        btn.textContent = 'Invia Email Test';
      }
    });
  }

  // Sandbox Live Dispatch Form
  const sandboxForm = document.getElementById('sandboxForm');
  if (sandboxForm) {
    sandboxForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const provider = document.getElementById('sandboxProvider').value;
      const configId = document.getElementById('sandboxConfig').value;
      if (!configId) {
        showToast('Seleziona una configurazione valida prima di inviare.', 'warning');
        return;
      }

      const btn = sandboxForm.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Esecuzione...';
      const resultBox = document.getElementById('sandboxResultBox');
      const startTime = performance.now();

      try {
        let endpoint = provider === 'telegram' 
          ? `/api/v1/admin/telegram/${configId}/test`
          : `/api/v1/admin/gmail/${configId}/test`;

        let payload = provider === 'telegram' ? {
          chat_id: document.getElementById('sbTgChatId').value.trim(),
          message: document.getElementById('sbTgMessage').value.trim(),
          parse_mode: 'HTML'
        } : {
          to: document.getElementById('sbEmailTo').value.trim(),
          subject: document.getElementById('sbEmailSubject').value.trim(),
          html: document.getElementById('sbEmailBody').value.trim()
        };

        const res = await apiCall(endpoint, {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        const duration = Math.round(performance.now() - startTime);
        resultBox.style.color = '#38bdf8';
        resultBox.textContent = `// HTTP 200 OK (${duration} ms)\n// Provider: ${provider.toUpperCase()}\n\n${JSON.stringify(res, null, 2)}`;
        showToast(`Notifica ${provider} recapitata in ${duration}ms!`, 'success');
      } catch (err) {
        resultBox.style.color = '#ef4444';
        resultBox.textContent = `// ERROR:\n${err.message}`;
      } finally {
        btn.disabled = false;
        btn.textContent = 'Esegui Notifica Live';
      }
    });
  }
}

function populateAppDropdowns() {
  const tgSelect = document.getElementById('tgAppId');
  const gmailSelect = document.getElementById('gmailAppId');
  const options = state.applications.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
  if (tgSelect) tgSelect.innerHTML = options || '<option value="">Crea prima un\'applicazione</option>';
  if (gmailSelect) gmailSelect.innerHTML = options || '<option value="">Crea prima un\'applicazione</option>';
}

/* ==============================================================================
   UTILITIES
   ============================================================================== */

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(100%)';
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copiato negli appunti!', 'success');
  }).catch(() => {
    showToast('Impossibile copiare il testo.', 'error');
  });
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatDate(isoString) {
  if (!isoString) return '-';
  try {
    const d = new Date(isoString);
    return d.toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch {
    return isoString;
  }
}

function formatSeconds(secs) {
  if (!secs) return '0s';
  const hours = Math.floor(secs / 3600);
  const minutes = Math.floor((secs % 3600) / 60);
  const seconds = Math.floor(secs % 60);
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}
