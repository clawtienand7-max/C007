/**
 * TFNK™ Splash Screen
 * components/splash.js
 *
 * Animated cyberpunk intro:
 * - Scanning lines sweep across
 * - Multiple rotating circles
 * - Matrix rain (CJK + Latin mix)
 * - "TFNK™" fades in large → shrinks to corner
 * - Status text sequence
 * - Loading bar with glow
 * Total: ~4 seconds
 */

'use strict';

class SplashScreen {
  constructor({ canvas, logo, status, bar, onComplete }) {
    this.canvas = canvas;
    this.logo = logo;
    this.statusEl = status;
    this.barEl = bar;
    this.onComplete = onComplete || (() => {});

    this.ctx = canvas.getContext('2d');
    this.running = false;
    this.startTime = 0;
    this.duration = 4200; // ms

    this.statusMessages = [
      '初始化系統...',
      '載入神經網絡...',
      '校準感知器...',
      '連接量子核心...',
      '就緒',
    ];

    // Matrix rain state
    this.matrixCols = [];
    this.circles = [];
    this.scanLines = [];

    this._initCircles();
    this._initScanLines();
  }

  _initCircles() {
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const defs = [
      { r: 80, speed: 0.8, cw: true, segments: 6, color: 'rgba(0,212,255,0.4)', dashed: [8, 4] },
      { r: 130, speed: -0.5, cw: false, segments: 4, color: 'rgba(0,212,255,0.25)', dashed: [3, 6] },
      { r: 190, speed: 0.3, cw: true, segments: 12, color: 'rgba(0,212,255,0.15)', dashed: [2, 8] },
      { r: 260, speed: -0.2, cw: false, segments: 8, color: 'rgba(0,212,255,0.08)', dashed: [] },
      { r: 340, speed: 0.12, cw: true, segments: 3, color: 'rgba(0,212,255,0.05)', dashed: [12, 6] },
    ];
    this.circles = defs.map(d => ({ ...d, cx, cy, angle: Math.random() * Math.PI * 2 }));
  }

  _initScanLines() {
    const h = window.innerHeight;
    for (let i = 0; i < 8; i++) {
      this.scanLines.push({
        y: Math.random() * h,
        speed: 1.5 + Math.random() * 2.5,
        width: 1 + Math.random() * 2,
        alpha: 0.3 + Math.random() * 0.4,
      });
    }
  }

  _initMatrix() {
    const w = window.innerWidth;
    const cellW = 16;
    const cols = Math.ceil(w / cellW);
    const h = window.innerHeight;

    this.matrixCols = [];
    for (let i = 0; i < cols; i++) {
      this.matrixCols.push({
        x: i * cellW,
        y: Math.random() * h,
        speed: 1 + Math.random() * 3,
        chars: [],
        len: 5 + Math.floor(Math.random() * 15),
      });
    }
  }

  _randomChar() {
    const sets = [
      '0123456789ABCDEF',
      'アイウエオカキクケコサシスセソタチツテトナニヌネノ',
      '初始化系統神經網絡感知器就緒載入校準量子核心',
      '!@#$%^&*()_+-=[]{}|;:,.<>?',
    ];
    const set = sets[Math.floor(Math.random() * sets.length)];
    return set[Math.floor(Math.random() * set.length)];
  }

  show() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
    this._initMatrix();
    this.running = true;
    this.startTime = performance.now();

    // Show logo with delay
    setTimeout(() => {
      if (this.logo) {
        this.logo.classList.add('visible');
      }
    }, 400);

    // Status text sequence
    const totalMsgs = this.statusMessages.length;
    const interval = (this.duration - 600) / totalMsgs;
    this.statusMessages.forEach((msg, i) => {
      setTimeout(() => {
        if (this.statusEl) this.statusEl.textContent = msg;
      }, 300 + i * interval);
    });

    // Loading bar
    this._animateBar();

    // Start animation loop
    this._loop();

    // End splash
    setTimeout(() => {
      this.running = false;
      this.onComplete();
    }, this.duration);
  }

  _animateBar() {
    if (!this.barEl) return;
    const start = performance.now();
    const dur = this.duration - 200;
    const tick = () => {
      const elapsed = performance.now() - start;
      const pct = Math.min(100, (elapsed / dur) * 100);
      // Ease: fast start, slow middle, burst at end
      const eased = pct < 80
        ? pct * 1.1
        : 88 + (pct - 80) * 0.6;
      this.barEl.style.width = Math.min(100, eased) + '%';
      if (elapsed < dur && this.running) requestAnimationFrame(tick);
      else this.barEl.style.width = '100%';
    };
    requestAnimationFrame(tick);
  }

  _loop() {
    if (!this.running) return;
    this._draw();
    requestAnimationFrame(() => this._loop());
  }

  _draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const elapsed = performance.now() - this.startTime;
    const t = elapsed / 1000; // seconds

    // Background
    ctx.fillStyle = 'rgba(0,0,15,0.2)';
    ctx.fillRect(0, 0, w, h);

    // ===== MATRIX RAIN =====
    ctx.font = 'bold 13px Rajdhani, monospace';
    ctx.textAlign = 'center';
    for (const col of this.matrixCols) {
      col.y += col.speed;
      if (col.y > h + col.len * 14) col.y = -col.len * 14;

      for (let j = 0; j < col.len; j++) {
        const cy = col.y - j * 14;
        if (cy < 0 || cy > h) continue;
        const alpha = (col.len - j) / col.len;
        const isHead = j === 0;
        if (isHead) ctx.fillStyle = 'rgba(200,255,255,0.9)';
        else ctx.fillStyle = `rgba(0,212,255,${alpha * 0.5})`;
        if (Math.random() < 0.05) {
          col.chars[j] = this._randomChar();
        }
        if (!col.chars[j]) col.chars[j] = this._randomChar();
        ctx.fillText(col.chars[j], col.x + 8, cy);
      }
    }

    // ===== SCAN LINES =====
    for (const sl of this.scanLines) {
      sl.y += sl.speed;
      if (sl.y > h) sl.y = 0;
      const grad = ctx.createLinearGradient(0, sl.y - 4, 0, sl.y + 4);
      grad.addColorStop(0, 'transparent');
      grad.addColorStop(0.5, `rgba(0,212,255,${sl.alpha})`);
      grad.addColorStop(1, 'transparent');
      ctx.fillStyle = grad;
      ctx.fillRect(0, sl.y - sl.width * 2, w, sl.width * 4);
    }

    // ===== ROTATING CIRCLES =====
    for (const c of this.circles) {
      c.angle += (c.cw ? 1 : -1) * c.speed * 0.01;

      ctx.save();
      ctx.translate(c.cx, c.cy);
      ctx.rotate(c.angle);

      ctx.strokeStyle = c.color;
      ctx.lineWidth = 1.5;

      if (c.dashed.length > 0) {
        ctx.setLineDash(c.dashed);
      } else {
        ctx.setLineDash([]);
      }

      // Main circle arc
      ctx.beginPath();
      ctx.arc(0, 0, c.r, 0, Math.PI * 2);
      ctx.stroke();

      // Segment markers
      for (let s = 0; s < c.segments; s++) {
        const a = (s / c.segments) * Math.PI * 2;
        const ix = Math.cos(a) * (c.r - 6);
        const iy = Math.sin(a) * (c.r - 6);
        const ox = Math.cos(a) * (c.r + 6);
        const oy = Math.sin(a) * (c.r + 6);
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(ix, iy);
        ctx.lineTo(ox, oy);
        ctx.stroke();

        // Glow dot at segment
        ctx.fillStyle = c.color;
        ctx.beginPath();
        ctx.arc(Math.cos(a) * c.r, Math.sin(a) * c.r, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.restore();
    }

    // ===== CENTER HUD RETICLE =====
    const cx = w / 2;
    const cy = h / 2;
    const pulse = 0.6 + Math.sin(t * 4) * 0.4;

    ctx.save();
    ctx.strokeStyle = `rgba(0,212,255,${pulse * 0.8})`;
    ctx.lineWidth = 1;
    ctx.setLineDash([]);

    // Cross hairs
    const crossSize = 30;
    ctx.beginPath();
    ctx.moveTo(cx - crossSize, cy); ctx.lineTo(cx - 10, cy);
    ctx.moveTo(cx + 10, cy); ctx.lineTo(cx + crossSize, cy);
    ctx.moveTo(cx, cy - crossSize); ctx.lineTo(cx, cy - 10);
    ctx.moveTo(cx, cy + 10); ctx.lineTo(cx, cy + crossSize);
    ctx.stroke();

    // Corner brackets around center
    const br = 60;
    const bl = 14;
    [[-1,-1],[1,-1],[1,1],[-1,1]].forEach(([sx, sy]) => {
      ctx.beginPath();
      ctx.moveTo(cx + sx * br, cy + sy * (br - bl));
      ctx.lineTo(cx + sx * br, cy + sy * br);
      ctx.lineTo(cx + sx * (br - bl), cy + sy * br);
      ctx.stroke();
    });
    ctx.restore();

    // ===== HORIZONTAL WIPE LINES =====
    const wipeAlpha = Math.max(0, Math.sin(t * 1.5) * 0.15);
    const wipeY = ((t * 0.3) % 1) * h;
    const wipeGrad = ctx.createLinearGradient(0, wipeY, w, wipeY);
    wipeGrad.addColorStop(0, 'transparent');
    wipeGrad.addColorStop(0.3, `rgba(0,212,255,${wipeAlpha})`);
    wipeGrad.addColorStop(0.5, `rgba(0,212,255,${wipeAlpha * 2})`);
    wipeGrad.addColorStop(0.7, `rgba(0,212,255,${wipeAlpha})`);
    wipeGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = wipeGrad;
    ctx.fillRect(0, wipeY - 1, w, 2);

    // ===== GRID OVERLAY =====
    ctx.strokeStyle = 'rgba(0,212,255,0.04)';
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    const gridSize = 48;
    for (let gx = 0; gx < w; gx += gridSize) {
      ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, h); ctx.stroke();
    }
    for (let gy = 0; gy < h; gy += gridSize) {
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke();
    }

    // ===== CORNER DATA READOUTS =====
    ctx.font = '10px Rajdhani, monospace';
    ctx.textAlign = 'left';
    ctx.fillStyle = 'rgba(0,212,255,0.4)';
    const time = new Date().toLocaleTimeString('zh-TW', { hour12: false });
    ctx.fillText(`SYS: ${time}`, 14, 24);
    ctx.fillText(`NODE: 0x${Math.floor(Math.random() * 0xFFFF).toString(16).toUpperCase().padStart(4,'0')}`, 14, 40);
    ctx.fillText(`STATUS: INIT`, 14, 56);

    ctx.textAlign = 'right';
    ctx.fillText(`BUILD: 20260603`, w - 14, 24);
    ctx.fillText(`VER: v4.2.1`, w - 14, 40);
    ctx.fillText(`MODE: BOOT`, w - 14, 56);
  }
}

window.SplashScreen = SplashScreen;
