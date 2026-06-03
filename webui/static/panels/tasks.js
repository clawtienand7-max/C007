/**
 * TFNK™ 任務管理面板（Task Manager Panel）
 * Gantt 甘特格式、優先隊列、拖拽排序、任務 CRUD
 */
class TasksPanel {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('panel-tasks');
    this.tasks = [];
    this.activeTab = 'running';
    this._init();
  }

  async _init() {
    this._bindTabs();
    this._bindAddTask();
    this._bindEmergencyStop();
    await this.refresh();
    setInterval(() => this.refresh(), 5000);
  }

  // ── 資料 ──────────────────────────────────────────────────────────────────

  async refresh() {
    try {
      const resp = await fetch('/api/tasks');
      const data = await resp.json();
      this.tasks = data.tasks || [];
      this._render();
    } catch (e) {
      console.warn('載入任務失敗:', e);
    }
  }

  // ── 渲染 ──────────────────────────────────────────────────────────────────

  _render() {
    const list = this.el.querySelector('#task-list');
    const gantt = this.el.querySelector('#gantt-chart');
    if (!list) return;

    const filtered = this.tasks.filter(t => {
      if (this.activeTab === 'running')   return ['RUNNING', 'PAUSED'].includes(t.status);
      if (this.activeTab === 'queued')    return t.status === 'PENDING';
      if (this.activeTab === 'completed') return ['COMPLETED', 'FAILED'].includes(t.status);
      return true;
    });

    list.innerHTML = '';
    filtered.forEach(task => {
      const row = document.createElement('div');
      row.className = `task-row task-${task.status.toLowerCase()}`;
      row.dataset.id = task.id;

      const pct = Math.round((task.progress || 0) * 100);
      const statusIcon = {
        RUNNING: '▶', PAUSED: '⏸', PENDING: '⏳',
        COMPLETED: '✓', FAILED: '✗',
      }[task.status] || '?';

      const elapsed = task.started_at
        ? this._fmtDuration((Date.now() / 1000) - task.started_at)
        : '—';

      row.innerHTML = `
        <div class="task-header-row">
          <span class="task-status-icon">${statusIcon}</span>
          <span class="task-label">${task.label || task.id}</span>
          <span class="task-elapsed">${elapsed}</span>
          <div class="task-actions">
            ${task.status === 'RUNNING'  ? '<button class="t-btn pause-btn"  title="暫停">⏸</button>' : ''}
            ${task.status === 'PAUSED'   ? '<button class="t-btn resume-btn" title="繼續">▶</button>' : ''}
            ${task.status === 'PENDING'  ? '<button class="t-btn start-btn"  title="立即執行">▶</button>' : ''}
            <button class="t-btn cancel-btn" title="取消">✕</button>
          </div>
        </div>
        <div class="task-progress-bar">
          <div class="task-progress-fill" style="width:${pct}%"></div>
          <span class="task-pct">${pct}%</span>
        </div>
        ${task.estimated_remaining ? `<div class="task-eta">預計剩餘：${this._fmtDuration(task.estimated_remaining)}</div>` : ''}
        ${task.current_step ? `<div class="task-step">► ${task.current_step}</div>` : ''}
        ${task.requires_auth ? '<div class="task-auth-badge">⚠ 需要授權</div>' : ''}
      `;

      row.querySelector('.pause-btn')?.addEventListener('click',  () => this._taskAction(task.id, 'pause'));
      row.querySelector('.resume-btn')?.addEventListener('click', () => this._taskAction(task.id, 'resume'));
      row.querySelector('.start-btn')?.addEventListener('click',  () => this._taskAction(task.id, 'start'));
      row.querySelector('.cancel-btn')?.addEventListener('click', () => this._confirmCancel(task));

      list.appendChild(row);
    });

    // Gantt
    if (gantt) this._renderGantt(gantt, filtered);
    this._updateSummary();
  }

  _renderGantt(canvas, tasks) {
    const ctx = canvas.getContext('2d');
    const W = canvas.offsetWidth || 400;
    const H = Math.max(tasks.length * 28 + 20, 60);
    canvas.width = W;
    canvas.height = H;
    ctx.clearRect(0, 0, W, H);

    const now = Date.now() / 1000;
    const startTimes = tasks.map(t => t.started_at || now);
    const minT = Math.min(...startTimes) - 10;
    const maxT = now + 300;
    const range = maxT - minT;

    const mode = this.app.currentMode || 'basic';
    const colors = {
      basic: { running: '#00D4FF', pending: '#1A4466', completed: '#00664C', failed: '#661A00', paused: '#665500' },
      thinking: { running: '#FF6B35', pending: '#4A2010', completed: '#00664C', failed: '#661A00', paused: '#665500' },
      collaborative: { running: '#00FF88', pending: '#0A3320', completed: '#006632', failed: '#661A00', paused: '#665500' },
    };
    const c = colors[mode] || colors.basic;

    tasks.forEach((task, i) => {
      const y = i * 28 + 4;
      const st = (task.started_at || now) - minT;
      const dur = task.estimated_total || 60;
      const progress = task.progress || 0;

      const x1 = (st / range) * W;
      const totalW = (dur / range) * W;
      const doneW = totalW * progress;

      // Background bar
      ctx.fillStyle = c.pending;
      ctx.roundRect ? ctx.roundRect(x1, y + 4, totalW, 18, 3) : ctx.fillRect(x1, y + 4, totalW, 18);
      ctx.fill();

      // Progress fill
      ctx.fillStyle = c[task.status.toLowerCase()] || c.running;
      ctx.fillRect(x1, y + 4, doneW, 18);

      // Label
      ctx.fillStyle = '#CCDDEE';
      ctx.font = '11px Rajdhani, sans-serif';
      ctx.fillText((task.label || task.id).slice(0, 24), x1 + 4, y + 17);
    });

    // Now line
    const nowX = ((now - minT) / range) * W;
    ctx.strokeStyle = '#FF4444';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(nowX, 0);
    ctx.lineTo(nowX, H);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  _updateSummary() {
    const running   = this.tasks.filter(t => t.status === 'RUNNING').length;
    const pending   = this.tasks.filter(t => t.status === 'PENDING').length;
    const completed = this.tasks.filter(t => t.status === 'COMPLETED').length;
    const failed    = this.tasks.filter(t => t.status === 'FAILED').length;

    const el = this.el.querySelector('#task-summary');
    if (el) {
      el.innerHTML = `
        <span class="ts running">▶ 執行中 ${running}</span>
        <span class="ts pending">⏳ 排隊中 ${pending}</span>
        <span class="ts completed">✓ 完成 ${completed}</span>
        <span class="ts failed">✗ 失敗 ${failed}</span>
      `;
    }
  }

  // ── 操作 ──────────────────────────────────────────────────────────────────

  async _taskAction(id, action) {
    try {
      await fetch(`/api/tasks/${id}/${action}`, { method: 'POST' });
      await this.refresh();
    } catch (e) {
      console.error(`任務操作 ${action} 失敗:`, e);
    }
  }

  async _confirmCancel(task) {
    const confirmed = window.confirm(`確認取消任務「${task.label || task.id}」？`);
    if (!confirmed) return;
    try {
      await fetch(`/api/tasks/${task.id}`, { method: 'DELETE' });
      await this.refresh();
    } catch (e) {
      console.error('取消任務失敗:', e);
    }
  }

  // ── 新增任務 ────────────────────────────────────────────────────────────

  _bindAddTask() {
    const btn = this.el.querySelector('#add-task-btn');
    const modal = this.el.querySelector('#add-task-modal');
    const submitBtn = this.el.querySelector('#add-task-submit');
    const cancelBtn = this.el.querySelector('#add-task-cancel');

    btn?.addEventListener('click', () => { if (modal) modal.style.display = 'flex'; });
    cancelBtn?.addEventListener('click', () => { if (modal) modal.style.display = 'none'; });

    submitBtn?.addEventListener('click', async () => {
      const label = this.el.querySelector('#new-task-label')?.value.trim();
      const desc  = this.el.querySelector('#new-task-desc')?.value.trim();
      const when  = this.el.querySelector('#new-task-schedule')?.value;
      if (!label) return;

      await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label, description: desc, schedule: when }),
      });
      if (modal) modal.style.display = 'none';
      await this.refresh();
    });
  }

  _bindTabs() {
    const tabs = this.el.querySelectorAll('.task-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.activeTab = tab.dataset.tab;
        this._render();
      });
    });
  }

  _bindEmergencyStop() {
    const stopBtn = this.el.querySelector('#task-stop-all');
    stopBtn?.addEventListener('click', () => this.app.emergencyStop());
  }

  // ── 工具 ──────────────────────────────────────────────────────────────────

  _fmtDuration(seconds) {
    if (!seconds || seconds < 0) return '0s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  }
}

window.TasksPanel = TasksPanel;
