/**
 * Notification Gateway - Enterprise Admin Dashboard Client
 * AdminLTE 4.0 & Bootstrap 5.3 + Font Scaling & Light/Dark Theme Engine
 */

// Global State
const state = {
  adminKey: sessionStorage.getItem('ng_admin_key') || localStorage.getItem('ng_admin_key') || '',
  activeSection: 'overview',
  stats: null,
  health: null,
  applications: [],
  telegramConfigs: [],
  gmailConfigs: [],
  smtpConfigs: []
};

// DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initThemeAndFontControls();
  initKeyManagement();
  initSidebarNavigation();
  initDialogFallbacks();
  
  // Initial data load
  refreshAllData();

  // Periodic health check
  setInterval(() => {
    loadHealth();
    if (state.activeSection === 'overview') {
      loadStats();
    }
  }, 30000);
});

/* ==============================================================================
   THEME (Light / Dark / Auto) & FONT SIZE SCALING
   ============================================================================== */

function initThemeAndFontControls() {
  // 1. Theme Management (Default: light)
  const storedTheme = localStorage.getItem('ng_theme') || 'light';
  applyTheme(storedTheme);

  document.querySelectorAll('[data-bs-theme-value]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const theme = btn.getAttribute('data-bs-theme-value');
      applyTheme(theme);
    });
  });

  // Listen for system theme changes if set to auto
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const currentStored = localStorage.getItem('ng_theme');
    if (currentStored === 'auto') {
      applyTheme('auto');
    }
  });

  // 2. Font Size Scaling Management
  const storedFontSize = localStorage.getItem('ng_font_size') || 'font-size-md';
  applyFontSize(storedFontSize);

  document.querySelectorAll('[data-font-size]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const sizeClass = btn.getAttribute('data-font-size');
      applyFontSize(sizeClass);
    });
  });
}

function applyTheme(theme) {
  localStorage.setItem('ng_theme', theme);
  const htmlEl = document.documentElement;
  
  let effectiveTheme = theme;
  if (theme === 'auto') {
    effectiveTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  htmlEl.setAttribute('data-bs-theme', effectiveTheme);

  // Update theme dropdown UI
  const themeIcon = document.getElementById('theme-active-icon');
  const themeText = document.getElementById('theme-active-text');
  
  if (themeIcon) {
    themeIcon.className = theme === 'light' ? 'bi bi-sun-fill fs-5' :
                          theme === 'dark' ? 'bi bi-moon-stars-fill fs-5' :
                          'bi bi-circle-half fs-5';
  }
  if (themeText) {
    themeText.textContent = theme === 'light' ? 'Chiaro' :
                            theme === 'dark' ? 'Scuro' : 'Auto';
  }

  document.querySelectorAll('[data-bs-theme-value]').forEach(btn => {
    const val = btn.getAttribute('data-bs-theme-value');
    const check = btn.querySelector('.theme-check');
    if (val === theme) {
      btn.classList.add('active');
      if (check) check.classList.remove('d-none');
    } else {
      btn.classList.remove('active');
      if (check) check.classList.add('d-none');
    }
  });
}

function applyFontSize(sizeClass) {
  const allowedClasses = ['font-size-sm', 'font-size-md', 'font-size-lg', 'font-size-xl'];
  if (!allowedClasses.includes(sizeClass)) {
    sizeClass = 'font-size-md';
  }

  localStorage.setItem('ng_font_size', sizeClass);
  const body = document.body;

  allowedClasses.forEach(cls => body.classList.remove(cls));
  body.classList.add(sizeClass);

  const labels = {
    'font-size-sm': 'Compatto',
    'font-size-md': 'Normale',
    'font-size-lg': 'Grande',
    'font-size-xl': 'Molto Grande'
  };

  const labelEl = document.getElementById('current-font-size-label');
  if (labelEl) labelEl.textContent = labels[sizeClass] || 'Normale';

  document.querySelectorAll('[data-font-size]').forEach(btn => {
    const cls = btn.getAttribute('data-font-size');
    const check = btn.querySelector('.font-check');
    if (cls === sizeClass) {
      btn.classList.add('active');
      if (check) check.classList.remove('d-none');
    } else {
      btn.classList.remove('active');
      if (check) check.classList.add('d-none');
    }
  });
}

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
  const config = {
    ...options,
    headers: getHeaders(options.headers || {})
  };

  try {
    const res = await fetch(endpoint, config);
    if (res.status === 401) {
      showToast('Autenticazione richiesta. Inserisci la Admin API Key corretta.', 'danger');
      openDialog('dialog-admin-key');
      throw new Error('Unauthorized');
    }
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const errMsg = json?.error?.message || json?.detail || json?.message || `Errore HTTP ${res.status}`;
      showToast(errMsg, 'danger');
      throw new Error(errMsg);
    }
    return json;
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      console.error(`API Error on ${endpoint}:`, err);
    }
    throw err;
  }
}

function initKeyManagement() {
  const btnChangeKey = document.getElementById('btn-change-key');
  if (btnChangeKey) {
    btnChangeKey.addEventListener('click', () => {
      const input = document.getElementById('input-admin-key');
      if (input) input.value = state.adminKey;
      openDialog('dialog-admin-key');
    });
  }

  const btnRefresh = document.getElementById('btn-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      refreshAllData();
      showToast('Dati aggiornati!', 'info');
    });
  }

  // If no admin key, open dialog immediately
  if (!state.adminKey) {
    openDialog('dialog-admin-key');
  }
}

function handleSaveAdminKey(e) {
  e.preventDefault();
  const input = document.getElementById('input-admin-key');
  if (!input) return;
  state.adminKey = input.value.trim();
  sessionStorage.setItem('ng_admin_key', state.adminKey);
  localStorage.setItem('ng_admin_key', state.adminKey);
  closeDialog('dialog-admin-key');
  showToast('Admin API Key salvata!', 'success');
  refreshAllData();
}

/* ==============================================================================
   NAVIGATION & SECTIONS
   ============================================================================== */

function initSidebarNavigation() {
  document.querySelectorAll('[data-section]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const section = link.getAttribute('data-section');
      openSection(section);
    });
  });

  // Handle URL hash changes
  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.replace('#', '');
    if (hash && document.getElementById(`section-${hash}`)) {
      openSection(hash);
    }
  });

  if (window.location.hash) {
    const hash = window.location.hash.replace('#', '');
    if (hash && document.getElementById(`section-${hash}`)) {
      openSection(hash);
    }
  }
}

function openSection(sectionId) {
  state.activeSection = sectionId;

  // Update sidebar active link
  document.querySelectorAll('[data-section]').forEach(l => {
    if (l.getAttribute('data-section') === sectionId) {
      l.classList.add('active');
    } else {
      l.classList.remove('active');
    }
  });

  // Update visible section
  document.querySelectorAll('.dashboard-section').forEach(sec => {
    sec.classList.add('d-none');
    sec.classList.remove('active');
  });

  const targetSec = document.getElementById(`section-${sectionId}`);
  if (targetSec) {
    targetSec.classList.remove('d-none');
    targetSec.classList.add('active');
  }

  const titles = {
    overview: 'Panoramica del Sistema - VORTEX',
    apps: 'Applicazioni & API Keys',
    telegram: 'Configurazioni Bot Telegram',
    gmail: 'Account Email (Gmail & SMTP)',
    inbound: 'Messaggi Ricevuti (Inbound Receiver)',
    test: 'Invia Notifica di Prova Live'
  };

  const titleEl = document.getElementById('page-title');
  if (titleEl && titles[sectionId]) {
    titleEl.textContent = titles[sectionId];
  }

  // Load relevant data
  if (sectionId === 'overview') { loadStats(); loadHealth(); }
  else if (sectionId === 'apps') { loadApplications(); }
  else if (sectionId === 'telegram') { loadTelegramConfigs(); }
  else if (sectionId === 'gmail') { loadGmailConfigs(); }
  else if (sectionId === 'inbound') { loadInboundMessages(); }
  else if (sectionId === 'test') { populateTestAppDropdown(); }
}

function refreshAllData() {
  loadHealth();
  loadStats();
  loadApplications();
  loadTelegramConfigs();
  loadGmailConfigs();
  loadInboundMessages();
}

/* ==============================================================================
   OVERVIEW & HEALTH & STATS
   ============================================================================== */

async function loadHealth() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    state.health = data;

    const setSafe = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setSafe('health-db', data.components?.database || 'OK');
    setSafe('health-redis', data.components?.redis || 'OK');
    const ver = data.version ? `v${data.version}` : 'v0.6.6';
    setSafe('health-version', ver);
    const footerVer = document.getElementById('footer-version-tag');
    if (footerVer) footerVer.innerHTML = `<i class="bi bi-info-circle me-1"></i>Versione: <strong>${ver}</strong>`;
    setSafe('modal-system-version', ver);

    const badge = document.getElementById('system-status-badge');
    if (badge) {
      const isHealthy = data.status === 'healthy' || data.status === 'ok';
      badge.className = isHealthy 
        ? 'badge bg-success-subtle text-success border border-success-subtle px-3 py-2' 
        : 'badge bg-danger-subtle text-danger border border-danger-subtle px-3 py-2';
      badge.innerHTML = `<i class="bi bi-circle-fill me-1" style="font-size: 0.6rem;"></i> ${isHealthy ? 'Sistema Operativo' : 'Problemi Rilevati'}`;
    }
  } catch (err) {
    console.error('Failed to load health:', err);
  }
}

async function loadStats() {
  try {
    const res = await apiCall('/api/v1/admin/stats');
    if (res?.data) {
      state.stats = res.data;
      const setSafe = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setSafe('stat-apps', res.data.applications?.total || 0);
      setSafe('stat-telegram', res.data.telegram?.total_configs || 0);
      setSafe('stat-gmail', res.data.gmail?.total_configs || 0);

      // Storage sizing and archives
      if (res.data.storage) {
        const s = res.data.storage;
        setSafe('storage-db-total', s.database_size_pretty || 'N/A');

        const rec = s.records || {};
        const tbl = s.tables || {};

        setSafe('storage-notifs-records', `${rec.notifications || 0} notifiche (${rec.notification_attempts || 0} tentativi)`);
        setSafe('storage-notifs-size', tbl.notifications?.pretty || tbl.notification_attempts?.pretty ? 
          `${tbl.notifications?.pretty || '0 kB'} + ${tbl.notification_attempts?.pretty || '0 kB'}` : '--');

        setSafe('storage-audit-records', `${rec.audit_logs || 0} eventi registrati`);
        setSafe('storage-audit-size', tbl.audit_logs?.pretty || '--');

        setSafe('storage-apps-records', `${rec.applications || 0} app (${rec.api_keys || 0} chiavi api)`);
        setSafe('storage-apps-size', tbl.applications?.pretty || '--');
      }
    }
  } catch (err) {
    // handled
  }
}

/* ==============================================================================
   APPLICATIONS MANAGEMENT
   ============================================================================== */

async function loadApplications() {
  try {
    const res = await apiCall('/api/v1/admin/applications');
    state.applications = res.data || [];
    renderApplicationsTable();
    populateSelectAppLists();
    
    const countEl = document.getElementById('stat-apps');
    if (countEl) countEl.textContent = state.applications.length;
  } catch (err) {
    console.error('Failed to load applications:', err);
  }
}

function renderApplicationsTable() {
  const tbody = document.getElementById('tbody-apps');
  if (!tbody) return;

  if (state.applications.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">Nessuna applicazione registrata. Clicca su "+ Nuova Applicazione" per iniziare.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.applications.map(app => {
    const isActive = app.status === 'active';
    return `
      <tr>
        <td>
          <div class="fw-bold">${escapeHtml(app.name)}</div>
          <small class="text-muted font-monospace">${app.id}</small>
        </td>
        <td>${escapeHtml(app.description || '-')}</td>
        <td>
          <span class="badge ${isActive ? 'bg-success' : 'bg-secondary'}">${isActive ? 'Attiva' : 'Disabilitata'}</span>
        </td>
        <td>${formatDate(app.created_at)}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary" onclick="openEditAppDialog('${app.id}')" title="Modifica Applicazione">
              <i class="bi bi-pencil me-1"></i>Modifica
            </button>
            <button type="button" class="btn btn-outline-primary" onclick="promptRegenerateKey('${app.id}', '${escapeHtml(app.name)}')">
              <i class="bi bi-key me-1"></i>Rigenera Key
            </button>
            <button type="button" class="btn ${isActive ? 'btn-outline-warning' : 'btn-outline-success'}" onclick="toggleAppStatus('${app.id}', '${isActive ? 'disabled' : 'active'}')">
              ${isActive ? 'Disabilita' : 'Attiva'}
            </button>
            <button type="button" class="btn btn-outline-danger" onclick="promptDeleteApp('${app.id}', '${escapeHtml(app.name)}')">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function openNewAppDialog() {
  document.getElementById('form-new-app')?.reset();
  openDialog('dialog-new-app');
}

async function handleCreateApp(e) {
  e.preventDefault();
  const name = document.getElementById('app-name').value.trim();
  const description = document.getElementById('app-desc').value.trim();

  try {
    const res = await apiCall('/api/v1/admin/applications', {
      method: 'POST',
      body: JSON.stringify({ name, description, rate_limit_per_minute: 120, permissions: ['telegram:send', 'gmail:send', 'smtp:send'] })
    });

    closeDialog('dialog-new-app');
    showToast(`Applicazione "${name}" creata!`, 'success');

    if (res?.data?.raw_api_key) {
      document.getElementById('created-app-key').value = res.data.raw_api_key;
      openDialog('dialog-app-created');
    }

    loadApplications();
    loadStats();
  } catch (err) {
    // handled
  }
}

async function promptRegenerateKey(appId, appName) {
  if (!confirm(`Sei sicuro di voler rigenerare la API Key per "${appName}"? La chiave precedente smetterà immediatamente di funzionare.`)) {
    return;
  }
  try {
    const res = await apiCall(`/api/v1/admin/applications/${appId}/api-key/regenerate`, { method: 'POST' });
    if (res?.data?.raw_api_key) {
      document.getElementById('created-app-key').value = res.data.raw_api_key;
      openDialog('dialog-app-created');
      loadApplications();
    }
  } catch (err) {
    // handled
  }
}

async function toggleAppStatus(appId, newStatus) {
  try {
    await apiCall(`/api/v1/admin/applications/${appId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: newStatus })
    });
    showToast(`Stato applicazione aggiornato a '${newStatus}'.`, 'success');
    loadApplications();
  } catch (err) {
    // handled
  }
}

async function promptDeleteApp(appId, appName) {
  if (!confirm(`Sei sicuro di voler eliminare l'applicazione "${appName}"?\n\nTutte le configurazioni associate e i messaggi verranno eliminati in modo definitivo.`)) {
    return;
  }
  try {
    await apiCall(`/api/v1/admin/applications/${appId}`, { method: 'DELETE' });
    showToast(`Applicazione "${appName}" eliminata.`, 'success');
    loadApplications();
    loadTelegramConfigs();
    loadGmailConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

function openEditAppDialog(appId) {
  const app = state.applications.find(a => a.id === appId);
  if (!app) return;

  document.getElementById('edit-app-id').value = app.id;
  document.getElementById('edit-app-name').value = app.name || '';
  document.getElementById('edit-app-desc').value = app.description || '';
  document.getElementById('edit-app-rate-limit').value = app.rate_limit_per_minute || 120;

  openDialog('dialog-edit-app');
}

async function handleUpdateApp(e) {
  e.preventDefault();
  const appId = document.getElementById('edit-app-id').value;
  const name = document.getElementById('edit-app-name').value.trim();
  const description = document.getElementById('edit-app-desc').value.trim();
  const rateLimit = parseInt(document.getElementById('edit-app-rate-limit').value, 10) || 120;

  try {
    await apiCall(`/api/v1/admin/applications/${appId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name, description, rate_limit_per_minute: rateLimit })
    });

    closeDialog('dialog-edit-app');
    showToast(`Applicazione "${name}" aggiornata con successo!`, 'success');
    loadApplications();
    loadStats();
  } catch (err) {
    // handled
  }
}

function copyCreatedKey() {
  const input = document.getElementById('created-app-key');
  if (input) {
    navigator.clipboard.writeText(input.value).then(() => {
      showToast('API Key copiata negli appunti!', 'success');
    });
  }
}

/* ==============================================================================
   TELEGRAM MANAGEMENT
   ============================================================================== */

async function loadTelegramConfigs() {
  try {
    const res = await apiCall('/api/v1/admin/telegram');
    state.telegramConfigs = res.data || [];
    renderTelegramTable();
    
    const countEl = document.getElementById('stat-telegram');
    if (countEl) countEl.textContent = state.telegramConfigs.length;
  } catch (err) {
    console.error('Failed to load telegram configs:', err);
  }
}

function renderTelegramTable() {
  const tbody = document.getElementById('tbody-telegram');
  if (!tbody) return;

  if (state.telegramConfigs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">Nessun bot Telegram configurato. Clicca su "Aggiungi Bot Telegram".</td></tr>`;
    return;
  }

  tbody.innerHTML = state.telegramConfigs.map(c => {
    const app = state.applications.find(a => a.id === c.application_id);
    const appName = app ? app.name : (c.application_id ? c.application_id.substring(0, 8) : 'Globale');
    const isActive = c.is_active;

    return `
      <tr>
        <td><strong>${escapeHtml(appName)}</strong></td>
        <td class="font-monospace">${escapeHtml(c.chat_id || 'N/A')}</td>
        <td class="font-monospace">••••••••••••${c.id.substring(0, 4)}</td>
        <td><span class="badge ${isActive ? 'bg-success' : 'bg-secondary'}">${isActive ? 'Attivo' : 'Disattivato'}</span></td>
        <td>${formatDate(c.created_at)}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary" onclick="openEditTelegramDialog('${c.id}')" title="Modifica Configurazione">
              <i class="bi bi-pencil me-1"></i>Modifica
            </button>
            <button type="button" class="btn btn-outline-info" onclick="quickTestTelegram('${c.id}')">
              <i class="bi bi-send me-1"></i>Test
            </button>
            <button type="button" class="btn btn-outline-danger" onclick="promptDeleteTelegram('${c.id}')">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function openNewTelegramDialog() {
  document.getElementById('form-new-telegram')?.reset();
  openDialog('dialog-new-telegram');
}

async function handleCreateTelegram(e) {
  e.preventDefault();
  const payload = {
    application_id: document.getElementById('telegram-app-id').value,
    name: 'Telegram Bot',
    bot_token: document.getElementById('telegram-bot-token').value.trim(),
    chat_id: document.getElementById('telegram-chat-id').value.trim() || null
  };

  try {
    await apiCall('/api/v1/admin/telegram', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    closeDialog('dialog-new-telegram');
    showToast('Bot Telegram salvato con successo!', 'success');
    loadTelegramConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

function openEditTelegramDialog(configId) {
  const cfg = state.telegramConfigs.find(c => c.id === configId);
  if (!cfg) return;

  document.getElementById('edit-telegram-id').value = cfg.id;
  document.getElementById('edit-telegram-name').value = cfg.name || '';
  document.getElementById('edit-telegram-chat-id').value = cfg.default_chat_id || cfg.chat_id || '';
  document.getElementById('edit-telegram-bot-token').value = '';

  openDialog('dialog-edit-telegram');
}

async function handleUpdateTelegram(e) {
  e.preventDefault();
  const configId = document.getElementById('edit-telegram-id').value;
  const name = document.getElementById('edit-telegram-name').value.trim();
  const chatId = document.getElementById('edit-telegram-chat-id').value.trim() || null;
  const botToken = document.getElementById('edit-telegram-bot-token').value.trim();

  const payload = {
    name: name,
    default_chat_id: chatId
  };
  if (botToken) {
    payload.bot_token = botToken;
  }

  try {
    await apiCall(`/api/v1/admin/telegram/${configId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });

    closeDialog('dialog-edit-telegram');
    showToast(`Configurazione Telegram "${name}" aggiornata!`, 'success');
    loadTelegramConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

async function promptDeleteTelegram(configId) {
  if (!confirm('Sei sicuro di voler eliminare questa configurazione Telegram?')) return;
  try {
    await apiCall(`/api/v1/admin/telegram/${configId}`, { method: 'DELETE' });
    showToast('Configurazione Telegram eliminata.', 'success');
    loadTelegramConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

async function quickTestTelegram(configId) {
  const chatId = prompt('Inserisci il Chat ID di test (lascia vuoto per usare quello default):');
  if (chatId === null) return;

  try {
    const res = await apiCall(`/api/v1/admin/telegram/${configId}/test`, {
      method: 'POST',
      body: JSON.stringify({
        chat_id: chatId.trim() || undefined,
        message: '🔔 Test Notifica Gateway AdminLTE 4.0 - Eseguito con Successo!'
      })
    });
    showToast('Notifica Telegram inviata con successo!', 'success');
  } catch (err) {
    // handled
  }
}

/* ==============================================================================
   GMAIL MANAGEMENT
   ============================================================================== */

async function loadGmailConfigs() {
  try {
    const res = await apiCall('/api/v1/admin/gmail');
    state.gmailConfigs = res.data || [];
    renderGmailTable();
    
    const countEl = document.getElementById('stat-gmail');
    if (countEl) countEl.textContent = state.gmailConfigs.length;
  } catch (err) {
    console.error('Failed to load gmail configs:', err);
  }
}

function renderGmailTable() {
  const tbody = document.getElementById('tbody-gmail');
  if (!tbody) return;

  if (state.gmailConfigs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">Nessun account Email/SMTP configurato. Clicca su "Aggiungi Account Email".</td></tr>`;
    return;
  }

  tbody.innerHTML = state.gmailConfigs.map(c => {
    const app = state.applications.find(a => a.id === c.application_id);
    const appName = app ? app.name : (c.application_id ? c.application_id.substring(0, 8) : 'Globale');
    const isActive = c.is_active;

    return `
      <tr>
        <td>
          <strong>${escapeHtml(c.name || 'Account Email')}</strong>
          <div class="small text-muted">${c.auth_type === 'app_password' ? 'App Password / SMTP' : 'OAuth2'}</div>
        </td>
        <td><strong>${escapeHtml(appName)}</strong></td>
        <td>${escapeHtml(c.email_address || c.username || c.from_email || 'N/A')}</td>
        <td class="font-monospace">${escapeHtml(c.smtp_host || 'smtp.gmail.com')}:${c.smtp_port || 587}</td>
        <td><span class="badge ${isActive ? 'bg-success' : 'bg-secondary'}">${isActive ? 'Attivo' : 'Disattivato'}</span></td>
        <td>${formatDate(c.created_at)}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary" onclick="openEditGmailDialog('${c.id}')" title="Modifica Configurazione">
              <i class="bi bi-pencil me-1"></i>Modifica
            </button>
            <button type="button" class="btn btn-outline-danger" onclick="quickTestGmail('${c.id}')">
              <i class="bi bi-send me-1"></i>Test
            </button>
            <button type="button" class="btn btn-outline-danger" onclick="promptDeleteGmail('${c.id}')">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function openNewGmailDialog() {
  document.getElementById('form-new-gmail')?.reset();
  const hostInput = document.getElementById('gmail-smtp-host');
  const portInput = document.getElementById('gmail-smtp-port');
  if (hostInput) hostInput.value = 'smtp.gmail.com';
  if (portInput) portInput.value = 587;
  openDialog('dialog-new-gmail');
}

async function handleCreateGmail(e) {
  e.preventDefault();
  const emailVal = document.getElementById('gmail-email').value.trim();
  const nameVal = document.getElementById('gmail-config-name')?.value.trim() || 'Account Email';
  const hostVal = document.getElementById('gmail-smtp-host')?.value.trim() || 'smtp.gmail.com';
  const portVal = parseInt(document.getElementById('gmail-smtp-port')?.value, 10) || 587;
  const passwordVal = document.getElementById('gmail-app-password').value.trim();

  const payload = {
    application_id: document.getElementById('gmail-app-id').value,
    name: nameVal,
    email_address: emailVal,
    auth_type: 'app_password',
    smtp_host: hostVal,
    smtp_port: portVal,
    app_password: passwordVal,
    is_active: true
  };

  try {
    await apiCall('/api/v1/admin/gmail', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    closeDialog('dialog-new-gmail');
    showToast('Configurazione Email salvata con successo!', 'success');
    loadGmailConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

function openEditGmailDialog(configId) {
  const cfg = state.gmailConfigs.find(c => c.id === configId);
  if (!cfg) return;

  document.getElementById('edit-gmail-id').value = cfg.id;
  document.getElementById('edit-gmail-name').value = cfg.name || '';
  document.getElementById('edit-gmail-smtp-host').value = cfg.smtp_host || 'smtp.gmail.com';
  document.getElementById('edit-gmail-smtp-port').value = cfg.smtp_port || 587;
  document.getElementById('edit-gmail-email').value = cfg.email_address || cfg.username || cfg.from_email || '';
  document.getElementById('edit-gmail-password').value = '';

  openDialog('dialog-edit-gmail');
}

async function handleUpdateGmail(e) {
  e.preventDefault();
  const configId = document.getElementById('edit-gmail-id').value;
  const name = document.getElementById('edit-gmail-name').value.trim();
  const host = document.getElementById('edit-gmail-smtp-host').value.trim();
  const port = parseInt(document.getElementById('edit-gmail-smtp-port').value, 10) || 587;
  const email = document.getElementById('edit-gmail-email').value.trim();
  const password = document.getElementById('edit-gmail-password').value.trim();

  const payload = {
    name: name,
    email_address: email,
    smtp_host: host,
    smtp_port: port
  };
  if (password) {
    payload.app_password = password;
  }

  try {
    await apiCall(`/api/v1/admin/gmail/${configId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });

    closeDialog('dialog-edit-gmail');
    showToast(`Configurazione Email "${name}" aggiornata!`, 'success');
    loadGmailConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

async function promptDeleteGmail(configId) {
  if (!confirm('Sei sicuro di voler eliminare questa configurazione Email?')) return;
  try {
    await apiCall(`/api/v1/admin/gmail/${configId}`, { method: 'DELETE' });
    showToast('Configurazione Email eliminata.', 'success');
    loadGmailConfigs();
    loadStats();
  } catch (err) {
    // handled
  }
}

async function quickTestGmail(configId) {
  const recipient = prompt('Inserisci indirizzo email di destinazione del test:');
  if (!recipient) return;

  try {
    await apiCall(`/api/v1/admin/gmail/${configId}/test?recipient=${encodeURIComponent(recipient.trim())}`, {
      method: 'POST'
    });
    showToast('Email di prova inviata con successo!', 'success');
  } catch (err) {
    // handled
  }
}

/* ==============================================================================
   INBOUND MESSAGES (RECEIVING)
   ============================================================================== */

async function loadInboundMessages() {
  try {
    const res = await apiCall('/api/v1/inbound/messages?limit=50');
    const tbody = document.getElementById('tbody-inbound');
    if (!tbody) return;

    const msgs = res.data || [];
    if (msgs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">Nessun messaggio in arrivo ricevuto. Gli aggiornamenti Telegram o Email compariranno qui.</td></tr>`;
      return;
    }

    tbody.innerHTML = msgs.map(m => {
      const isTg = m.provider === 'telegram';
      const badgeProvider = isTg ? '<span class="badge bg-info text-white"><i class="bi bi-telegram me-1"></i>Telegram</span>'
                                 : '<span class="badge bg-danger text-white"><i class="bi bi-envelope-at me-1"></i>Email</span>';

      return `
        <tr>
          <td>${badgeProvider}</td>
          <td>
            <strong>${escapeHtml(m.sender_name || m.sender_identifier)}</strong>
            <div class="small text-muted font-monospace">${escapeHtml(m.sender_identifier)}</div>
          </td>
          <td>${escapeHtml(m.subject || (isTg ? 'Chat Diretta' : '-'))}</td>
          <td><div style="max-width: 380px; white-space: pre-wrap; word-break: break-word;">${escapeHtml(m.message_text || '-')}</div></td>
          <td><span class="badge bg-success-subtle text-success border border-success-subtle">${m.status}</span></td>
          <td>${formatDate(m.created_at)}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to load inbound messages:', err);
  }
}

function openSystemInfoDialog(e) {
  if (e) e.preventDefault();
  openDialog('dialog-system-info');
}

function openTelegramGuideModal(e) {
  if (e) e.preventDefault();
  openDialog('dialog-telegram-guide');
}

/* ==============================================================================
   LIVE NOTIFICATION TESTER
   ============================================================================== */

function handleTestChannelChange() {
  const channel = document.getElementById('test-channel').value;
  const subjGroup = document.getElementById('group-test-subject');
  const recipientInput = document.getElementById('test-recipient');

  if (channel === 'telegram') {
    if (subjGroup) subjGroup.classList.add('d-none');
    if (recipientInput) recipientInput.placeholder = 'Chat ID Telegram (es. 12345678)';
  } else {
    if (subjGroup) subjGroup.classList.remove('d-none');
    if (recipientInput) recipientInput.placeholder = 'Indirizzo Email (es. utente@dominio.it)';
  }
}

function populateTestAppDropdown() {
  // If apps exist, prefill apiKey from clipboard or memory if available
  handleTestChannelChange();
}

async function handleSendTestNotification(e) {
  e.preventDefault();
  const channel = document.getElementById('test-channel').value;
  const apiKey = document.getElementById('test-api-key').value.trim();
  const recipient = document.getElementById('test-recipient').value.trim();
  const subject = document.getElementById('test-subject').value.trim();
  const message = document.getElementById('test-message').value.trim();

  const btnSubmit = document.getElementById('btn-submit-test');
  const resultBox = document.getElementById('test-result-box');
  const resultJson = document.getElementById('test-result-json');

  btnSubmit.disabled = true;
  btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Invio in corso...';
  resultBox.classList.add('d-none');

  try {
    let endpoint = channel === 'telegram' ? '/api/v1/notifications/telegram' : '/api/v1/notifications/email';
    let payload = channel === 'telegram' ? {
      chat_id: recipient,
      message: message
    } : {
      to: recipient,
      subject: subject || 'Test Notification Gateway',
      html: `<p>${escapeHtml(message)}</p>`
    };

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));

    resultBox.classList.remove('d-none');
    resultJson.textContent = JSON.stringify(data, null, 2);

    if (res.ok) {
      showToast('Notifica recapitata con successo!', 'success');
    } else {
      showToast(data.detail || data.error?.message || `Errore HTTP ${res.status}`, 'danger');
    }
  } catch (err) {
    resultBox.classList.remove('d-none');
    resultJson.textContent = `Errore di rete / eccezione: ${err.message}`;
    showToast('Errore durante l\'invio della notifica.', 'danger');
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.innerHTML = '<i class="bi bi-send me-1"></i> Invia Subito';
  }
}

/* ==============================================================================
   HELPERS & MODAL DIALOG UTILS
   ============================================================================== */

function populateSelectAppLists() {
  document.querySelectorAll('.select-app-list').forEach(sel => {
    const currentVal = sel.value;
    if (state.applications.length === 0) {
      sel.innerHTML = '<option value="">Nessuna applicazione disponibile</option>';
    } else {
      sel.innerHTML = state.applications.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
      if (currentVal) sel.value = currentVal;
    }
  });
}

function openDialog(dialogId) {
  const dialog = document.getElementById(dialogId);
  if (dialog && typeof dialog.showModal === 'function') {
    dialog.showModal();
  }
}

function closeDialog(dialogId) {
  const dialog = document.getElementById(dialogId);
  if (dialog && typeof dialog.close === 'function') {
    dialog.close();
  }
}

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
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toastId = 'toast-' + Math.random().toString(36).substring(2, 9);
  const bgClass = type === 'success' ? 'bg-success text-white' :
                  type === 'danger' ? 'bg-danger text-white' :
                  type === 'warning' ? 'bg-warning text-dark' :
                  'bg-primary text-white';

  const toastEl = document.createElement('div');
  toastEl.className = `toast align-items-center ${bgClass} border-0 shadow`;
  toastEl.id = toastId;
  toastEl.setAttribute('role', 'alert');
  toastEl.setAttribute('aria-live', 'assertive');
  toastEl.setAttribute('aria-atomic', 'true');

  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        ${escapeHtml(message)}
      </div>
      <button type="button" class="btn-close ${type !== 'warning' ? 'btn-close-white' : ''} me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
  `;

  container.appendChild(toastEl);
  if (window.bootstrap && window.bootstrap.Toast) {
    const bsToast = new window.bootstrap.Toast(toastEl, { delay: 4000 });
    bsToast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
  } else {
    setTimeout(() => toastEl.remove(), 4000);
  }
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
      minute: '2-digit'
    });
  } catch {
    return isoString;
  }
}
