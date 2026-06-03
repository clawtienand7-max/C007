/**
 * TFNK™ Matrix Background
 * components/matrix-bg.js
 *
 * Two streams:
 *   - User commands: characters flow UPWARD (blue)
 *   - Agent activity: characters flow DOWNWARD (mode-color), new chars glow then fade
 */

'use strict';

class MatrixBackground {
  constructor({ canvas, mode = 'basic' }) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.mode = mode;
    this.modeColor = '#00D4FF';
    this.activity = 0.3;  // 0-1 density control

    // Character sets
    this.latinChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()[]{}<>/\\|_+-=:;';
    this.cjkStart = 0x4E00;
    this.cjkEnd = 0x9FFF;
    this.symbolChars = '※◆◇★☆▲△▼▽◉○●◎□■';
    this.katakana = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';

    // Column data
    this.cellW = 14;
    this.cellH = 16;
    this.cols = 0;
    this.downDrops = [];   // Agent stream — downward
    this.upDrops = [];     // User stream — upward

    // Injected text streams
    this.userTextQueue = [];
    this.agentTextQueue = [];

    this._resize();
    window.addEventListener('resize', () => this._resize());
    this._loop();
  }

  _resize() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
    this.cols = Math.ceil(this.canvas.width / this.cellW);

    // Reset drops
    this.downDrops = [];
    this.upDrops = [];
    for (let i = 0; i < this.cols; i++) {
      this.downDrops[i] = this._newDownDrop(i, true);
      this.upDrops[i] = this._newUpDrop(i, true);
    }
  }

  _newDownDrop(col, randomStart = false) {
    const h = this.canvas.height;
    const len = 8 + Math.floor(Math.random() * 16);
    return {
      col,
      y: randomStart ? Math.random() * h : -len * this.cellH,
      len,
      speed: 1.5 + Math.random() * 3 * this.activity,
      chars: Array.from({ length: len }, () => this._randomChar()),
      glowAge: Array(len).fill(0),
      active: Math.random() < this.activity,
      nextChange: 0,
    };
  }

  _newUpDrop(col, randomStart = false) {
    const h = this.canvas.height;
    const len = 5 + Math.floor(Math.random() * 10);
    return {
      col,
      y: randomStart ? Math.random() * h : h + len * this.cellH,
      len,
      speed: 0.8 + Math.random() * 1.5 * this.activity,
      chars: Array.from({ length: len }, () => this._randomChar(true)),
      active: Math.random() < (this.activity * 0.4),
    };
  }

  _randomChar(latinBias = false) {
    const r = Math.random();
    if (latinBias || r < 0.35) {
      return this.latinChars[Math.floor(Math.random() * this.latinChars.length)];
    } else if (r < 0.55) {
      return this.katakana[Math.floor(Math.random() * this.katakana.length)];
    } else if (r < 0.65) {
      return this.symbolChars[Math.floor(Math.random() * this.symbolChars.length)];
    } else {
      return String.fromCharCode(
        this.cjkStart + Math.floor(Math.random() * (this.cjkEnd - this.cjkStart))
      );
    }
  }

  setMode(mode, color) {
    this.mode = mode;
    this.modeColor = color;
  }

  setActivity(level) {
    this.activity = Math.max(0, Math.min(1, level));
    // Update speeds
    this.downDrops.forEach(d => {
      d.speed = 1.5 + Math.random() * 3 * this.activity;
      d.active = Math.random() < this.activity;
    });
    this.upDrops.forEach(u => {
      u.speed = 0.8 + Math.random() * 1.5 * this.activity;
      u.active = Math.random() < (this.activity * 0.4);
    });
  }

  addUserCommand(text) {
    // Inject text chars into upward stream
    const chars = text.toUpperCase().split('');
    this.userTextQueue.push(...chars);
    // Pick a random column to inject
    const col = Math.floor(Math.random() * this.cols);
    const drop = this.upDrops[col];
    if (drop) {
      drop.chars = chars.slice(0, drop.len);
      while (drop.chars.length < drop.len) drop.chars.push(this._randomChar(true));
      drop.active = true;
      drop.y = this.canvas.height + drop.len * this.cellH;
    }
  }

  addAgentActivity(text) {
    // Inject text chars into downward stream
    const chars = text.split('');
    const col = Math.floor(Math.random() * this.cols);
    const drop = this.downDrops[col];
    if (drop) {
      drop.chars = chars.slice(0, drop.len);
      while (drop.chars.length < drop.len) drop.chars.push(this._randomChar());
      drop.glowAge = Array(drop.len).fill(1); // Start glowing
      drop.active = true;
      drop.y = -drop.len * this.cellH;
    }
  }

  _hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return { r, g, b };
  }

  _colorWithAlpha(hex, alpha) {
    try {
      const { r, g, b } = this._hexToRgb(hex);
      return `rgba(${r},${g},${b},${alpha})`;
    } catch {
      return `rgba(0,212,255,${alpha})`;
    }
  }

  _draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const cw = this.cellW;
    const ch = this.cellH;

    // Fade effect
    ctx.fillStyle = 'rgba(0,0,0,0.08)';
    ctx.fillRect(0, 0, w, h);

    ctx.font = `bold ${ch - 2}px 'Rajdhani', monospace`;
    ctx.textAlign = 'center';

    const now = Date.now();
    const modeRgb = this._hexToRgb(this.modeColor || '#00D4FF');

    // ===== DOWNWARD STREAM (agent) =====
    for (let i = 0; i < this.downDrops.length; i++) {
      const d = this.downDrops[i];
      if (!d.active) {
        // Randomly activate based on activity
        if (Math.random() < 0.001 * this.activity) d.active = true;
        continue;
      }

      const x = i * cw + cw / 2;

      for (let j = 0; j < d.len; j++) {
        const cy = d.y + j * ch;
        if (cy < -ch || cy > h + ch) continue;

        const ratio = j / d.len;
        const isHead = j === d.len - 1;
        const glowAge = d.glowAge[j] || 0;

        let alpha, color;
        if (isHead) {
          // Bright head
          alpha = 1;
          color = `rgb(220,255,255)`;
        } else if (glowAge > 0) {
          // Glowing new char
          alpha = glowAge;
          color = `rgba(${modeRgb.r},${modeRgb.g},${modeRgb.b},${alpha})`;
          d.glowAge[j] = Math.max(0, glowAge - 0.02);
        } else {
          // Normal fade
          alpha = (1 - ratio) * 0.65;
          color = `rgba(${modeRgb.r},${modeRgb.g},${modeRgb.b},${alpha})`;
        }

        // Randomly mutate chars
        if (Math.random() < 0.01) {
          d.chars[j] = this._randomChar();
        }

        ctx.fillStyle = color;
        ctx.fillText(d.chars[j] || '', x, cy);
      }

      // Advance
      d.y += d.speed;

      // Reset when off screen
      if (d.y > h + d.len * ch) {
        Object.assign(d, this._newDownDrop(i, false));
        d.active = Math.random() < this.activity;
      }
    }

    // ===== UPWARD STREAM (user) =====
    for (let i = 0; i < this.upDrops.length; i++) {
      const u = this.upDrops[i];
      if (!u.active) {
        if (Math.random() < 0.0005 * this.activity) u.active = true;
        continue;
      }

      const x = i * cw + cw / 2;

      for (let j = 0; j < u.len; j++) {
        const cy = u.y - j * ch;
        if (cy < -ch || cy > h + ch) continue;

        const isHead = j === u.len - 1;
        const alpha = isHead ? 0.9 : ((u.len - j) / u.len) * 0.5;

        if (isHead) {
          ctx.fillStyle = 'rgba(180,240,255,0.9)';
        } else {
          ctx.fillStyle = `rgba(0,212,255,${alpha})`;
        }

        if (Math.random() < 0.008) u.chars[j] = this._randomChar(true);

        ctx.fillText(u.chars[j] || '', x, cy);
      }

      // Advance upward
      u.y -= u.speed;

      // Reset when off screen
      if (u.y < -u.len * ch) {
        Object.assign(u, this._newUpDrop(i, false));
        u.active = Math.random() < (this.activity * 0.4);
      }
    }
  }

  _loop() {
    this._draw();
    requestAnimationFrame(() => this._loop());
  }
}

// Attach to window
window.MatrixBackground = MatrixBackground;
