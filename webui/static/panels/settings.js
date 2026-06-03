/**
 * TFNK™ 設定面板（Settings Panel）
 * 電路板/晶片概念 — 開關=插晶片動畫，API key 輸入=連接端口，轉盤切模式
 */
class SettingsPanel {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('panel-settings');
    this.config = {};
    this._init();
  }

  async _init() {
    await this._loadConfig();
    this._renderChipToggles();
    this._renderApiPorts();
    this._renderLockList();
    this._renderToolPolicy();
    this._renderThemeSelector();
    this._bindRotaryDial();
  }

  // ── 設定載入/儲存 ────────────────────────────────────────────────────────

  async _loadConfig() {
    try {
      const resp = await fetch('/api/config');
      this.config = await resp.json();
      this._applyToUI();
    } catch (e) {
      console.warn('載入設定失敗:', e);
    }
  }

  async _saveConfig(key, value) {
    this.config[key] = value;
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
      });
    } catch (e) {
      console.error('儲存設定失敗:', e);
    }
  }

  _applyToUI() {
    // Fill API key fields
    const keyFields = this.el.querySelectorAll('[data-api-key]');
    keyFields.forEach(f => {
      const k = f.dataset.apiKey;
      if (this.config[k]) f.value = '•'.repeat(12); // mask
    });
  }

  // ── 晶片切換開關 ─────────────────────────────────────────────────────────

  _renderChipToggles() {
    const container = this.el.querySelector('#chip-toggles');
    if (!container) return;

    const options = [
      { key: 'auto_mode',        label: '全自動模式',     default: true  },
      { key: 'audit_log',        label: '審計日誌',       default: true  },
      { key: 'auto_backup',      label: '自動備份',       default: true  },
      { key: 'voice_always_on',  label: '語音常開',       default: false },
      { key: 'wake_word',        label: '喚醒詞偵測',     default: false },
      { key: 'screen_translate', label: '截圖翻譯',       default: true  },
      { key: 'skill_reuse',      label: '技能複用(Hermes)', default: true },
      { key: 'tool_policy',      label: '工具政策審查',   default: true  },
      { key: 'lazy_correction',  label: '懶音修正',       default: true  },
      { key: 'confirm_irreversible', label: '不可逆確認', default: true  },
    ];

    container.innerHTML = '';
    options.forEach(opt => {
      const isOn = this.config[opt.key] ?? opt.default;
      const chip = document.createElement('div');
      chip.className = `chip-toggle ${isOn ? 'chip-on' : 'chip-off'}`;
      chip.dataset.key = opt.key;
      chip.innerHTML = `
        <div class="chip-socket">
          <div class="chip-body">
            <div class="chip-legs left"></div>
            <div class="chip-label">${opt.label}</div>
            <div class="chip-legs right"></div>
          </div>
          <div class="chip-glow"></div>
        </div>
        <span class="chip-status">${isOn ? '啟用' : '停用'}</span>
      `;
      chip.addEventListener('click', () => this._toggleChip(chip, opt.key));
      container.appendChild(chip);
    });
  }

  _toggleChip(el, key) {
    const isOn = el.classList.contains('chip-on');
    el.classList.toggle('chip-on', !isOn);
    el.classList.toggle('chip-off', isOn);
    el.querySelector('.chip-status').textContent = !isOn ? '啟用' : '停用';

    // Insertion animation
    el.classList.add('chip-inserting');
    setTimeout(() => el.classList.remove('chip-inserting'), 400);

    this._saveConfig(key, !isOn);
  }

  // ── API 連接端口 ─────────────────────────────────────────────────────────

  _renderApiPorts() {
    const container = this.el.querySelector('#api-ports');
    if (!container) return;

    const ports = [
      { key: 'anthropic_api_key',    label: 'Anthropic（Claude）',  placeholder: 'sk-ant-...' },
      { key: 'openai_api_key',       label: 'OpenAI',               placeholder: 'sk-...' },
      { key: 'openrouter_api_key',   label: 'OpenRouter',           placeholder: 'sk-or-...' },
      { key: 'groq_api_key',         label: 'Groq',                 placeholder: 'gsk_...' },
      { key: 'gemini_api_key',       label: 'Google Gemini',        placeholder: 'AIza...' },
      { key: 'google_api_key',       label: 'Google Search',        placeholder: 'AIza...' },
      { key: 'google_cse_id',        label: 'Google CSE ID',        placeholder: 'cx...' },
      { key: 'youtube_api_key',      label: 'YouTube API v3',       placeholder: 'AIza...' },
      { key: 'alpha_vantage_api_key',label: 'Alpha Vantage（財經）', placeholder: 'DEMO' },
      { key: 'finnhub_api_key',      label: 'Finnhub（財經）',       placeholder: 'pk_...' },
    ];

    container.innerHTML = '';
    ports.forEach(p => {
      const row = document.createElement('div');
      row.className = 'api-port-row';
      row.innerHTML = `
        <div class="port-connector"></div>
        <label class="port-label">${p.label}</label>
        <div class="port-input-wrap">
          <input type="password" class="port-input" data-api-key="${p.key}"
                 placeholder="${p.placeholder}" autocomplete="off" />
          <button class="port-save-btn" data-key="${p.key}" title="儲存">⚡</button>
          <button class="port-reveal-btn" title="顯示/隱藏">👁</button>
        </div>
        <div class="port-status" data-status="${p.key}"></div>
      `;
      const input = row.querySelector('.port-input');
      const saveBtn = row.querySelector('.port-save-btn');
      const revealBtn = row.querySelector('.port-reveal-btn');

      saveBtn.addEventListener('click', async () => {
        const val = input.value.trim();
        if (!val || val.startsWith('•')) return;
        await this._saveConfig(p.key, val);
        input.value = '•'.repeat(12);
        this._showPortStatus(p.key, '已儲存 ✓', 'ok');
        // Plug animation
        row.querySelector('.port-connector').classList.add('port-connected');
      });

      revealBtn.addEventListener('click', () => {
        input.type = input.type === 'password' ? 'text' : 'password';
      });

      container.appendChild(row);
    });
  }

  _showPortStatus(key, msg, type = 'ok') {
    const el = this.el.querySelector(`[data-status="${key}"]`);
    if (el) {
      el.textContent = msg;
      el.className = `port-status port-status-${type}`;
      setTimeout(() => { el.textContent = ''; el.className = 'port-status'; }, 3000);
    }
  }

  // ── 檔案鎖清單 ──────────────────────────────────────────────────────────

  _renderLockList() {
    const container = this.el.querySelector('#lock-list');
    if (!container) return;

    const addBtn = this.el.querySelector('#lock-add-btn');
    const lockInput = this.el.querySelector('#lock-path-input');

    const refresh = async () => {
      const resp = await fetch('/api/files/locks');
      const { locks } = await resp.json();
      container.innerHTML = '';
      (locks || []).forEach(path => {
        const row = document.createElement('div');
        row.className = 'lock-row';
        row.innerHTML = `
          <span class="lock-icon">🔒</span>
          <span class="lock-path">${path}</span>
          <button class="lock-del-btn" title="解鎖">✕</button>
        `;
        row.querySelector('.lock-del-btn').addEventListener('click', async () => {
          await fetch(`/api/files/locks/${encodeURIComponent(path)}`, { method: 'DELETE' });
          refresh();
        });
        container.appendChild(row);
      });
    };

    addBtn?.addEventListener('click', async () => {
      const path = lockInput?.value.trim();
      if (!path) return;
      await fetch('/api/files/locks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      if (lockInput) lockInput.value = '';
      refresh();
    });

    refresh();
  }

  // ── 工具政策（OpenClaw 風格）────────────────────────────────────────────

  _renderToolPolicy() {
    const container = this.el.querySelector('#tool-policy');
    if (!container) return;

    const tools = [
      { id: 'file_read',     label: '讀取檔案',   risk: 'low'    },
      { id: 'file_write',    label: '寫入檔案',   risk: 'medium' },
      { id: 'file_delete',   label: '刪除檔案',   risk: 'high'   },
      { id: 'web_search',    label: '網絡搜尋',   risk: 'low'    },
      { id: 'web_browse',    label: '瀏覽器操控', risk: 'medium' },
      { id: 'code_execute',  label: '執行代碼',   risk: 'high'   },
      { id: 'system_cmd',    label: '系統命令',   risk: 'high'   },
      { id: 'image_gen',     label: '圖像生成',   risk: 'low'    },
      { id: 'youtube_dl',    label: 'YouTube 下載', risk: 'low'  },
      { id: 'upload',        label: '上載/發佈',  risk: 'high'   },
    ];

    container.innerHTML = '';
    tools.forEach(tool => {
      const policies = ['allow', 'confirm', 'deny'];
      const current = this.config[`tool_policy_${tool.id}`] || (tool.risk === 'high' ? 'confirm' : 'allow');
      const row = document.createElement('div');
      row.className = `tool-policy-row risk-${tool.risk}`;
      row.innerHTML = `
        <span class="tool-risk-badge risk-${tool.risk}">${tool.risk === 'high' ? '高' : tool.risk === 'medium' ? '中' : '低'}</span>
        <span class="tool-label">${tool.label}</span>
        <div class="tool-policy-select">
          ${policies.map(p => `<button class="policy-btn ${p === current ? 'active' : ''}" data-policy="${p}" data-tool="${tool.id}">${p === 'allow' ? '允許' : p === 'confirm' ? '確認' : '拒絕'}</button>`).join('')}
        </div>
      `;
      row.querySelectorAll('.policy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          row.querySelectorAll('.policy-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this._saveConfig(`tool_policy_${tool.id}`, btn.dataset.policy);
        });
      });
      container.appendChild(row);
    });
  }

  // ── 主題選擇器（16 套 Cyberpunk 配色）──────────────────────────────────

  _renderThemeSelector() {
    const container = this.el.querySelector('#theme-selector');
    if (!container) return;

    const themes = [
      { id: 'cyber-blue',    name: '賽博藍',     primary: '#00D4FF', bg: '#0A0E1A' },
      { id: 'neon-orange',   name: '霓虹橙',     primary: '#FF6B35', bg: '#1A0A05' },
      { id: 'matrix-green',  name: '母體綠',     primary: '#00FF88', bg: '#051A0A' },
      { id: 'plasma-purple', name: '電漿紫',     primary: '#BF5FFF', bg: '#0D0A1A' },
      { id: 'solar-gold',    name: '太陽金',     primary: '#FFD700', bg: '#1A1500' },
      { id: 'ice-white',     name: '冰晶白',     primary: '#E8F4FF', bg: '#05080F' },
      { id: 'blood-red',     name: '血色紅',     primary: '#FF2244', bg: '#1A0508' },
      { id: 'acid-yellow',   name: '酸性黃',     primary: '#EEFF00', bg: '#0D0F00' },
      { id: 'deep-teal',     name: '深青色',     primary: '#00FFCC', bg: '#001A16' },
      { id: 'rose-pink',     name: '玫瑰粉',     primary: '#FF4DA6', bg: '#1A0010' },
      { id: 'amber-warm',    name: '琥珀暖',     primary: '#FF9500', bg: '#140A00' },
      { id: 'cobalt-deep',   name: '鈷藍深',     primary: '#2979FF', bg: '#030B1A' },
      { id: 'emerald',       name: '翡翠',       primary: '#00E676', bg: '#001A08' },
      { id: 'volcanic',      name: '火山紅橙',   primary: '#FF4500', bg: '#1A0900' },
      { id: 'arctic',        name: '極光藍白',   primary: '#80DEEA', bg: '#050D12' },
      { id: 'chrome',        name: '鉻銀',       primary: '#CFD8DC', bg: '#0A0A0A' },
    ];

    container.innerHTML = '';
    themes.forEach(t => {
      const swatch = document.createElement('div');
      swatch.className = `theme-swatch ${this.config.theme === t.id ? 'active' : ''}`;
      swatch.title = t.name;
      swatch.style.setProperty('--t-primary', t.primary);
      swatch.style.setProperty('--t-bg', t.bg);
      swatch.innerHTML = `<div class="swatch-dot"></div><span>${t.name}</span>`;
      swatch.addEventListener('click', () => {
        container.querySelectorAll('.theme-swatch').forEach(s => s.classList.remove('active'));
        swatch.classList.add('active');
        this.app.applyTheme(t);
        this._saveConfig('theme', t.id);
      });
      container.appendChild(swatch);
    });
  }

  // ── 轉盤模式選擇器 ─────────────────────────────────────────────────────

  _bindRotaryDial() {
    const dial = this.el.querySelector('#mode-dial');
    if (!dial) return;
    const modes = ['basic', 'thinking', 'collaborative'];
    let currentIdx = modes.indexOf(this.app.currentMode);

    const updateDial = (idx) => {
      currentIdx = idx;
      const angle = idx * 120; // 0°, 120°, 240°
      dial.style.transform = `rotate(${angle}deg)`;
      dial.dataset.mode = modes[idx];
      this.app.setMode(modes[idx]);
    };

    dial.addEventListener('click', () => updateDial((currentIdx + 1) % 3));

    // Drag rotation
    let startY = 0, startAngle = 0;
    dial.addEventListener('mousedown', (e) => {
      startY = e.clientY;
      startAngle = currentIdx * 120;
      const onMove = (e2) => {
        const delta = startY - e2.clientY;
        const newAngle = startAngle + delta;
        const idx = Math.abs(Math.round(newAngle / 120) % 3);
        updateDial(Math.max(0, Math.min(2, idx)));
      };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  }

  // ── 語音設定 ────────────────────────────────────────────────────────────

  bindVoiceSettings() {
    const voiceSel = this.el.querySelector('#voice-select');
    if (voiceSel) {
      voiceSel.value = this.config.tts_voice || 'zh-HK-HiuMaanNeural';
      voiceSel.addEventListener('change', () => {
        this._saveConfig('tts_voice', voiceSel.value);
      });
    }
    const wakeInput = this.el.querySelector('#wake-word-input');
    if (wakeInput) {
      wakeInput.value = this.config.wake_word || '嘿 TFNK';
      wakeInput.addEventListener('change', () => {
        this._saveConfig('wake_word', wakeInput.value);
      });
    }
  }

  refresh() {
    this._loadConfig();
  }
}

window.SettingsPanel = SettingsPanel;
