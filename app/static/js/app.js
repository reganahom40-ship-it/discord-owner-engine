// Private Owner Control Panel — High-Density Client Engine v3
let cachedAuditLogs = [];
let cachedKeys = [];
let cachedClientId = '';
let pollTimer = null;

const API = {
  async get(url) {
    const res = await fetch(url);
    if (res.status === 401) {
      window.location.href = '/login';
      throw new Error('Owner session expired');
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  },
  async post(url, body = {}) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (res.status === 401) {
      window.location.href = '/login';
      throw new Error('Owner session expired');
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  },
  async delete(url) {
    const res = await fetch(url, { method: 'DELETE' });
    if (res.status === 401) {
      window.location.href = '/login';
      throw new Error('Owner session expired');
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  }
};

function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container') || createToastContainer();
  const toast = document.createElement('div');
  toast.className = `alert alert-${type}`;
  toast.style.boxShadow = 'var(--shadow-md)';
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

function createToastContainer() {
  const el = document.createElement('div');
  el.id = 'toast-container';
  el.style.position = 'fixed';
  el.style.bottom = '16px';
  el.style.right = '16px';
  el.style.zIndex = '9999';
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.gap = '6px';
  el.style.maxWidth = '360px';
  document.body.appendChild(el);
  return el;
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('active');
}

function copyRawText(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard!', 'info');
  });
}

function copyTextValue(inputId) {
  const el = document.getElementById(inputId);
  if (el && el.value) {
    copyRawText(el.value);
  }
}

async function handleOwnerLogout() {
  try {
    await API.post('/api/auth/logout');
    window.location.href = '/login';
  } catch (e) {
    window.location.href = '/login';
  }
}

// Navigation Tab Router
function switchTab(tabId) {
  document.querySelectorAll('.tab-view').forEach(v => v.style.display = 'none');
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));

  const targetView = document.getElementById(`view-${tabId}`);
  const targetBtn = document.getElementById(`btn-nav-${tabId}`);
  if (targetView) targetView.style.display = 'block';
  if (targetBtn) targetBtn.classList.add('active');

  if (tabId === 'overview') loadOverview();
  if (tabId === 'advertising') loadAdvertising();
  if (tabId === 'tasks') loadTasks();
  if (tabId === 'members') loadMemberOperations();
  if (tabId === 'boost') loadBoostOperations();
  if (tabId === 'keys') loadInternalKeys();
  if (tabId === 'settings') loadSettings();
}

// TAB 1: OVERVIEW & LIVE CONSOLE
async function loadOverview() {
  try {
    const data = await API.get('/api/owner/overview');
    const t = data.telemetry;

    // Top status pills
    const botPill = document.getElementById('top-bot-status');
    if (botPill) {
      if (t.bot_status === 'connected') {
        const lat = t.bot_latency_ms ? ` (${t.bot_latency_ms}ms)` : '';
        botPill.innerHTML = `<span class="status-dot online"></span> Bot: ${t.bot_name || 'Online'}${lat}`;
      } else if (t.bot_status === 'unconfigured') {
        botPill.innerHTML = `<span class="status-dot warning"></span> Bot: Unconfigured`;
      } else {
        botPill.innerHTML = `<span class="status-dot offline"></span> Bot: Auth Error`;
      }
    }

    const workerPill = document.getElementById('top-worker-status');
    if (workerPill) {
      workerPill.innerHTML = `<span class="status-dot ${t.worker_running ? 'online' : 'offline'}"></span> Daemon: ${t.worker_running ? 'Active' : 'Halted'}`;
    }

    // Sidebar Counters
    const navCamp = document.getElementById('nav-count-campaigns');
    if (navCamp) navCamp.innerText = t.active_campaigns;
    const navTasks = document.getElementById('nav-count-tasks');
    if (navTasks) navTasks.innerText = t.running_tasks + t.pending_tasks;
    const navKeys = document.getElementById('nav-count-keys');
    if (navKeys) navKeys.innerText = t.active_keys || 0;

    // KPI Cards
    document.getElementById('stat-running-tasks').innerText = t.running_tasks;
    document.getElementById('stat-completed-sub').innerText = `${t.completed_tasks} completed total`;
    document.getElementById('stat-pending-tasks').innerText = t.pending_tasks;
    document.getElementById('stat-failed-sub').innerText = `${t.failed_tasks} failed jobs`;
    document.getElementById('stat-active-campaigns').innerText = t.active_campaigns;
    document.getElementById('stat-processed-sub').innerText = `${t.jobs_processed} cycles executed`;
    document.getElementById('stat-webhooks').innerText = t.total_webhooks;
    document.getElementById('stat-keys-sub').innerText = `${t.active_keys || 0} active node keys`;

    // Live Daemon Console
    renderConsoleLogs(data.console_logs || []);
    if (t.worker_last_run) {
      const lbl = document.getElementById('worker-last-cycle-label');
      if (lbl) lbl.innerText = `Last cycle: ${new Date(t.worker_last_run).toLocaleTimeString()}`;
    }

    // Audit Logs
    cachedAuditLogs = data.recent_logs || [];
    renderAuditTable(cachedAuditLogs);
  } catch (err) {
    console.error('Overview error:', err);
  }
}

function renderConsoleLogs(logs) {
  const box = document.getElementById('daemon-console-box');
  if (!box) return;
  if (!logs.length) {
    box.innerHTML = '<div class="terminal-line"><span class="terminal-ts">--:--:--</span><span class="terminal-lvl INFO">INFO</span><span class="terminal-msg">No console events logged yet.</span></div>';
    return;
  }
  box.innerHTML = logs.map(l => `
    <div class="terminal-line">
      <span class="terminal-ts">[${l.timestamp}]</span>
      <span class="terminal-lvl ${l.level}">${l.level}</span>
      <span class="terminal-msg">${l.message}</span>
    </div>
  `).join('');
  box.scrollTop = box.scrollHeight;
}

function renderAuditTable(logs) {
  const tbody = document.getElementById('overview-logs-table');
  if (!tbody) return;
  if (logs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-dim); padding:1.5rem;">No matching system audit entries</td></tr>';
    return;
  }
  tbody.innerHTML = logs.map(l => `
    <tr>
      <td><span class="badge badge-info">${l.event_type}</span></td>
      <td>${l.details}</td>
      <td><code>${l.ip_address || '127.0.0.1'}</code></td>
      <td>${new Date(l.created_at).toLocaleTimeString()}</td>
    </tr>
  `).join('');
}

function filterAuditTable() {
  const q = (document.getElementById('audit-search-input')?.value || '').toLowerCase();
  if (!q) {
    renderAuditTable(cachedAuditLogs);
    return;
  }
  const filtered = cachedAuditLogs.filter(l =>
    l.event_type.toLowerCase().includes(q) ||
    l.details.toLowerCase().includes(q) ||
    (l.ip_address || '').toLowerCase().includes(q)
  );
  renderAuditTable(filtered);
}

// TAB 2: ADVERTISING & EMBED STUDIO
async function openBroadcastStudio() {
  try {
    const whData = await API.get('/api/owner/webhooks');
    const sel = document.getElementById('camp-saved-webhook-select');
    if (sel) {
      sel.innerHTML = '<option value="">-- Choose from saved webhooks --</option>' +
        whData.webhooks.map(w => `<option value="${w.url}">${w.name} (${w.status})</option>`).join('');
    }
  } catch (e) {}
  updateLiveEmbedPreview();
  openModal('modal-create-campaign');
}

function selectSavedWebhookForCamp(url) {
  if (url) {
    document.getElementById('camp-webhook').value = url;
  }
}

function updateLiveEmbedPreview() {
  const author = document.getElementById('camp-embed-author')?.value.trim() || 'Server Operations';
  const title = document.getElementById('camp-embed-title')?.value.trim() || '📢 Official Server Notice';
  const desc = document.getElementById('camp-content')?.value.trim() || 'Your broadcast content will appear here in real time...';
  const footer = document.getElementById('camp-embed-footer')?.value.trim() || 'Private Owner Control Panel • Verified Transmission';
  const color = document.getElementById('camp-embed-color')?.value || '#4f46e5';

  const borderEl = document.getElementById('preview-embed-border');
  if (borderEl) borderEl.style.borderLeftColor = color;
  const authEl = document.getElementById('preview-embed-author');
  if (authEl) authEl.innerText = author;
  const titleEl = document.getElementById('preview-embed-title');
  if (titleEl) titleEl.innerText = title;
  const descEl = document.getElementById('preview-embed-desc');
  if (descEl) descEl.innerText = desc;
  const footEl = document.getElementById('preview-embed-footer');
  if (footEl) footEl.innerText = footer;
}

async function loadAdvertising() {
  try {
    const data = await API.get('/api/owner/campaigns');
    const tbody = document.getElementById('campaigns-table-body');
    if (!tbody) return;

    if (data.campaigns.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-dim); padding:1.5rem;">No scheduled announcement broadcasts configured. Click "+ Launch Embed Studio" to create one.</td></tr>';
      return;
    }

    tbody.innerHTML = data.campaigns.map(c => `
      <tr>
        <td><strong>${c.title}</strong></td>
        <td>${c.embed_title || 'Plain Message'}</td>
        <td><code>${c.run_count} / ${c.max_runs}</code></td>
        <td>Every ${c.interval_minutes}m</td>
        <td>${c.last_latency_ms ? `<span class="badge badge-success">${c.last_latency_ms}ms</span>` : '<span style="color:var(--text-dim);">-</span>'}</td>
        <td><span class="badge ${c.status === 'scheduled' ? 'badge-info' : (c.status === 'completed' ? 'badge-success' : 'badge-warning')}">${c.status}</span></td>
        <td>${c.next_run_at ? new Date(c.next_run_at).toLocaleTimeString() : 'Completed'}</td>
        <td>
          <div style="display:flex; gap:0.35rem;">
            <button onclick="campaignAction(${c.id}, 'run_now')" class="btn btn-primary btn-sm" title="Fire broadcast right now">⚡ Run Now</button>
            ${c.status === 'scheduled' ? `<button onclick="campaignAction(${c.id}, 'pause')" class="btn btn-secondary btn-sm">Pause</button>` : ''}
            ${c.status === 'paused' ? `<button onclick="campaignAction(${c.id}, 'resume')" class="btn btn-secondary btn-sm">Resume</button>` : ''}
            <button onclick="campaignAction(${c.id}, 'delete')" class="btn btn-danger btn-sm">Delete</button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function createCampaignAction() {
  const title = document.getElementById('camp-title').value.trim();
  const webhook = document.getElementById('camp-webhook').value.trim();
  const content = document.getElementById('camp-content').value.trim();
  const embedTitle = document.getElementById('camp-embed-title').value.trim();
  const embedAuthor = document.getElementById('camp-embed-author').value.trim();
  const embedFooter = document.getElementById('camp-embed-footer').value.trim();
  const embedColor = document.getElementById('camp-embed-color').value;
  const interval = parseInt(document.getElementById('camp-interval').value) || 60;
  const maxRuns = parseInt(document.getElementById('camp-runs').value) || 5;

  try {
    const res = await API.post('/api/owner/campaigns', {
      title,
      target_webhook: webhook,
      content,
      embed_title: embedTitle,
      embed_author: embedAuthor,
      embed_footer: embedFooter,
      embed_color: embedColor,
      interval_minutes: interval,
      max_runs: maxRuns
    });
    showToast(res.message, 'success');
    closeModal('modal-create-campaign');
    loadAdvertising();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function testDispatchAction() {
  const webhook = document.getElementById('camp-webhook').value.trim();
  const content = document.getElementById('camp-content').value.trim();
  const embedTitle = document.getElementById('camp-embed-title').value.trim();
  const embedAuthor = document.getElementById('camp-embed-author').value.trim();
  const embedFooter = document.getElementById('camp-embed-footer').value.trim();
  const embedColor = document.getElementById('camp-embed-color').value;

  if (!webhook) {
    showToast('Select or paste a target webhook URL first', 'warning');
    return;
  }

  try {
    showToast('Dispatching live test transmission...', 'info');
    const res = await API.post('/api/owner/campaigns/test-dispatch', {
      target_webhook: webhook,
      content: content || 'Test broadcast transmission from Embed Studio',
      embed_title: embedTitle,
      embed_author: embedAuthor,
      embed_footer: embedFooter,
      embed_color: embedColor
    });
    showToast(`Test delivered! (${res.latency_ms || 0}ms)`, 'success');
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function campaignAction(id, action) {
  try {
    const res = await API.post(`/api/owner/campaigns/${id}/action`, { action });
    if (action === 'run_now') {
      showToast(`Broadcast fired! (${res.latency_ms || 0}ms)`, 'success');
    } else {
      showToast(`Campaign ${action}d`, 'success');
    }
    loadAdvertising();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// TAB 3: QUEST & TASK QUEUE
async function loadTasks() {
  try {
    const data = await API.get('/api/owner/tasks');
    const tbody = document.getElementById('tasks-table-body');
    if (!tbody) return;

    if (data.tasks.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-dim); padding:1.5rem;">No background operations in queue. Use the buttons above to dispatch a task.</td></tr>';
      return;
    }

    tbody.innerHTML = data.tasks.map(t => `
      <tr>
        <td><code>#${t.id}</code></td>
        <td><strong>${t.name}</strong><br><small style="color:var(--text-dim); font-family:var(--font-mono);">${t.task_type}</small></td>
        <td>
          <div style="width:110px;">
            <div style="font-size:0.7rem; margin-bottom:2px;">${t.progress_percent}%</div>
            <div class="progress-track"><div class="progress-fill" style="width:${t.progress_percent}%;"></div></div>
          </div>
        </td>
        <td><span class="badge ${t.status === 'completed' ? 'badge-success' : (t.status === 'running' ? 'badge-info' : (t.status === 'failed' ? 'badge-danger' : 'badge-warning'))}">${t.status}</span></td>
        <td style="max-width:260px;">
          ${t.error_message ? `<span style="color:var(--danger); font-size:0.75rem;">${t.error_message}</span>` : (t.result_json ? `<code style="font-size:0.72rem; color:var(--success);">${t.result_json.substring(0, 65)}...</code>` : '<span style="color:var(--text-dim);">Queued</span>')}
        </td>
        <td>
          <div style="display:flex; gap:0.35rem;">
            <button onclick="inspectTaskModal(${t.id})" class="btn btn-secondary btn-sm">Inspect</button>
            ${t.status === 'failed' || t.status === 'cancelled' ? `<button onclick="taskAction(${t.id}, 'run_now')" class="btn btn-primary btn-sm">Retry</button>` : ''}
            ${t.status === 'running' || t.status === 'pending' ? `<button onclick="taskAction(${t.id}, 'cancel')" class="btn btn-danger btn-sm">Cancel</button>` : ''}
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function dispatchTaskType(taskType, taskName, runImmediately = true) {
  try {
    const res = await API.post('/api/owner/tasks', {
      task_type: taskType,
      name: taskName,
      payload: { dispatched_by: 'owner', timestamp: new Date().toISOString() },
      run_immediately: runImmediately
    });
    showToast(`Executed: ${taskName}`, 'success');
    loadTasks();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function inspectTaskModal(taskId) {
  try {
    const res = await API.get(`/api/owner/tasks/${taskId}`);
    const t = res.task;
    document.getElementById('inspect-task-title').innerText = `Task #${t.id} — ${t.name}`;

    let prettyPayload = t.payload_json || '{}';
    let prettyResult = t.result_json || 'null';
    try { prettyPayload = JSON.stringify(JSON.parse(prettyPayload), null, 2); } catch (e) {}
    try { prettyResult = JSON.stringify(JSON.parse(prettyResult), null, 2); } catch (e) {}

    document.getElementById('inspect-task-body').innerHTML = `
      <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:0.5rem; margin-bottom:0.85rem;">
        <div class="card stat-box"><div class="stat-box-label">Type</div><div><code>${t.task_type}</code></div></div>
        <div class="card stat-box"><div class="stat-box-label">Status</div><div><span class="badge badge-info">${t.status}</span></div></div>
        <div class="card stat-box"><div class="stat-box-label">Retries</div><div>${t.retries} / ${t.max_retries}</div></div>
      </div>
      ${t.error_message ? `<div class="alert alert-danger">${t.error_message}</div>` : ''}
      <div class="form-group">
        <label class="form-label">Input Payload JSON</label>
        <pre class="terminal-box" style="height:auto; max-height:130px;">${prettyPayload}</pre>
      </div>
      <div class="form-group">
        <label class="form-label">Execution Output JSON</label>
        <pre class="terminal-box" style="height:auto; max-height:180px; color:var(--success);">${prettyResult}</pre>
      </div>
    `;
    openModal('modal-task-inspector');
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function clearCompletedTasksAction() {
  try {
    const res = await API.post('/api/owner/tasks/clear-completed');
    showToast(res.message, 'info');
    loadTasks();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function taskAction(id, action) {
  try {
    await API.post(`/api/owner/tasks/${id}/action`, { action });
    showToast(`Task ${action}d`, 'success');
    loadTasks();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// TAB 4 & 5: MEMBER & BOOST OPERATIONS
async function loadMemberOperations() {
  try {
    const settings = await API.get('/api/owner/settings');
    cachedClientId = settings.settings.discord_client_id || '';
    const guildInput = document.getElementById('input-member-guild-id');
    if (guildInput && !guildInput.value && settings.settings.default_guild_id) {
      guildInput.value = settings.settings.default_guild_id;
    }
    recalcOAuthUrl();
    loadConnectedBotGuilds();
  } catch (e) {}
}

async function loadConnectedBotGuilds() {
  const grid = document.getElementById('bot-guilds-grid');
  const countEl = document.getElementById('connected-guilds-count');
  if (!grid) return;

  try {
    const res = await API.get('/api/owner/bot-guilds');
    if (!res.success || !res.guilds || res.guilds.length === 0) {
      if (countEl) countEl.innerText = '0';
      grid.innerHTML = `<span style="color:var(--text-dim); font-size:0.78rem;">${res.error || 'Bot is not in any servers yet.'}</span>`;
      return;
    }
    if (countEl) countEl.innerText = res.guilds.length;
    grid.innerHTML = res.guilds.map(g => `
      <div style="background-color:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-sm); padding:0.55rem 0.85rem; display:flex; align-items:center; gap:0.75rem;">
        <div>
          <strong style="color:#fff; font-size:0.82rem;">${g.name}</strong>
          <div style="font-size:0.7rem; color:var(--text-dim); font-family:var(--font-mono);">ID: ${g.id}</div>
        </div>
        <button onclick="inspectBotGuild('${g.id}')" class="btn btn-primary btn-sm">Inspect</button>
      </div>
    `).join('');
  } catch (err) {
    grid.innerHTML = `<span style="color:var(--danger); font-size:0.78rem;">${err.message}</span>`;
  }
}

function inspectBotGuild(guildId) {
  document.getElementById('input-member-guild-id').value = guildId;
  const boostInput = document.getElementById('input-boost-guild-id');
  if (boostInput) boostInput.value = guildId;
  queryGuildTelemetry('members');
}

function recalcOAuthUrl() {
  const checkboxes = document.querySelectorAll('#oauth-perm-grid input[type="checkbox"]:checked');
  let bitmask = 0n;
  checkboxes.forEach(cb => {
    bitmask |= BigInt(cb.value);
  });
  const cid = cachedClientId || 'YOUR_CLIENT_ID';
  const url = `https://discord.com/api/oauth2/authorize?client_id=${cid}&permissions=${bitmask.toString()}&scope=bot%20applications.commands`;
  const out = document.getElementById('computed-oauth-url');
  if (out) out.value = url;
}

function openComputedOAuthUrl() {
  const url = document.getElementById('computed-oauth-url')?.value;
  if (!url || url.includes('YOUR_CLIENT_ID')) {
    showToast('Save your Discord Application / Client ID in Integrations first', 'warning');
    return;
  }
  window.open(url, '_blank');
}

async function queryGuildTelemetry(targetView = 'members') {
  const inputId = targetView === 'members' ? 'input-member-guild-id' : 'input-boost-guild-id';
  const guildId = document.getElementById(inputId).value.trim();
  const infoCard = document.getElementById(`${targetView}-result-card`);

  if (!guildId) {
    showToast('Enter a Discord Server / Guild ID', 'warning');
    return;
  }

  infoCard.style.display = 'block';
  infoCard.innerHTML = '<div style="color:var(--text-muted); padding:0.75rem;">Querying live Discord Guild API...</div>';

  try {
    const res = await API.get(`/api/owner/guild-telemetry?guild_id=${guildId}`);
    if (!res.success) {
      infoCard.innerHTML = `<div class="alert alert-danger">${res.error}</div>`;
      return;
    }

    const g = res.guild;
    if (targetView === 'members') {
      const rolesHtml = (g.roles || []).map(r => `<span class="badge badge-info">${r}</span>`).join(' ');
      infoCard.innerHTML = `
        <div style="background-color:var(--bg-surface); padding:0.9rem; border-radius:var(--radius-sm); border:1px solid var(--border);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.65rem;">
            <div>
              <strong style="font-size:1rem; color:#fff;">${g.name}</strong>
              <div style="font-size:0.72rem; color:var(--text-dim);">ID: <code>${g.id}</code></div>
            </div>
            <span class="badge badge-success">Connected</span>
          </div>
          <div class="grid-3" style="margin-bottom:0.75rem;">
            <div class="card stat-box"><div class="stat-box-label">Total Members</div><div class="stat-box-value">${g.approximate_member_count.toLocaleString()}</div></div>
            <div class="card stat-box"><div class="stat-box-label">Online Presence</div><div class="stat-box-value" style="color:var(--success);">${g.approximate_presence_count.toLocaleString()}</div></div>
            <div class="card stat-box"><div class="stat-box-label">Roles / Emojis</div><div class="stat-box-value">${g.roles_count || 0} / ${g.emojis_count || 0}</div></div>
          </div>
          <div style="font-size:0.76rem; color:var(--text-muted); margin-bottom:0.3rem;"><strong>Server Roles Hierarchy:</strong></div>
          <div style="display:flex; flex-wrap:wrap; gap:0.35rem;">${rolesHtml || 'None'}</div>
        </div>
      `;
    } else {
      const pm = g.perk_matrix || { progress_to_max_pct: 0, tiers: [] };
      const tiersHtml = (pm.tiers || []).map(tierObj => `
        <div class="card" style="border-color:${tierObj.unlocked ? 'rgba(16, 185, 129, 0.4)' : 'var(--border)'};">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
            <strong style="color:#fff;">Level ${tierObj.level} Perks (${tierObj.required_boosts} Boosts)</strong>
            <span class="badge ${tierObj.unlocked ? 'badge-success' : 'badge-warning'}">${tierObj.unlocked ? '✓ UNLOCKED' : 'LOCKED'}</span>
          </div>
          <ul class="perk-list">
            ${tierObj.perks.map(p => `<li>${tierObj.unlocked ? '🟢' : '⚪'} ${p}</li>`).join('')}
          </ul>
        </div>
      `).join('');

      infoCard.innerHTML = `
        <div class="card" style="margin-bottom:1rem;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <h3 class="card-title">${g.name} — Boost Level ${g.premium_tier}</h3>
              <div style="font-size:0.76rem; color:var(--text-muted); margin-top:2px;">
                Active Server Boosts: <strong>${g.premium_subscription_count} / 14</strong> for Maximum Tier (Level 3)
              </div>
            </div>
            <span class="badge badge-info" style="font-size:0.82rem; padding:0.3rem 0.75rem;">${g.premium_subscription_count} Boosts Active</span>
          </div>
          <div class="boost-gauge-track">
            <div class="boost-gauge-fill" style="width:${pm.progress_to_max_pct}%;"></div>
          </div>
          <div style="display:flex; justify-content:space-between; font-size:0.7rem; color:var(--text-dim);">
            <span>0 Boosts</span>
            <span>Level 1 (2 Boosts)</span>
            <span>Level 2 (7 Boosts)</span>
            <span>Level 3 Max (14 Boosts)</span>
          </div>
        </div>
        <div class="grid-3">
          ${tiersHtml}
        </div>
      `;
    }
  } catch (err) {
    infoCard.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
  }
}

async function loadBoostOperations() {
  const guildInput = document.getElementById('input-boost-guild-id');
  if (guildInput && !guildInput.value) {
    try {
      const settings = await API.get('/api/owner/settings');
      if (settings.settings.default_guild_id) {
        guildInput.value = settings.settings.default_guild_id;
        queryGuildTelemetry('boost');
      }
    } catch (e) {}
  }
}

// TAB 6: INTERNAL NODE KEYS
async function loadInternalKeys() {
  try {
    const data = await API.get('/api/owner/keys');
    cachedKeys = data.keys || [];
    const tbody = document.getElementById('internal-keys-table');
    if (!tbody) return;

    if (cachedKeys.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-dim); padding:1.5rem;">No internal authorization keys generated yet.</td></tr>';
      return;
    }

    tbody.innerHTML = cachedKeys.map(k => `
      <tr>
        <td><code>${k.key_code}</code></td>
        <td><strong>${k.label}</strong></td>
        <td><span class="badge badge-info">${k.service_scope}</span></td>
        <td><span class="badge ${k.status === 'active' ? 'badge-success' : 'badge-danger'}">${k.status}</span></td>
        <td>${k.expires_at ? new Date(k.expires_at).toLocaleDateString() : 'Never'}</td>
        <td>
          <div style="display:flex; gap:0.35rem;">
            <button onclick="copyRawText('${k.key_code}')" class="btn btn-secondary btn-sm">Copy</button>
            ${k.status === 'active' ? `<button onclick="revokeInternalKey(${k.id})" class="btn btn-danger btn-sm">Revoke</button>` : ''}
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function generateInternalKeyAction() {
  const label = document.getElementById('key-gen-label')?.value.trim() || 'Worker Node';
  const prefix = document.getElementById('key-gen-prefix')?.value || 'OWN';
  const scope = document.getElementById('key-gen-scope')?.value || 'all';
  const days = parseInt(document.getElementById('key-gen-days')?.value || '90');
  const count = parseInt(document.getElementById('key-gen-count')?.value || '1');

  try {
    const res = await API.post('/api/owner/keys', {
      label,
      prefix,
      service_scope: scope,
      duration_days: days,
      count
    });
    showToast(`Generated ${res.keys.length} authorization key(s)!`, 'success');
    loadInternalKeys();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function exportKeysJson() {
  const blob = new Blob([JSON.stringify(cachedKeys, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'internal_node_keys.json';
  a.click();
}

async function revokeInternalKey(keyId) {
  try {
    await API.post(`/api/owner/keys/${keyId}/revoke`);
    showToast('Authorization key revoked', 'info');
    loadInternalKeys();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// TAB 7: SETTINGS & INTEGRATIONS
async function loadSettings() {
  try {
    const data = await API.get('/api/owner/settings');
    const s = data.settings;
    cachedClientId = s.discord_client_id || '';

    document.getElementById('set-bot-token').value = s.discord_bot_token_set ? '********' : '';
    document.getElementById('set-client-id').value = s.discord_client_id || '';
    document.getElementById('set-client-secret').value = s.discord_client_secret_set ? '********' : '';
    document.getElementById('set-guild-id').value = s.default_guild_id || '';

    loadSavedWebhooks();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function saveSettingsAction(e) {
  e.preventDefault();
  const token = document.getElementById('set-bot-token').value.trim();
  const clientId = document.getElementById('set-client-id').value.trim();
  const clientSecret = document.getElementById('set-client-secret').value.trim();
  const guildId = document.getElementById('set-guild-id').value.trim();

  try {
    const res = await API.post('/api/owner/settings', {
      discord_bot_token: token,
      discord_client_id: clientId,
      discord_client_secret: clientSecret,
      default_guild_id: guildId
    });
    showToast(res.message, 'success');
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function testBotTokenAction() {
  const token = document.getElementById('set-bot-token').value.trim();
  const box = document.getElementById('bot-verify-result-box');
  try {
    showToast('Verifying token with Discord API...', 'info');
    const res = await API.post('/api/owner/test-bot', { bot_token: token });
    if (res.valid) {
      box.style.display = 'block';
      box.innerHTML = `<div class="alert alert-success">✓ Connected as <strong>${res.bot.username}</strong> (ID: <code>${res.bot.id}</code>) — Latency: <strong>${res.latency_ms || 0}ms</strong></div>`;
      showToast(`Verified: ${res.bot.username}`, 'success');
    } else {
      box.style.display = 'block';
      box.innerHTML = `<div class="alert alert-danger">${res.error}</div>`;
    }
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function loadSavedWebhooks() {
  try {
    const data = await API.get('/api/owner/webhooks');
    const list = document.getElementById('saved-webhooks-list');
    if (!list) return;

    if (data.webhooks.length === 0) {
      list.innerHTML = '<div style="color:var(--text-dim); font-size:0.78rem; padding:0.5rem 0;">No webhooks saved yet. Add one above to use in Broadcast Studio.</div>';
      return;
    }

    list.innerHTML = data.webhooks.map(w => `
      <div style="display:flex; justify-content:space-between; align-items:center; background-color:var(--bg-surface); padding:0.55rem 0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border); margin-bottom:0.4rem;">
        <div>
          <strong>${w.name}</strong>
          <span class="badge ${w.status === 'healthy' ? 'badge-success' : (w.status === 'failed' ? 'badge-danger' : 'badge-warning')}">${w.status}${w.last_latency_ms ? ` • ${w.last_latency_ms}ms` : ''}</span>
          <div style="font-size:0.7rem; color:var(--text-dim); font-family:var(--font-mono); margin-top:2px;">${w.url.substring(0, 48)}...</div>
        </div>
        <div style="display:flex; gap:0.35rem;">
          <button onclick="copyRawText('${w.url}')" class="btn btn-secondary btn-sm">Copy</button>
          <button onclick="testWebhookAction(${w.id})" class="btn btn-primary btn-sm">Ping</button>
          <button onclick="deleteWebhookAction(${w.id})" class="btn btn-danger btn-sm">&times;</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Webhooks error:', err);
  }
}

async function saveNewWebhookAction() {
  const name = document.getElementById('new-wh-name').value.trim();
  const url = document.getElementById('new-wh-url').value.trim();
  if (!name || !url) {
    showToast('Name and Webhook URL required', 'warning');
    return;
  }
  try {
    const res = await API.post('/api/owner/webhooks', { name, url });
    showToast(res.message, 'success');
    document.getElementById('new-wh-name').value = '';
    document.getElementById('new-wh-url').value = '';
    loadSavedWebhooks();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function testWebhookAction(whId) {
  try {
    showToast('Pinging webhook endpoint...', 'info');
    const res = await API.post(`/api/owner/webhooks/${whId}/test`);
    if (res.success) {
      showToast(`Webhook healthy! (${res.latency_ms || 0}ms)`, 'success');
    } else {
      showToast(`Webhook failed: ${res.error}`, 'danger');
    }
    loadSavedWebhooks();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function deleteWebhookAction(whId) {
  try {
    await API.delete(`/api/owner/webhooks/${whId}`);
    showToast('Webhook removed', 'info');
    loadSavedWebhooks();
    loadOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function updatePasswordAction(e) {
  e.preventDefault();
  const currentPassword = document.getElementById('pwd-current').value;
  const newPassword = document.getElementById('pwd-new').value;

  try {
    const res = await API.post('/api/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword
    });
    showToast(res.message, 'success');
    document.getElementById('pwd-current').value = '';
    document.getElementById('pwd-new').value = '';
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function updatePollInterval(msStr) {
  const ms = parseInt(msStr, 10);
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (ms > 0) {
    pollTimer = setInterval(() => {
      const active = document.querySelector('.nav-item.active');
      if (active && active.id === 'btn-nav-overview') {
        loadOverview();
      } else if (active && active.id === 'btn-nav-tasks') {
        loadTasks();
      }
    }, ms);
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const authRes = await fetch('/api/auth/me');
    const authData = await authRes.json();
    if (!authData.authenticated) {
      window.location.href = '/login';
      return;
    }
  } catch (e) {
    window.location.href = '/login';
    return;
  }

  switchTab('overview');
  updatePollInterval('5000');
});
