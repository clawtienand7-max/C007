/**
 * TFNK™ 情報中心面板（Intelligence Center Panel）
 * 模型比較 / 每日 AI 新聞 / 免費模型清單 / 代理比較 / 熱門工具
 */
class IntelPanel {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('panel-intel');
    this.activeTab = 'news';
    this.data = {};
    this._init();
  }

  async _init() {
    this._bindTabs();
    this._bindRefresh();
    await this.refresh();
  }

  // ── 資料 ──────────────────────────────────────────────────────────────────

  async refresh() {
    const tabs = ['news', 'models', 'free-models', 'agents', 'tools'];
    const btn = this.el.querySelector('#intel-refresh-btn');
    if (btn) btn.disabled = true;

    try {
      await Promise.allSettled(tabs.map(t => this._fetchTab(t)));
      this._renderActive();
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '⟳ 更新'; }
      this._updateTimestamp();
    }
  }

  async _fetchTab(tab) {
    try {
      const resp = await fetch(`/api/intel/${tab}`);
      this.data[tab] = await resp.json();
    } catch (_) {
      this.data[tab] = null;
    }
  }

  // ── 渲染 ──────────────────────────────────────────────────────────────────

  _renderActive() {
    const content = this.el.querySelector('#intel-content');
    if (!content) return;
    content.innerHTML = '';

    switch (this.activeTab) {
      case 'news':        this._renderNews(content);       break;
      case 'models':      this._renderModels(content);     break;
      case 'free-models': this._renderFreeModels(content); break;
      case 'agents':      this._renderAgents(content);     break;
      case 'tools':       this._renderTools(content);      break;
    }
  }

  // (a) AI 新聞
  _renderNews(el) {
    const news = this.data['news'];
    if (!news?.items?.length) {
      el.innerHTML = '<div class="intel-empty">尚未載入新聞，點擊更新</div>';
      return;
    }
    news.items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'news-card';
      const ago = this._timeAgo(item.published_at);
      card.innerHTML = `
        <div class="news-source">${item.source}</div>
        <div class="news-title">${item.title}</div>
        <div class="news-meta">
          <span class="news-time">${ago}</span>
          ${item.category ? `<span class="news-cat">${item.category}</span>` : ''}
        </div>
        ${item.summary ? `<div class="news-summary">${item.summary}</div>` : ''}
      `;
      if (item.url) {
        card.style.cursor = 'pointer';
        card.addEventListener('click', () => window.open(item.url, '_blank'));
      }
      el.appendChild(card);
    });
  }

  // (b) 模型比較
  _renderModels(el) {
    const models = this.data['models'];
    if (!models?.models?.length) {
      el.innerHTML = '<div class="intel-empty">載入中…</div>';
      return;
    }
    const maxCtx = Math.max(...models.models.map(m => m.context_window || 0));
    const maxIn  = Math.max(...models.models.map(m => m.price_in || 0));

    const table = document.createElement('div');
    table.className = 'model-table';
    table.innerHTML = `
      <div class="model-table-header">
        <span>模型</span><span>上下文</span><span>輸入價</span><span>輸出價</span><span>評分</span>
      </div>
    `;
    models.models.forEach(m => {
      const row = document.createElement('div');
      row.className = 'model-row';
      const ctxPct = maxCtx ? ((m.context_window || 0) / maxCtx * 100) : 0;
      const inPct  = maxIn  ? ((m.price_in || 0) / maxIn * 100) : 0;
      const stars  = '★'.repeat(Math.round(m.rating || 3)) + '☆'.repeat(5 - Math.round(m.rating || 3));
      row.innerHTML = `
        <div class="model-name">
          <span class="model-provider-badge">${m.provider}</span>
          ${m.name}
        </div>
        <div class="model-bar-cell">
          <div class="hud-bar"><div class="hud-fill" style="width:${ctxPct}%"></div></div>
          <span>${this._fmtCtx(m.context_window)}</span>
        </div>
        <div class="model-price">${m.price_in != null ? '$' + m.price_in.toFixed(2) : '免費'}</div>
        <div class="model-price">${m.price_out != null ? '$' + m.price_out.toFixed(2) : '免費'}</div>
        <div class="model-stars" title="${m.rating || 3}/5">${stars}</div>
      `;
      table.appendChild(row);
    });
    el.appendChild(table);
  }

  // (c) 免費模型
  _renderFreeModels(el) {
    const data = this.data['free-models'];
    if (!data?.models?.length) {
      el.innerHTML = '<div class="intel-empty">載入中…</div>';
      return;
    }
    const grid = document.createElement('div');
    grid.className = 'free-models-grid';

    const byProvider = {};
    data.models.forEach(m => {
      if (!byProvider[m.provider]) byProvider[m.provider] = [];
      byProvider[m.provider].push(m);
    });

    Object.entries(byProvider).forEach(([provider, ms]) => {
      const group = document.createElement('div');
      group.className = 'free-model-group';
      group.innerHTML = `<div class="fmg-header">${provider}</div>`;
      ms.forEach(m => {
        const card = document.createElement('div');
        card.className = `free-model-card ${m.selected ? 'selected' : ''}`;
        card.innerHTML = `
          <div class="fmc-name">${m.name}</div>
          <div class="fmc-meta">
            ${m.context_window ? `<span>${this._fmtCtx(m.context_window)}</span>` : ''}
            ${m.is_free ? '<span class="free-badge">免費</span>' : ''}
          </div>
        `;
        card.addEventListener('click', () => {
          card.classList.toggle('selected');
          m.selected = card.classList.contains('selected');
          this.app.updateSelectedModels?.(data.models.filter(x => x.selected));
        });
        group.appendChild(card);
      });
      grid.appendChild(group);
    });
    el.appendChild(grid);
  }

  // (d) 代理比較（Claude / Manus / Hermes / OpenClaw）
  _renderAgents(el) {
    const data = this.data['agents'];
    const agents = data?.agents || this._staticAgentData();
    const features = [
      '自主迴圈', '任務拆解', '技能重用', '工具政策', '持久記憶',
      '子代理', '網頁瀏覽', '代碼執行', '自我升級', '多模態',
      '非同步背景', '計劃模式', '開源', '本地部署',
    ];

    const table = document.createElement('table');
    table.className = 'agent-compare-table';
    const thead = `<thead><tr><th>功能</th>${agents.map(a => `<th class="agent-col">${a.name}</th>`).join('')}</tr></thead>`;
    const rows = features.map(f => {
      const cells = agents.map(a => {
        const val = a.features?.[f];
        const icon = val === true ? '✓' : val === false ? '✗' : val === 'partial' ? '◐' : '—';
        const cls  = val === true ? 'feat-yes' : val === false ? 'feat-no' : 'feat-partial';
        return `<td class="${cls}">${icon}</td>`;
      });
      return `<tr><td class="feat-name">${f}</td>${cells.join('')}</tr>`;
    });
    table.innerHTML = `${thead}<tbody>${rows.join('')}</tbody>`;
    el.appendChild(table);

    // Last updated note
    if (data?.last_updated) {
      const note = document.createElement('div');
      note.className = 'intel-note';
      note.textContent = `代理資訊更新：${new Date(data.last_updated * 1000).toLocaleDateString('zh-HK')}`;
      el.appendChild(note);
    }
  }

  _staticAgentData() {
    return [
      {
        name: 'Claude', features: {
          '自主迴圈': true, '任務拆解': true, '技能重用': true, '工具政策': true,
          '持久記憶': 'partial', '子代理': true, '網頁瀏覽': true, '代碼執行': true,
          '自我升級': 'partial', '多模態': true, '非同步背景': true, '計劃模式': true,
          '開源': false, '本地部署': false,
        },
      },
      {
        name: 'Manus', features: {
          '自主迴圈': true, '任務拆解': true, '技能重用': false, '工具政策': false,
          '持久記憶': true, '子代理': true, '網頁瀏覽': true, '代碼執行': true,
          '自我升級': false, '多模態': true, '非同步背景': true, '計劃模式': true,
          '開源': false, '本地部署': false,
        },
      },
      {
        name: 'Hermes', features: {
          '自主迴圈': true, '任務拆解': true, '技能重用': true, '工具政策': false,
          '持久記憶': true, '子代理': 'partial', '網頁瀏覽': true, '代碼執行': true,
          '自我升級': true, '多模態': false, '非同步背景': 'partial', '計劃模式': 'partial',
          '開源': true, '本地部署': true,
        },
      },
      {
        name: 'OpenClaw', features: {
          '自主迴圈': true, '任務拆解': 'partial', '技能重用': 'partial', '工具政策': true,
          '持久記憶': true, '子代理': false, '網頁瀏覽': true, '代碼執行': true,
          '自我升級': true, '多模態': 'partial', '非同步背景': false, '計劃模式': false,
          '開源': true, '本地部署': true,
        },
      },
    ];
  }

  // (e) 熱門工具
  _renderTools(el) {
    const data = this.data['tools'];
    const categories = data?.categories || this._staticToolData();

    categories.forEach(cat => {
      const section = document.createElement('div');
      section.className = 'tool-section';
      section.innerHTML = `<div class="tool-cat-header">${cat.name}</div>`;
      const grid = document.createElement('div');
      grid.className = 'tool-grid';
      (cat.tools || []).forEach(tool => {
        const card = document.createElement('div');
        card.className = 'tool-card';
        card.innerHTML = `
          <div class="tool-name">${tool.name}</div>
          <div class="tool-desc">${tool.description || ''}</div>
          ${tool.free ? '<span class="free-badge">免費</span>' : ''}
          ${tool.trending ? '<span class="trend-badge">🔥 熱門</span>' : ''}
        `;
        grid.appendChild(card);
      });
      section.appendChild(grid);
      el.appendChild(section);
    });
  }

  _staticToolData() {
    return [
      {
        name: '影片生成',
        tools: [
          { name: 'Sora',        description: 'OpenAI 影片生成', trending: true },
          { name: 'Runway Gen-3',description: '專業影片AI',      trending: true },
          { name: 'Kling AI',    description: '快手影片生成',    trending: true, free: true },
        ],
      },
      {
        name: '圖像生成',
        tools: [
          { name: 'Midjourney', description: '頂級圖像生成',    trending: true },
          { name: 'DALL-E 3',   description: 'OpenAI 圖像',     trending: false },
          { name: 'Stable Diffusion', description: '開源本地',  free: true },
        ],
      },
      {
        name: 'Agent 框架',
        tools: [
          { name: 'LangChain',     description: 'Python agent 框架', free: true },
          { name: 'AutoGen',       description: 'Microsoft 多代理',  free: true },
          { name: 'CrewAI',        description: '角色分工代理',      free: true },
          { name: 'Claude Code',   description: 'Anthropic CLI',     trending: true },
        ],
      },
    ];
  }

  // ── Tab 切換 ────────────────────────────────────────────────────────────

  _bindTabs() {
    const tabs = this.el.querySelectorAll('.intel-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.activeTab = tab.dataset.tab;
        this._renderActive();
      });
    });
  }

  _bindRefresh() {
    const btn = this.el.querySelector('#intel-refresh-btn');
    btn?.addEventListener('click', async () => {
      btn.textContent = '更新中…';
      await fetch('/api/intel/refresh', { method: 'POST' });
      await this.refresh();
    });
  }

  _updateTimestamp() {
    const el = this.el.querySelector('#intel-last-updated');
    if (el) el.textContent = `最後更新：${new Date().toLocaleTimeString('zh-HK')}`;
  }

  // ── 工具 ──────────────────────────────────────────────────────────────────

  _fmtCtx(n) {
    if (!n) return '—';
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000)    return `${(n / 1000).toFixed(0)}K`;
    return String(n);
  }

  _timeAgo(ts) {
    if (!ts) return '—';
    const secs = Math.floor(Date.now() / 1000 - ts);
    if (secs < 60)    return '剛才';
    if (secs < 3600)  return `${Math.floor(secs / 60)} 分鐘前`;
    if (secs < 86400) return `${Math.floor(secs / 3600)} 小時前`;
    return `${Math.floor(secs / 86400)} 天前`;
  }
}

window.IntelPanel = IntelPanel;
