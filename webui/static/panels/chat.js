/**
 * TFNK™ 聊天面板（Chat Panel）
 * 負責訊息渲染、打字指示器、Markdown、代碼高亮
 */
class ChatPanel {
  constructor(app) {
    this.app = app;
    this.msgList    = document.getElementById('msg-list');
    this.chatInput  = document.getElementById('chat-input');
    this.sendBtn    = document.getElementById('send-btn');
    this.pttBtn     = document.getElementById('ptt-btn');
    this.typingEl   = document.getElementById('typing-indicator');
    this.messages   = [];
    this.isRecording = false;
    this.mediaRecorder = null;
    this.audioChunks  = [];
    this._init();
  }

  _init() {
    this.sendBtn.addEventListener('click', () => this.sendMessage());
    this.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) this.sendMessage();
      // Shift+Enter = newline (default)
    });

    // Push-to-Talk
    this.pttBtn.addEventListener('mousedown', () => this._startPTT());
    this.pttBtn.addEventListener('mouseup',   () => this._stopPTT());
    this.pttBtn.addEventListener('mouseleave',() => this._stopPTT());
    this.pttBtn.addEventListener('touchstart', (e) => { e.preventDefault(); this._startPTT(); });
    this.pttBtn.addEventListener('touchend',   (e) => { e.preventDefault(); this._stopPTT(); });

    // Auto-resize textarea
    this.chatInput.addEventListener('input', () => {
      this.chatInput.style.height = 'auto';
      this.chatInput.style.height = Math.min(this.chatInput.scrollHeight, 160) + 'px';
    });

    // Emoji click opens emoji picker
    const emojiFace = document.getElementById('emoji-face');
    if (emojiFace) {
      emojiFace.addEventListener('click', () => this._showEmojiMenu());
    }
  }

  // ── 訊息發送 ─────────────────────────────────────────────────────────────

  async sendMessage(text = null) {
    const content = (text || this.chatInput.value).trim();
    if (!content) return;

    this.chatInput.value = '';
    this.chatInput.style.height = 'auto';

    this._appendMessage({ role: 'user', content, timestamp: Date.now() });
    this._showTyping(true);
    if (this.app.emoji) this.app.emoji.setState('working');

    try {
      await this._streamChat(content);
    } catch (err) {
      this._appendMessage({
        role: 'system',
        content: `⚠️ 錯誤：${err.message}`,
        timestamp: Date.now(),
        isError: true,
      });
    } finally {
      this._showTyping(false);
      if (this.app.emoji) this.app.emoji.setState('idle');
    }
  }

  async _streamChat(content) {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: content,
        model: this.app.activeModel,
        mode: this.app.currentMode,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || '伺服器錯誤');
    }

    const msgEl = this._appendMessage({ role: 'agent', content: '', timestamp: Date.now(), streaming: true });
    const contentEl = msgEl.querySelector('.msg-content');
    let accumulated = '';

    const reader = resp.body.getReader();
    const dec = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = dec.decode(value, { stream: true });
      // SSE format: "data: ...\n\n"
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') break;
        try {
          const json = JSON.parse(data);
          const token = json.token || json.content || json.delta || '';
          accumulated += token;
          contentEl.innerHTML = this._renderMarkdown(accumulated);
          this._scrollToBottom();
        } catch (_) {
          // plain text token
          accumulated += data;
          contentEl.innerHTML = this._renderMarkdown(accumulated);
          this._scrollToBottom();
        }
      }
    }

    msgEl.classList.remove('streaming');
    this.messages.push({ role: 'agent', content: accumulated, timestamp: Date.now() });
    // Trigger code highlighting
    msgEl.querySelectorAll('pre code').forEach(b => hljs?.highlightElement(b));
    // TTS if voice is on
    if (this.app.voiceMode !== 'off' && accumulated) {
      this.app.voice?.speak(accumulated.slice(0, 400));
    }
  }

  // ── 訊息渲染 ─────────────────────────────────────────────────────────────

  _appendMessage({ role, content, timestamp, streaming = false, isError = false }) {
    const el = document.createElement('div');
    el.className = `msg msg-${role}${streaming ? ' streaming' : ''}${isError ? ' msg-error' : ''}`;

    const time = new Date(timestamp).toLocaleTimeString('zh-HK', { hour: '2-digit', minute: '2-digit' });
    const avatar = role === 'user' ? '👤' : role === 'agent' ? '🤖' : '⚠️';
    const label  = role === 'user' ? '你' : role === 'agent' ? 'TFNK™' : '系統';

    el.innerHTML = `
      <div class="msg-header">
        <span class="msg-avatar">${avatar}</span>
        <span class="msg-sender">${label}</span>
        <span class="msg-time">${time}</span>
        ${role === 'agent' ? '<button class="msg-copy-btn" title="複製">⎘</button>' : ''}
      </div>
      <div class="msg-content">${this._renderMarkdown(content)}</div>
      ${streaming ? '<div class="msg-cursor">▋</div>' : ''}
    `;

    if (role !== 'user') {
      el.querySelector('.msg-copy-btn')?.addEventListener('click', () => {
        navigator.clipboard.writeText(content);
        el.querySelector('.msg-copy-btn').textContent = '✓';
        setTimeout(() => el.querySelector('.msg-copy-btn').textContent = '⎘', 1500);
      });
    }

    this.msgList.appendChild(el);
    this._scrollToBottom();
    this.messages.push({ role, content, timestamp });
    return el;
  }

  _renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
      return marked.parse(text, { breaks: true, gfm: true });
    }
    // Minimal fallback
    return text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  _scrollToBottom() {
    this.msgList.scrollTop = this.msgList.scrollHeight;
  }

  // ── 打字指示器 ───────────────────────────────────────────────────────────

  _showTyping(show) {
    if (this.typingEl) {
      this.typingEl.style.display = show ? 'flex' : 'none';
    }
  }

  // ── 語音推送說話（PTT）──────────────────────────────────────────────────

  async _startPTT() {
    if (this.isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioChunks = [];
      this.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      this.mediaRecorder.ondataavailable = (e) => this.audioChunks.push(e.data);
      this.mediaRecorder.start();
      this.isRecording = true;
      this.pttBtn.classList.add('recording');
      if (this.app.voice) this.app.voice.setWaveformActive(true);
    } catch (err) {
      console.error('無法存取麥克風:', err);
    }
  }

  async _stopPTT() {
    if (!this.isRecording || !this.mediaRecorder) return;
    this.isRecording = false;
    this.pttBtn.classList.remove('recording');
    if (this.app.voice) this.app.voice.setWaveformActive(false);

    await new Promise((res) => {
      this.mediaRecorder.onstop = res;
      this.mediaRecorder.stop();
      this.mediaRecorder.stream.getTracks().forEach(t => t.stop());
    });

    const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
    const fd = new FormData();
    fd.append('audio', blob, 'voice.webm');

    try {
      const resp = await fetch('/api/voice/stt', { method: 'POST', body: fd });
      const data = await resp.json();
      if (data.text) {
        this.chatInput.value = data.text;
        await this.sendMessage();
      }
    } catch (err) {
      console.error('STT 失敗:', err);
    }
  }

  // ── 工具方法 ─────────────────────────────────────────────────────────────

  _showEmojiMenu() {
    // Simple emoji state picker popup
    const states = ['idle','thinking','happy','excited','working','error',
                    'sleeping','confused','laughing','proud','focused','alert',
                    'curious','sad','cool','success'];
    const existing = document.getElementById('emoji-menu');
    if (existing) { existing.remove(); return; }

    const menu = document.createElement('div');
    menu.id = 'emoji-menu';
    menu.className = 'emoji-menu';
    states.forEach(s => {
      const btn = document.createElement('button');
      btn.textContent = s;
      btn.addEventListener('click', () => {
        this.app.emoji?.setState(s);
        menu.remove();
      });
      menu.appendChild(btn);
    });
    document.getElementById('emoji-face')?.after(menu);
  }

  appendSystemMessage(text) {
    this._appendMessage({ role: 'system', content: text, timestamp: Date.now() });
  }

  clearHistory() {
    this.msgList.innerHTML = '';
    this.messages = [];
  }
}

window.ChatPanel = ChatPanel;
