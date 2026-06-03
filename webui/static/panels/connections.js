/**
 * TFNK™ 連接狀態面板（Connection Status Panel）
 * 顯示每個外部連接的狀態、延遲、連接時長、使用情況
 */
class ConnectionsPanel {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('panel-connections');
    this.connections = [];
    this._init();
  }

  async _init() {
    this._bindRefresh();
    await this.refresh();
    setInterval(() => this.refresh(), 30000);
  }

  // ── 資料 ──────────────────────────────────────────────────────────────────

  async refresh() {
    try {
      const resp = await fetch('/api/connections');
      const data = await resp.json();
      this.connections = data.connections || [];
      this._render();
    } catch (e) {
      this._renderError('無法連接伺服器');
    }
  }

  async forceCheck() {
    const btn = this.el.querySelector('#conn-refresh-btn');
    if (btn) { btn.disabled = true; btn.textContent = '檢查中…'; }
    try {
      await fetch('/api/connections/check', { method: 'POST' });
      await this.refresh();
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '⟳ 重新檢查'; }
    }
  }

  // ── 渲染 ──────────────────────────────────────────────────────────────────

  _render() {
    const tbody = this.el.querySelector('#conn-tbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    // Sort: ok first, then error, then unknown
    const sorted = [...this.connections].sort((a, b) => {
      const order = { ok: 0, warning: 1, error: 2, unknown: 3 };
      return (order[a.status] ?? 3) - (order[b.status] ?? 3);
    });

    sorted.forEach(conn => {
      const row = document.createElement('tr');
      row.className = `conn-row conn-${conn.status}`;
      row.dataset.name = conn.name;

      const statusDot = { ok: '●', warning: '◕', error: '○', unknown: '?' }[conn.status] || '?';
      const statusClass = conn.status;
      const latency = conn.latency_ms != null
        ? `${conn.latency_ms}ms`
        : (conn.status === 'ok' ? '<1ms' : '—');
      const uptime = conn.connected_since
        ? this._fmtUptime(conn.connected_since)
        : '—';
      const used = conn.is_actually_used ? '✓' : '—';

      row.innerHTML = `
        <td class="conn-dot ${statusClass}" title="${conn.status}">
          <span class="dot-pulse">${statusDot}</span>
        </td>
        <td class="conn-name">
          <span class="conn-icon">${this._serviceIcon(conn.name)}</span>
          ${conn.display_name || conn.name}
        </td>
        <td class="conn-latency">${latency}</td>
        <td class="conn-uptime">${uptime}</td>
        <td class="conn-used ${conn.is_actually_used ? 'used-yes' : 'used-no'}">${used}</td>
        <td class="conn-error" title="${conn.error || ''}">${conn.error ? '⚠' : ''}</td>
        <td class="conn-actions">
          <button class="conn-del-btn" title="移除連接">✕</button>
        </td>
      `;

      row.querySelector('.conn-del-btn')?.addEventListener('click', () => this._deleteConnection(conn.name));

      // Click row to see details
      row.addEventListener('click', (e) => {
        if (e.target.classList.contains('conn-del-btn')) return;
        this._showDetail(conn);
      });

      tbody.appendChild(row);
    });

    this._updateSummary();
  }

  _renderError(msg) {
    const tbody = this.el.querySelector('#conn-tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="conn-error-row">⚠ ${msg}</td></tr>`;
    }
  }

  _updateSummary() {
    const ok  = this.connections.filter(c => c.status === 'ok').length;
    const err = this.connections.filter(c => c.status === 'error').length;
    const total = this.connections.length;
    const el = this.el.querySelector('#conn-summary');
    if (el) {
      el.innerHTML = `<span class="c-ok">● ${ok} 正常</span> / <span class="c-err">● ${err} 異常</span> / 共 ${total}`;
    }
  }

  // ── 連接詳情彈窗 ────────────────────────────────────────────────────────

  _showDetail(conn) {
    const existing = document.getElementById('conn-detail-popup');
    if (existing) existing.remove();

    const popup = document.createElement('div');
    popup.id = 'conn-detail-popup';
    popup.className = 'conn-detail-popup';
    popup.innerHTML = `
      <div class="cdp-header">
        <span>${this._serviceIcon(conn.name)} ${conn.display_name || conn.name}</span>
        <button class="cdp-close">✕</button>
      </div>
      <div class="cdp-body">
        <div class="cdp-row"><span>狀態</span><span class="conn-${conn.status}">${conn.status}</span></div>
        <div class="cdp-row"><span>延遲</span><span>${conn.latency_ms != null ? conn.latency_ms + 'ms' : '—'}</span></div>
        <div class="cdp-row"><span>連接時長</span><span>${conn.connected_since ? this._fmtUptime(conn.connected_since) : '—'}</span></div>
        <div class="cdp-row"><span>實際使用</span><span>${conn.is_actually_used ? '是' : '否'}</span></div>
        <div class="cdp-row"><span>最後檢查</span><span>${conn.last_checked ? new Date(conn.last_checked * 1000).toLocaleTimeString('zh-HK') : '—'}</span></div>
        ${conn.endpoint ? `<div class="cdp-row"><span>端點</span><span class="cdp-mono">${conn.endpoint}</span></div>` : ''}
        ${conn.error ? `<div class="cdp-row cdp-error"><span>錯誤</span><span>${conn.error}</span></div>` : ''}
        ${conn.models ? `<div class="cdp-row"><span>可用模型</span><span>${conn.models.slice(0,3).join(', ')}${conn.models.length > 3 ? '…' : ''}</span></div>` : ''}
      </div>
    `;
    popup.querySelector('.cdp-close').addEventListener('click', () => popup.remove());
    document.body.appendChild(popup);
    // Auto-close on outside click
    setTimeout(() => {
      document.addEventListener('click', function h(e) {
        if (!popup.contains(e.target)) { popup.remove(); document.removeEventListener('click', h); }
      });
    }, 100);
  }

  // ── 操作 ──────────────────────────────────────────────────────────────────

  async _deleteConnection(name) {
    if (!confirm(`確認移除連接「${name}」？`)) return;
    try {
      await fetch(`/api/connections/${encodeURIComponent(name)}`, { method: 'DELETE' });
      await this.refresh();
    } catch (e) {
      console.error('刪除連接失敗:', e);
    }
  }

  _bindRefresh() {
    const btn = this.el.querySelector('#conn-refresh-btn');
    btn?.addEventListener('click', () => this.forceCheck());
  }

  // ── 工具 ──────────────────────────────────────────────────────────────────

  _serviceIcon(name) {
    const icons = {
      ollama: '🦙', anthropic: '🤖', openai: '⬛', google: '🔵',
      groq: '⚡', openrouter: '🔀', gemini: '✨', youtube: '▶',
      tailscale: '🔒', nas: '💾', 'image-gen': '🖼', cerebras: '🧠',
      sambanova: '🌐', huggingface: '🤗', github: '🐙', mistral: '〰',
    };
    const lower = (name || '').toLowerCase();
    for (const [k, v] of Object.entries(icons)) {
      if (lower.includes(k)) return v;
    }
    return '🔌';
  }

  _fmtUptime(since) {
    const secs = Math.max(0, Math.floor(Date.now() / 1000 - since));
    if (secs < 60)    return `${secs}s`;
    if (secs < 3600)  return `${Math.floor(secs / 60)}m`;
    if (secs < 86400) return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
    return `${Math.floor(secs / 86400)}d ${Math.floor((secs % 86400) / 3600)}h`;
  }

  // Called by WebSocket updates
  onConnectionUpdate(connections) {
    this.connections = connections;
    this._render();
  }
}

window.ConnectionsPanel = ConnectionsPanel;
