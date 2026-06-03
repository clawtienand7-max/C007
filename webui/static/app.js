/**
 * TFNK™ Main Application Controller
 * app.js — Central orchestrator for the autonomous agent desktop
 */

'use strict';

class TFNKApp {
  constructor() {
    this.version = '4.2.1';
    this.mode = 'basic'; // basic | thinking | collaborative
    this.panels = new Map();
    this.ws = {};          // WebSocket connections
    this.settings = {};    // Loaded from localStorage
    this.stats = { cpu: 0, ram: 0, gpu: 0 };
    this.voiceMode = 'off';        // off | ptt | always
    this.isRecording = false;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isEmergencyStop = false;
    this.currentModel = 'gpt-4o';
    this.taskFilter = 'running';
    this.dragState = null;
    this.resizeState = null;

    // Sub-controllers (initialized after DOM ready)
    this.matrixBg = null;
    this.emojiEngine = null;
    this.chatPanel = null;
    this.settingsPanel = null;
    this.tasksPanel = null;
    this.connectionsPanel = null;
    this.intelPanel = null;
    this.graphPanel = null;

    this._init();
  }

  async _init() {
    this._loadSettings();
    this._initSplash();
  }

  _loadSettings() {
    try {
      const saved = localStorage.getItem('tfnk_settings');
      this.settings = saved ? JSON.parse(saved) : this._defaultSettings();
      const layout = localStorage.getItem('tfnk_layout');
      if (layout) this._savedLayout = JSON.parse(layout);
    } catch (e) {
      this.settings = this._defaultSettings();
    }
  }

  _defaultSettings() {
    return {
      mode: 'basic',
      voiceMode: 'off',
      wakeWord: '嘿 TFNK',
      voiceSensitivity: 70,
      matrixDensity: 50,
      fontSize: 13,
      chips: {
        voice_enabled: true,
        auto_think: true,
        web_search: false,
        code_exec: false,
        file_access: false,
        memory: true,
        require_confirm: true,
        sandbox: true,
        audit_log: true,
        tool_browser: false,
        tool_terminal: false,
        tool_email: false,
      },
      apiKeys: {},
    };
  }

  _saveSettings() {
    localStorage.setItem('tfnk_settings', JSON.stringify(this.settings));
  }

  _saveLayout() {
    const layout = {};
    this.panels.forEach((p, id) => {
      layout[id] = {
        floating: p.el.classList.contains('floating'),
        minimized: p.el.classList.contains('minimized'),
        hidden: p.el.classList.contains('hidden'),
        x: p.el.style.left,
        y: p.el.style.top,
        w: p.el.style.width,
        h: p.el.style.height,
      };
    });
    localStorage.setItem('tfnk_layout', JSON.stringify(layout));
  }

  // ===== SPLASH =====
  _initSplash() {
    const splash = document.getElementById('splash');
    if (!splash) { this._postSplash(); return; }

    const splashScreen = new SplashScreen({
      canvas: document.getElementById('splash-canvas'),
      logo: document.getElementById('splash-logo'),
      status: document.getElementById('splash-status'),
      bar: document.getElementById('splash-bar'),
      onComplete: () => this._postSplash(),
    });
    splashScreen.show();
  }

  _postSplash() {
    const splash = document.getElementById('splash');
    if (splash) {
      splash.classList.add('fade-out');
      setTimeout(() => { splash.style.display = 'none'; }, 900);
    }

    const app = document.getElementById('app');
    app.style.display = 'grid';

    this._initMatrix();
    this._initEmoji();
    this._initPanelManager();
    this._initPanelModules();
    this._initModeChips();
    this._initHeaderStats();
    this._initEmergencyStop();
    this._initVoiceBar();
    this._initKeyboardShortcuts();
    this._initWebSockets();
    this._restoreLayout();
    this._applySettings();
    this._startStatsMock();
    this._injectToastContainer();
    this._injectModals();
    this._applyMode(this.settings.mode || 'basic', false);

    this.showToast('系統就緒', 'success', '🟢');
  }

  // ===== MATRIX BACKGROUND =====
  _initMatrix() {
    this.matrixBg = new MatrixBackground({
      canvas: document.getElementById('matrix-canvas'),
      mode: this.mode,
    });
    this.matrixBg.setActivity(0.3);
  }

  // ===== EMOJI ENGINE =====
  _initEmoji() {
    const canvas = document.getElementById('emoji-canvas');
    if (!canvas) return;
    this.emojiEngine = new EmojiEngine(canvas);
    this.emojiEngine.setState('idle');
  }

  setEmojiState(state) {
    if (this.emojiEngine) this.emojiEngine.setState(state);
    const label = document.getElementById('emoji-state-label');
    if (label) {
      const names = {
        idle: '待機中', thinking: '思考中', happy: '開心', excited: '興奮',
        working: '工作中', error: '錯誤', sleeping: '休眠', confused: '困惑',
        laughing: '歡笑', proud: '自豪', focused: '專注', alert: '警覺',
        curious: '好奇', sad: '難過', angry: '憤怒', love: '喜愛',
        cool: '炫酷', nervous: '緊張', success: '成功', loading: '載入中',
      };
      label.textContent = names[state] || state;
    }
  }

  // ===== PANEL MANAGER =====
  _initPanelManager() {
    const panelEls = document.querySelectorAll('.panel[data-panel-id]');
    panelEls.forEach(el => {
      const id = el.dataset.panelId;
      this.panels.set(id, {
        el,
        id,
        floating: false,
        minimized: false,
        hidden: el.style.display === 'none',
      });
      this._bindPanelControls(el, id);
    });

    // Bind toggle buttons
    document.querySelectorAll('[data-panel]').forEach(btn => {
      if (btn.classList.contains('panel-toggle-btn')) {
        btn.addEventListener('click', () => this._togglePanel(btn.dataset.panel, btn));
      }
    });
  }

  _bindPanelControls(el, id) {
    const header = el.querySelector('.panel-header');
    if (!header) return;

    // Control buttons
    el.querySelectorAll('.panel-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const action = btn.dataset.action;
        if (action === 'minimize') this._minimizePanel(id);
        else if (action === 'float') this._floatPanel(id);
        else if (action === 'close') this._closePanel(id);
      });
    });

    // Drag
    header.addEventListener('mousedown', e => {
      if (e.button !== 0) return;
      if (e.target.closest('.panel-btn')) return;
      this._startDrag(e, el, id);
    });

    // Resize
    const resizeHandle = el.querySelector('.resize-handle');
    if (resizeHandle) {
      resizeHandle.addEventListener('mousedown', e => {
        e.stopPropagation();
        this._startResize(e, el);
      });
    }

    // Focus on click
    el.addEventListener('mousedown', () => this._focusPanel(el));
  }

  _focusPanel(el) {
    document.querySelectorAll('.panel.floating').forEach(p => p.classList.remove('top'));
    el.classList.add('top');
  }

  _minimizePanel(id) {
    const p = this.panels.get(id);
    if (!p) return;
    p.minimized = !p.minimized;
    p.el.classList.toggle('minimized', p.minimized);
    const btn = p.el.querySelector('[data-action="minimize"]');
    if (btn) btn.textContent = p.minimized ? '□' : '−';
    this._saveLayout();
  }

  _floatPanel(id) {
    const p = this.panels.get(id);
    if (!p) return;
    p.floating = !p.floating;
    p.el.classList.toggle('floating', p.floating);
    const header = p.el.querySelector('.panel-header');
    if (header) header.classList.toggle('draggable', p.floating);
    const btn = p.el.querySelector('[data-action="float"]');
    if (btn) btn.textContent = p.floating ? '⊡' : '⧉';

    if (p.floating) {
      const rect = p.el.getBoundingClientRect();
      p.el.style.left = rect.left + 'px';
      p.el.style.top = rect.top + 'px';
      p.el.style.width = rect.width + 'px';
      p.el.style.height = rect.height + 'px';
      document.body.appendChild(p.el);
    } else {
      const workspace = document.getElementById('workspace');
      p.el.style.left = '';
      p.el.style.top = '';
      p.el.style.width = '';
      p.el.style.height = '';
      workspace.appendChild(p.el);
    }
    this._saveLayout();
  }

  _closePanel(id) {
    const p = this.panels.get(id);
    if (!p) return;
    p.hidden = true;
    p.el.classList.add('hidden');
    // Update toggle button
    const toggleBtn = document.querySelector(`.panel-toggle-btn[data-panel="${p.el.id}"]`);
    if (toggleBtn) toggleBtn.classList.remove('active');
    this._saveLayout();
  }

  _togglePanel(panelId, btn) {
    const p = this.panels.get(panelId.replace('panel-', ''));
    if (!p) return;
    p.hidden = !p.hidden;
    p.el.classList.toggle('hidden', p.hidden);
    p.el.style.display = p.hidden ? 'none' : '';
    btn.classList.toggle('active', !p.hidden);
    this._saveLayout();
  }

  _startDrag(e, el, id) {
    if (!el.classList.contains('floating')) {
      this._floatPanel(id);
    }
    const rect = el.getBoundingClientRect();
    this.dragState = {
      el,
      startX: e.clientX - rect.left,
      startY: e.clientY - rect.top,
    };
    el.classList.add('dragging');
    document.addEventListener('mousemove', this._onDrag);
    document.addEventListener('mouseup', this._onDragEnd);
  }

  _onDrag = (e) => {
    if (!this.dragState) return;
    const { el, startX, startY } = this.dragState;
    let x = e.clientX - startX;
    let y = e.clientY - startY;
    // Clamp to viewport
    x = Math.max(0, Math.min(x, window.innerWidth - el.offsetWidth));
    y = Math.max(0, Math.min(y, window.innerHeight - el.offsetHeight));
    el.style.left = x + 'px';
    el.style.top = y + 'px';
  }

  _onDragEnd = () => {
    if (this.dragState) {
      this.dragState.el.classList.remove('dragging');
      this.dragState = null;
      this._saveLayout();
    }
    document.removeEventListener('mousemove', this._onDrag);
    document.removeEventListener('mouseup', this._onDragEnd);
  }

  _startResize(e, el) {
    e.preventDefault();
    const startW = el.offsetWidth;
    const startH = el.offsetHeight;
    const startX = e.clientX;
    const startY = e.clientY;

    const onMove = (ev) => {
      const w = Math.max(200, startW + ev.clientX - startX);
      const h = Math.max(120, startH + ev.clientY - startY);
      el.style.width = w + 'px';
      el.style.height = h + 'px';
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      this._saveLayout();
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  _restoreLayout() {
    if (!this._savedLayout) return;
    Object.entries(this._savedLayout).forEach(([id, state]) => {
      const p = this.panels.get(id);
      if (!p) return;
      if (state.hidden) {
        p.hidden = true;
        p.el.classList.add('hidden');
      }
      if (state.minimized) {
        p.minimized = true;
        p.el.classList.add('minimized');
      }
      if (state.floating) {
        this._floatPanel(id);
        if (state.x) p.el.style.left = state.x;
        if (state.y) p.el.style.top = state.y;
        if (state.w) p.el.style.width = state.w;
        if (state.h) p.el.style.height = state.h;
      }
    });
  }

  // ===== PANEL MODULES =====
  _initPanelModules() {
    if (window.ChatPanel) this.chatPanel = new ChatPanel(this);
    if (window.SettingsPanel) this.settingsPanel = new SettingsPanel(this);
    if (window.TasksPanel) this.tasksPanel = new TasksPanel(this);
    if (window.ConnectionsPanel) this.connectionsPanel = new ConnectionsPanel(this);
    if (window.IntelPanel) this.intelPanel = new IntelPanel(this);
    if (window.GraphPanel) this.graphPanel = new GraphPanel(this);
  }

  // ===== MODE SWITCHING =====
  _initModeChips() {
    document.querySelectorAll('.mode-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        this._applyMode(chip.dataset.mode, true);
      });
    });
  }

  _applyMode(mode, animate = true) {
    this.mode = mode;
    this.settings.mode = mode;
    this._saveSettings();

    // Update body class
    document.body.classList.remove('mode-basic', 'mode-thinking', 'mode-collaborative');
    document.body.classList.add(`mode-${mode}`);

    // Update chips
    document.querySelectorAll('.mode-chip').forEach(chip => {
      chip.classList.toggle('active', chip.dataset.mode === mode);
    });

    // Update mode badge in chat
    const badge = document.getElementById('chat-mode-badge');
    const names = { basic: '基礎', thinking: '思維', collaborative: '協作' };
    if (badge) badge.textContent = names[mode] || mode;

    // Update rotary label
    const rotaryLabel = document.getElementById('rotary-label');
    const rotaryNames = { basic: '基礎模式', thinking: '思維模式', collaborative: '協作模式' };
    if (rotaryLabel) rotaryLabel.textContent = rotaryNames[mode] || mode;

    // Update rotary pointer
    const pointer = document.getElementById('rotary-pointer');
    const angles = { basic: 0, thinking: 120, collaborative: 240 };
    if (pointer) {
      pointer.setAttribute('transform', `rotate(${angles[mode]}, 40, 40)`);
    }

    // Update rotary dots
    document.querySelectorAll('.rotary-dot').forEach(dot => {
      dot.classList.toggle('active', dot.dataset.mode === mode);
    });

    // Mode sweep animation
    if (animate) {
      const sweep = document.getElementById('mode-sweep');
      if (sweep) {
        sweep.classList.remove('sweeping');
        void sweep.offsetWidth; // reflow
        sweep.classList.add('sweeping');
        setTimeout(() => sweep.classList.remove('sweeping'), 600);
      }
    }

    // Update matrix background
    if (this.matrixBg) {
      const colors = { basic: '#00D4FF', thinking: '#FF6B35', collaborative: '#00FF88' };
      this.matrixBg.setMode(mode, colors[mode]);
    }

    this.showToast(`切換至${rotaryNames[mode]}`, 'success', '⚡');
  }

  // ===== HEADER STATS =====
  _initHeaderStats() {
    // Initial display handled by mock data
  }

  _updateStats(cpu, ram, gpu) {
    this.stats = { cpu, ram, gpu };
    const setBar = (id, val) => {
      const bar = document.getElementById(id + '-bar');
      const label = document.getElementById('stat-' + id + '-val');
      if (bar) bar.style.width = val + '%';
      if (label) label.textContent = Math.round(val) + '%';
    };
    setBar('cpu', cpu);
    setBar('ram', ram);
    setBar('gpu', gpu);
  }

  _startStatsMock() {
    // Simulate live stats until WebSocket provides real data
    let t = 0;
    const tick = () => {
      t += 0.05;
      const cpu = 35 + Math.sin(t) * 20 + Math.random() * 5;
      const ram = 60 + Math.sin(t * 0.7) * 15 + Math.random() * 3;
      const gpu = 25 + Math.sin(t * 1.3) * 20 + Math.random() * 8;
      this._updateStats(
        Math.min(99, Math.max(1, cpu)),
        Math.min(99, Math.max(1, ram)),
        Math.min(99, Math.max(1, gpu)),
      );

      // Tokens/s gauge
      const tps = 60 + Math.sin(t * 2) * 30 + Math.random() * 10;
      const tpsClamped = Math.min(120, Math.max(0, tps));
      const tpsGauge = document.getElementById('tokens-gauge');
      const tpsVal = document.getElementById('tokens-val');
      if (tpsGauge) tpsGauge.style.width = (tpsClamped / 120 * 100) + '%';
      if (tpsVal) tpsVal.textContent = Math.round(tpsClamped) + ' t/s';

      // Latency
      const latency = document.getElementById('stat-latency');
      if (latency) {
        const ms = 200 + Math.random() * 300;
        latency.innerHTML = Math.round(ms) + '<span class="stat-block-unit">ms</span>';
      }
    };
    setInterval(tick, 800);
    tick();
  }

  // ===== EMERGENCY STOP =====
  _initEmergencyStop() {
    const btn = document.getElementById('emergency-stop-btn');
    if (btn) btn.addEventListener('click', () => this.triggerEmergencyStop());

    const resume = document.getElementById('emergency-resume');
    if (resume) resume.addEventListener('click', () => this.resumeFromEmergency());
  }

  triggerEmergencyStop() {
    this.isEmergencyStop = true;
    const overlay = document.getElementById('emergency-overlay');
    if (overlay) overlay.classList.add('active');
    this.setEmojiState('error');
    if (this.matrixBg) this.matrixBg.setActivity(0.05);

    // POST to backend
    this.apiPost('/api/emergency-stop', {})
      .catch(() => {}); // Ignore if backend not available
  }

  resumeFromEmergency() {
    this.isEmergencyStop = false;
    const overlay = document.getElementById('emergency-overlay');
    if (overlay) overlay.classList.remove('active');
    this.setEmojiState('idle');
    if (this.matrixBg) this.matrixBg.setActivity(0.3);
    this.showToast('系統已恢復', 'success', '▶');
  }

  // ===== VOICE BAR =====
  _initVoiceBar() {
    // Voice mode toggle buttons
    document.querySelectorAll('.voice-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.voiceMode = btn.dataset.vmode;
        document.querySelectorAll('.voice-mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this._onVoiceModeChange(this.voiceMode);
      });
    });

    // Voice PTT button in chat (mousedown/mouseup)
    const pttBtn = document.getElementById('voice-ptt-btn');
    if (pttBtn) {
      pttBtn.addEventListener('mousedown', () => {
        if (this.voiceMode === 'ptt' || this.voiceMode === 'off') this._startRecording();
      });
      pttBtn.addEventListener('mouseup', () => {
        if (this.isRecording) this._stopRecording();
      });
      pttBtn.addEventListener('mouseleave', () => {
        if (this.isRecording) this._stopRecording();
      });
    }

    // Start waveform animation
    this._startWaveformAnimation();
  }

  _onVoiceModeChange(mode) {
    const wakeInd = document.getElementById('wake-word-indicator');
    const micIcon = document.getElementById('voice-mic-icon');
    if (mode === 'always') {
      if (wakeInd) wakeInd.classList.add('listening');
      if (micIcon) micIcon.classList.add('active');
      this.showToast('常開語音模式已啟用', 'success', '🎤');
    } else {
      if (wakeInd) wakeInd.classList.remove('listening');
      if (micIcon) micIcon.classList.remove('active');
    }
  }

  async _startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioChunks = [];
      this.mediaRecorder = new MediaRecorder(stream);
      this.mediaRecorder.ondataavailable = e => this.audioChunks.push(e.data);
      this.mediaRecorder.onstop = () => this._onRecordingStop();
      this.mediaRecorder.start();
      this.isRecording = true;
      const btn = document.getElementById('voice-ptt-btn');
      if (btn) btn.classList.add('active', 'recording');
      const micIcon = document.getElementById('voice-mic-icon');
      if (micIcon) micIcon.classList.add('active');
      if (this.matrixBg) this.matrixBg.setActivity(0.7);
      this.setEmojiState('focused');
    } catch (e) {
      this.showToast('無法存取麥克風', 'error', '🎤');
    }
  }

  _stopRecording() {
    if (this.mediaRecorder && this.isRecording) {
      this.mediaRecorder.stop();
      this.mediaRecorder.stream.getTracks().forEach(t => t.stop());
      this.isRecording = false;
      const btn = document.getElementById('voice-ptt-btn');
      if (btn) btn.classList.remove('active', 'recording');
      const micIcon = document.getElementById('voice-mic-icon');
      if (micIcon) micIcon.classList.remove('active');
      if (this.matrixBg) this.matrixBg.setActivity(0.3);
    }
  }

  async _onRecordingStop() {
    const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', blob, 'voice.webm');

    try {
      const res = await fetch('/api/voice/stt', { method: 'POST', body: formData });
      if (res.ok) {
        const data = await res.json();
        if (data.text) {
          const input = document.getElementById('chat-input');
          if (input) {
            input.value = data.text;
            this._sendMessage(data.text);
          }
        }
      }
    } catch (e) {
      // Voice STT not available
    }
  }

  _startWaveformAnimation() {
    const canvas = document.getElementById('voice-waveform');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let phase = 0;

    const draw = () => {
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const primary = getComputedStyle(document.body).getPropertyValue('--primary').trim() || '#00D4FF';
      ctx.strokeStyle = primary;
      ctx.lineWidth = 1;
      ctx.globalAlpha = this.isRecording ? 0.9 : 0.35;

      ctx.beginPath();
      for (let x = 0; x < w; x++) {
        const amp = this.isRecording ? 7 : 2;
        const freq = this.isRecording ? 3 : 1.5;
        const y = h / 2 + Math.sin((x / w * Math.PI * freq * 2) + phase) * amp
                  + Math.sin((x / w * Math.PI * 5) + phase * 1.5) * (amp * 0.4);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      phase += this.isRecording ? 0.15 : 0.04;
      requestAnimationFrame(draw);
    };
    draw();
  }

  // ===== WEBSOCKETS =====
  _initWebSockets() {
    this._connectWS('chat', '/ws/chat');
    this._connectWS('stats', '/ws/stats');
    this._connectWS('voice', '/ws/voice');
    this._connectWS('mobile', '/ws/mobile');
  }

  _connectWS(name, path) {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}${path}`;

    const connect = () => {
      try {
        const ws = new WebSocket(url);
        ws.onopen = () => {
          this.ws[name] = ws;
          if (this.connectionsPanel) this.connectionsPanel.onWSConnect(name);
        };
        ws.onmessage = (e) => this._onWSMessage(name, e);
        ws.onclose = () => {
          delete this.ws[name];
          if (this.connectionsPanel) this.connectionsPanel.onWSDisconnect(name);
          // Reconnect after 3s
          setTimeout(() => connect(), 3000);
        };
        ws.onerror = () => {};
      } catch (e) {}
    };
    connect();
  }

  _onWSMessage(name, e) {
    try {
      const msg = JSON.parse(e.data);
      switch (name) {
        case 'chat':
          if (msg.type === 'message' && this.chatPanel) {
            this.chatPanel.receiveAgentMessage(msg.content, msg.role);
          }
          if (msg.type === 'typing' && this.chatPanel) {
            this.chatPanel.setTyping(msg.active);
          }
          if (msg.type === 'emoji') this.setEmojiState(msg.state);
          break;
        case 'stats':
          if (msg.cpu !== undefined) this._updateStats(msg.cpu, msg.ram, msg.gpu);
          break;
        case 'mobile':
          if (msg.type === 'command') this._handleMobileCommand(msg);
          break;
      }
    } catch (e) {}
  }

  _handleMobileCommand(msg) {
    if (msg.action === 'mode') this._applyMode(msg.value, true);
    if (msg.action === 'send' && this.chatPanel) this.chatPanel.sendMessage(msg.text);
  }

  // ===== API CLIENT =====
  async apiGet(path) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async apiPost(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async apiDelete(path) {
    const res = await fetch(path, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  // ===== CHAT SEND =====
  _sendMessage(text) {
    if (!text || !text.trim()) return;
    if (this.chatPanel) this.chatPanel.sendMessage(text);
  }

  // ===== KEYBOARD SHORTCUTS =====
  _initKeyboardShortcuts() {
    document.addEventListener('keydown', e => {
      const ctrl = e.ctrlKey || e.metaKey;

      // Ctrl+Enter: Send message
      if (ctrl && e.key === 'Enter') {
        e.preventDefault();
        const input = document.getElementById('chat-input');
        if (input && input.value.trim()) this._sendMessage(input.value);
      }

      // Ctrl+Space: Push-to-talk
      if (ctrl && e.key === ' ') {
        e.preventDefault();
        if (!this.isRecording) this._startRecording();
      }

      // Ctrl+E: Emergency stop
      if (ctrl && e.key === 'e') {
        e.preventDefault();
        if (this.isEmergencyStop) this.resumeFromEmergency();
        else this.triggerEmergencyStop();
      }

      // Ctrl+T: Toggle always-on voice
      if (ctrl && e.key === 't') {
        e.preventDefault();
        const newMode = this.voiceMode === 'always' ? 'off' : 'always';
        this.voiceMode = newMode;
        document.querySelectorAll('.voice-mode-btn').forEach(btn => {
          btn.classList.toggle('active', btn.dataset.vmode === newMode);
        });
        this._onVoiceModeChange(newMode);
      }

      // Escape: Close overlays
      if (e.key === 'Escape') {
        document.getElementById('confirm-modal')?.classList.remove('active');
        document.getElementById('task-modal')?.classList.remove('active');
        document.getElementById('context-menu')?.classList.remove('active');
      }
    });

    // Ctrl+Space keyup: stop recording
    document.addEventListener('keyup', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === ' ') {
        if (this.isRecording) this._stopRecording();
      }
    });
  }

  // ===== MODALS =====
  _injectToastContainer() {
    if (!document.getElementById('toast-container')) {
      const tc = document.createElement('div');
      tc.id = 'toast-container';
      document.body.appendChild(tc);
    }
  }

  _injectModals() {
    // Confirm modal
    if (!document.getElementById('confirm-modal')) {
      const m = document.createElement('div');
      m.id = 'confirm-modal';
      m.innerHTML = `<div class="confirm-box">
        <div class="confirm-title" id="confirm-title">確認操作</div>
        <div class="confirm-msg" id="confirm-msg"></div>
        <div class="confirm-btns">
          <button class="confirm-btn" id="confirm-cancel">取消</button>
          <button class="confirm-btn danger" id="confirm-ok">確認</button>
        </div>
      </div>`;
      document.body.appendChild(m);
      document.getElementById('confirm-cancel').addEventListener('click', () => {
        m.classList.remove('active');
        if (this._confirmReject) this._confirmReject();
      });
      document.getElementById('confirm-ok').addEventListener('click', () => {
        m.classList.remove('active');
        if (this._confirmResolve) this._confirmResolve();
      });
    }

    // Task modal
    if (!document.getElementById('task-modal')) {
      const m = document.createElement('div');
      m.id = 'task-modal';
      m.innerHTML = `<div class="task-modal-box">
        <div class="task-modal-title">新增任務</div>
        <div class="task-modal-field">
          <label class="task-modal-label">任務名稱</label>
          <input class="task-modal-input" id="new-task-name" type="text" placeholder="任務描述..." />
        </div>
        <div class="task-modal-field">
          <label class="task-modal-label">優先級</label>
          <select class="task-modal-select" id="new-task-priority">
            <option value="high">高</option>
            <option value="normal" selected>普通</option>
            <option value="low">低</option>
          </select>
        </div>
        <div class="task-modal-field">
          <label class="task-modal-label">預計時間 (秒)</label>
          <input class="task-modal-input" id="new-task-eta" type="number" value="60" min="1" />
        </div>
        <div class="task-modal-btns">
          <button class="confirm-btn" id="task-modal-cancel">取消</button>
          <button class="confirm-btn" id="task-modal-ok" style="border-color:var(--primary);color:var(--primary)">新增</button>
        </div>
      </div>`;
      document.body.appendChild(m);
      document.getElementById('task-modal-cancel').addEventListener('click', () => m.classList.remove('active'));
      document.getElementById('task-modal-ok').addEventListener('click', () => {
        const name = document.getElementById('new-task-name').value.trim();
        const priority = document.getElementById('new-task-priority').value;
        const eta = parseInt(document.getElementById('new-task-eta').value) || 60;
        if (name && this.tasksPanel) this.tasksPanel.addTask({ name, priority, eta });
        m.classList.remove('active');
      });
    }
  }

  showConfirm(title, msg) {
    return new Promise((resolve, reject) => {
      this._confirmResolve = resolve;
      this._confirmReject = reject;
      document.getElementById('confirm-title').textContent = title;
      document.getElementById('confirm-msg').textContent = msg;
      document.getElementById('confirm-modal').classList.add('active');
    });
  }

  showToast(text, type = 'info', icon = 'ℹ') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-text">${text}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('fade-out');
      setTimeout(() => toast.remove(), 350);
    }, 3000);
  }

  // ===== SETTINGS APPLICATION =====
  _applySettings() {
    // Apply saved chip states
    if (this.settings.chips) {
      Object.entries(this.settings.chips).forEach(([key, val]) => {
        const socket = document.querySelector(`.chip-socket[data-chip="${key}"]`);
        if (socket) {
          socket.classList.toggle('on', val);
          const statusEl = document.getElementById(`chip-status-${key}`);
          if (statusEl) statusEl.textContent = val ? '啟用' : '停用';
        }
      });
    }

    // Font size
    if (this.settings.fontSize) {
      document.body.style.fontSize = this.settings.fontSize + 'px';
      const slider = document.getElementById('font-size-slider');
      if (slider) slider.value = this.settings.fontSize;
    }

    // Matrix density
    if (this.matrixBg && this.settings.matrixDensity !== undefined) {
      this.matrixBg.setActivity(this.settings.matrixDensity / 100);
      const slider = document.getElementById('matrix-density');
      if (slider) slider.value = this.settings.matrixDensity;
    }

    // Voice settings
    if (this.settings.wakeWord) {
      const input = document.getElementById('wake-word-input');
      if (input) input.value = this.settings.wakeWord;
      const ind = document.getElementById('wake-word-indicator');
      if (ind) ind.textContent = `WAKE: ${this.settings.wakeWord}`;
    }

    // Sliders
    const densitySlider = document.getElementById('matrix-density');
    if (densitySlider) {
      densitySlider.addEventListener('input', () => {
        const val = parseInt(densitySlider.value);
        this.settings.matrixDensity = val;
        if (this.matrixBg) this.matrixBg.setActivity(val / 100);
        this._saveSettings();
      });
    }

    const fontSlider = document.getElementById('font-size-slider');
    if (fontSlider) {
      fontSlider.addEventListener('input', () => {
        const val = parseInt(fontSlider.value);
        this.settings.fontSize = val;
        document.body.style.fontSize = val + 'px';
        this._saveSettings();
      });
    }

    const wakeWordInput = document.getElementById('wake-word-input');
    if (wakeWordInput) {
      wakeWordInput.addEventListener('change', () => {
        this.settings.wakeWord = wakeWordInput.value;
        const ind = document.getElementById('wake-word-indicator');
        if (ind) ind.textContent = `WAKE: ${wakeWordInput.value}`;
        this._saveSettings();
      });
    }

    // Model switcher
    const modelSwitcher = document.getElementById('model-switcher');
    if (modelSwitcher) {
      modelSwitcher.addEventListener('change', () => {
        this.currentModel = modelSwitcher.value;
        const nameEl = document.getElementById('model-current-name');
        if (nameEl) nameEl.textContent = modelSwitcher.options[modelSwitcher.selectedIndex].text;
        this.showToast(`切換至 ${modelSwitcher.options[modelSwitcher.selectedIndex].text}`, 'success', '⚡');
      });
    }
  }
}

// ===== BOOTSTRAP =====
document.addEventListener('DOMContentLoaded', () => {
  window.TFNK = new TFNKApp();
});
