/**
 * TFNK™ 關聯圖面板（Relation Graph Panel）
 * Obsidian 風格 · D3 力導向 · 兩種視覺模式
 * 模式 A: 電路板/神經風格
 * 模式 B: 使用越多越亮
 */
class GraphPanel {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('panel-graph');
    this.canvas = this.el?.querySelector('#graph-canvas');
    this.svg = null;
    this.simulation = null;
    this.graphData = { nodes: [], links: [] };
    this.visualMode = 'circuit'; // 'circuit' | 'neural'
    this._init();
  }

  async _init() {
    if (!this.canvas) return;
    this._bindControls();
    await this.refresh();
    // Resize observer
    const ro = new ResizeObserver(() => this._resize());
    ro.observe(this.canvas.parentElement);
  }

  async refresh() {
    try {
      const resp = await fetch('/api/graph');
      this.graphData = await resp.json();
      this._render();
    } catch (e) {
      this.graphData = this._staticGraph();
      this._render();
    }
  }

  // ── 渲染（D3 force layout）─────────────────────────────────────────────

  _render() {
    if (typeof d3 === 'undefined') {
      this._renderFallback();
      return;
    }

    const parent = this.canvas.parentElement;
    const W = parent.clientWidth  || 400;
    const H = parent.clientHeight || 300;

    // Clear previous
    if (this.svg) this.svg.remove();
    if (this.simulation) this.simulation.stop();

    const svg = d3.select(parent).append('svg')
      .attr('width', W).attr('height', H)
      .style('position', 'absolute').style('top', 0).style('left', 0)
      .style('overflow', 'visible');
    this.svg = svg;

    // Defs: glow filter
    const defs = svg.append('defs');
    const filter = defs.append('filter').attr('id', 'glow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
    const feMerge = filter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Mode colors
    const modeColor = {
      basic: '#00D4FF', thinking: '#FF6B35', collaborative: '#00FF88',
    }[this.app.currentMode || 'basic'];

    const nodes = this.graphData.nodes.map(n => ({ ...n }));
    const links = this.graphData.links.map(l => ({ ...l }));

    // Link strength based on weight
    const link = svg.append('g').selectAll('line').data(links).enter().append('line')
      .attr('stroke', this.visualMode === 'circuit' ? '#1A3A55' : modeColor)
      .attr('stroke-width', d => Math.max(0.5, (d.weight || 1) * 1.5))
      .attr('stroke-opacity', d => Math.min(0.8, (d.weight || 0.3)))
      .attr('filter', this.visualMode === 'neural' ? 'url(#glow)' : null);

    // Circuit board connector style for 'circuit' mode
    if (this.visualMode === 'circuit') {
      link.attr('stroke-dasharray', d => d.type === 'skill' ? '4,2' : null);
    }

    // Node radius: bigger = used more
    const maxUsage = Math.max(1, ...nodes.map(n => n.usage || 1));
    const rScale = d3.scaleSqrt().domain([0, maxUsage]).range([4, 20]);

    // Node color
    const typeColors = {
      skill:    '#00D4FF', memory:  '#FF9500', task:    '#00FF88',
      model:    '#BF5FFF', concept: '#FF6B35', system:  '#80DEEA',
    };

    const node = svg.append('g').selectAll('g').data(nodes).enter().append('g')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) this.simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) this.simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    node.append('circle')
      .attr('r', d => rScale(d.usage || 1))
      .attr('fill', d => typeColors[d.type] || modeColor)
      .attr('fill-opacity', d => this.visualMode === 'neural' ? Math.min(1, 0.4 + (d.usage || 1) / maxUsage * 0.6) : 0.85)
      .attr('stroke', d => typeColors[d.type] || modeColor)
      .attr('stroke-width', 1.5)
      .attr('filter', d => (d.usage || 1) > maxUsage * 0.5 ? 'url(#glow)' : null);

    node.append('text')
      .text(d => d.label || d.id)
      .attr('dy', d => rScale(d.usage || 1) + 12)
      .attr('text-anchor', 'middle')
      .attr('fill', '#8AABB8')
      .attr('font-size', '10px')
      .attr('font-family', 'Rajdhani, sans-serif');

    // Circuit mode: extra decorations
    if (this.visualMode === 'circuit') {
      node.append('rect')
        .attr('x', d => -rScale(d.usage || 1) - 2)
        .attr('y', d => -rScale(d.usage || 1) - 2)
        .attr('width', d => (rScale(d.usage || 1) + 2) * 2)
        .attr('height', d => (rScale(d.usage || 1) + 2) * 2)
        .attr('fill', 'none')
        .attr('stroke', d => typeColors[d.type] || modeColor)
        .attr('stroke-width', 0.5)
        .attr('stroke-opacity', 0.4);
    }

    node.on('mouseover', (event, d) => this._showTooltip(event, d))
        .on('mouseout',  ()          => this._hideTooltip());

    // Force simulation
    this.simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(80).strength(0.5))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius(d => rScale(d.usage || 1) + 5))
      .on('tick', () => {
        link
          .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
  }

  _renderFallback() {
    const parent = this.canvas.parentElement;
    parent.innerHTML = '<div style="color:#556677;padding:20px;text-align:center">D3.js 未載入，關聯圖不可用</div>';
  }

  // ── 工具提示 ─────────────────────────────────────────────────────────────

  _showTooltip(event, d) {
    let tip = document.getElementById('graph-tooltip');
    if (!tip) {
      tip = document.createElement('div');
      tip.id = 'graph-tooltip';
      tip.className = 'graph-tooltip';
      document.body.appendChild(tip);
    }
    tip.innerHTML = `
      <div class="gt-label">${d.label || d.id}</div>
      <div class="gt-type">${d.type || '節點'}</div>
      ${d.usage ? `<div class="gt-usage">使用次數：${d.usage}</div>` : ''}
      ${d.description ? `<div class="gt-desc">${d.description}</div>` : ''}
    `;
    tip.style.left  = (event.pageX + 12) + 'px';
    tip.style.top   = (event.pageY - 10) + 'px';
    tip.style.display = 'block';
  }

  _hideTooltip() {
    const tip = document.getElementById('graph-tooltip');
    if (tip) tip.style.display = 'none';
  }

  // ── 控制項 ──────────────────────────────────────────────────────────────

  _bindControls() {
    const circuitBtn = this.el.querySelector('#graph-mode-circuit');
    const neuralBtn  = this.el.querySelector('#graph-mode-neural');
    const refreshBtn = this.el.querySelector('#graph-refresh-btn');

    circuitBtn?.addEventListener('click', () => {
      this.visualMode = 'circuit';
      circuitBtn.classList.add('active');
      neuralBtn?.classList.remove('active');
      this._render();
    });

    neuralBtn?.addEventListener('click', () => {
      this.visualMode = 'neural';
      neuralBtn.classList.add('active');
      circuitBtn?.classList.remove('active');
      this._render();
    });

    refreshBtn?.addEventListener('click', () => this.refresh());
  }

  _resize() {
    if (this.simulation) {
      this._render();
    }
  }

  // ── 靜態演示資料 ─────────────────────────────────────────────────────────

  _staticGraph() {
    return {
      nodes: [
        { id: 'tfnk',     label: 'TFNK™ 核心', type: 'system',  usage: 100 },
        { id: 'chat',     label: '對話',         type: 'skill',   usage: 80  },
        { id: 'voice',    label: '語音',         type: 'skill',   usage: 60  },
        { id: 'tasks',    label: '任務排程',     type: 'skill',   usage: 45  },
        { id: 'files',    label: '檔案管理',     type: 'skill',   usage: 35  },
        { id: 'search',   label: '網絡搜尋',     type: 'skill',   usage: 55  },
        { id: 'image',    label: '圖像生成',     type: 'skill',   usage: 30  },
        { id: 'finance',  label: '財經數據',     type: 'concept', usage: 20  },
        { id: 'memory',   label: '持久記憶',     type: 'memory',  usage: 70  },
        { id: 'claude',   label: 'Claude',       type: 'model',   usage: 90  },
        { id: 'ollama',   label: 'Ollama',       type: 'model',   usage: 50  },
        { id: 'skills',   label: '技能庫',       type: 'memory',  usage: 65  },
      ],
      links: [
        { source: 'tfnk',   target: 'chat',    weight: 3 },
        { source: 'tfnk',   target: 'voice',   weight: 2 },
        { source: 'tfnk',   target: 'tasks',   weight: 2 },
        { source: 'tfnk',   target: 'memory',  weight: 3 },
        { source: 'tfnk',   target: 'skills',  weight: 2 },
        { source: 'chat',   target: 'claude',  weight: 3 },
        { source: 'chat',   target: 'ollama',  weight: 2 },
        { source: 'chat',   target: 'voice',   weight: 1 },
        { source: 'tasks',  target: 'files',   weight: 2 },
        { source: 'tasks',  target: 'search',  weight: 2 },
        { source: 'skills', target: 'tasks',   weight: 2, type: 'skill' },
        { source: 'skills', target: 'chat',    weight: 2, type: 'skill' },
        { source: 'finance',target: 'search',  weight: 1 },
        { source: 'image',  target: 'tfnk',    weight: 1 },
      ],
    };
  }
}

window.GraphPanel = GraphPanel;
