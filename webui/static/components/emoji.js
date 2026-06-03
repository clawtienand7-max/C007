/**
 * TFNK™ Pixel Art Emoji Engine
 * components/emoji.js
 *
 * 20 states, each drawn as 32x32 pixel art on canvas.
 * Cyberpunk/futuristic style with glowing eyes, circuit patterns.
 * Smooth interpolation between states + always-running blink.
 */

'use strict';

class EmojiEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.scale = canvas.width / 32; // canvas is 64x64, grid is 32x32
    this.currentState = 'idle';
    this.targetState = 'idle';
    this.transitionProgress = 1; // 0-1
    this.intensity = 0.8;  // 0-1 glow brightness
    this.blinkTimer = 0;
    this.blinkInterval = 3000 + Math.random() * 2000;
    this.isBlinking = false;
    this.blinkProgress = 0;
    this.lastTime = 0;
    this.animFrame = 0;

    this._loop();
  }

  // ===== STATE DEFINITIONS =====
  // Each pixel is defined as a 32-row array of strings
  // Characters: ' '=empty, '▓'=face, '█'=dark, 'O'=eye-glow, 'o'=eye-dim,
  //             'C'=circuit, '-'=line, '+'=node, '~'=accent, '*'=spark
  _getStatePixels(state) {
    const faces = {
      idle: [
        '                                ',
        '       ████████████████         ',
        '      ██████████████████        ',
        '     ████████████████████       ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████C+C█████████C+C█████    ',
        '    ████C O C███████C O C███    ',
        '    ████C+C█████████C+C█████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    █████────────────█████      ',
        '    ████ ──────────── ████      ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████~~~~~~~~~~~~~████████   ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ██████████████████████      ',
        '     ██████████████████         ',
        '      ████████████████          ',
        '       ████████████             ',
        '        C+─────+C               ',
        '        │       │               ',
        '        C       C               ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
      ],
      thinking: [
        '                                ',
        '       ████████████████         ',
        '      ██████████████████        ',
        '     ████████████████████       ',
        '    ████████████████████████    ',
        '    ████~~~~~████████~~~~~████  ',
        '    ████~███~████████~███~████  ',
        '    ████~█O█~████████~█O█~████  ',
        '    ████~███~████████~███~████  ',
        '    ████~~~~~████████~~~~~████  ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ ─ ─ ─ ─ ─ ─ ─ ████   ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████~███████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ██████████████████████      ',
        '     ████████████████████       ',
        '      ██████████████████        ',
        '       ████████████████         ',
        '              * *               ',
        '            *  *  *             ',
        '          *   ***   *           ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
      ],
      happy: [
        '                                ',
        '       ████████████████         ',
        '      ██████████████████        ',
        '     ████████████████████       ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ O █████████ O █████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ ┌──────────┐ ████      ',
        '    ████ │          │ ████      ',
        '    ████ └──────────┘ ████      ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    █████~~~~~~~~~~███████████  ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ██████████████████████      ',
        '     ██████████████████         ',
        '      ████████████████          ',
        '       ████████████             ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
      ],
      working: [
        '                                ',
        '       ████████████████         ',
        '      ██████████████████        ',
        '     ████████████████████       ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ > █████████ < █████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ ════════════ ████      ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ C─+─C─+─C─+─C ████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ██████████████████████      ',
        '     ██████████████████         ',
        '      ████████████████          ',
        '       ████████████             ',
        '        * C─────C *             ',
        '          │     │               ',
        '          * * * *               ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
      ],
      error: [
        '                                ',
        '    *   * *       * *   *       ',
        '       ████████████████         ',
        '      ██████████████████        ',
        '     ████████████████████       ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ X █████████ X █████    ',
        '    ████ X █████████ X █████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ ┌──────────┐ ████      ',
        '    ████ │!  ERROR !│ ████      ',
        '    ████ └──────────┘ ████      ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ██████████████████████      ',
        '     ██████████████████         ',
        '      ████████████████          ',
        '       ████████████             ',
        '    *   * *       * *   *       ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
      ],
      sleeping: [
        '                                ',
        '       ████████████████         ',
        '      ██████████████████        ',
        '     ████████████████████       ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ ─ █████████ ─ █████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ ──────────── ████      ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ██████████████████████      ',
        '     ██████████████████         ',
        '      ████████████████          ',
        '       ████████████             ',
        '                   z            ',
        '                 z              ',
        '               Z               ',
        '             Z                  ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
      ],
      excited: [
        '      * *             * *       ',
        '    *   *             *   *     ',
        '       ████████████████         ',
        '      ██████████████████        ',
        '     ████████████████████       ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ * █████████ * █████    ',
        '    ████ O █████████ O █████    ',
        '    ████ * █████████ * █████    ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    ████ ╔══════════╗ ████      ',
        '    ████ ║  ♦  ♦  ♦ ║ ████     ',
        '    ████ ╚══════════╝ ████      ',
        '    ████████████████████████    ',
        '    ████████████████████████    ',
        '    █████~~~~~~~~~~███████████  ',
        '    ████████████████████████    ',
        '    ██████████████████████      ',
        '     ██████████████████         ',
        '      ████████████████          ',
        '    *   *             *   *     ',
        '      * *             * *       ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
        '                                ',
      ],
    };

    // Return the face or default to idle
    return faces[state] || faces['idle'];
  }

  // ===== DRAWING =====
  _drawState(state, alpha = 1) {
    const ctx = this.ctx;
    const s = this.scale;
    const rows = this._getStatePixels(state);
    const now = Date.now();

    // Color palette based on state
    const stateColors = {
      idle:          { face: '#1A2744', eye: '#00D4FF', accent: '#0088AA', circuit: '#00FF88', spark: '#FFB800' },
      thinking:      { face: '#1A1A2E', eye: '#FF6B35', accent: '#AA4422', circuit: '#FFAA00', spark: '#FF6B35' },
      happy:         { face: '#0A1A2E', eye: '#00FF88', accent: '#007744', circuit: '#00D4FF', spark: '#FFFF00' },
      excited:       { face: '#1A0A2E', eye: '#FF88FF', accent: '#884488', circuit: '#FF6B35', spark: '#FFFFFF' },
      working:       { face: '#0A2E1A', eye: '#00D4FF', accent: '#004488', circuit: '#00FF88', spark: '#FFB800' },
      error:         { face: '#2E0A0A', eye: '#FF3355', accent: '#880022', circuit: '#FF6B35', spark: '#FFFFFF' },
      sleeping:      { face: '#0A0A1A', eye: '#334466', accent: '#112233', circuit: '#112244', spark: '#223355' },
      confused:      { face: '#1A1A0A', eye: '#FFAA00', accent: '#885500', circuit: '#FFAA00', spark: '#FF6B35' },
      laughing:      { face: '#0A1A0A', eye: '#00FF88', accent: '#008844', circuit: '#00D4FF', spark: '#FFFF00' },
      proud:         { face: '#1A0A1A', eye: '#FF88FF', accent: '#660066', circuit: '#00D4FF', spark: '#FFD700' },
      focused:       { face: '#0A1A2E', eye: '#00D4FF', accent: '#0044AA', circuit: '#00FF88', spark: '#00D4FF' },
      alert:         { face: '#2E1A0A', eye: '#FFB800', accent: '#AA6600', circuit: '#FF6B35', spark: '#FFB800' },
      curious:       { face: '#0A1A1A', eye: '#00FFFF', accent: '#006688', circuit: '#00FF88', spark: '#00FFFF' },
      sad:           { face: '#0A0A2E', eye: '#6688AA', accent: '#334466', circuit: '#334477', spark: '#6688AA' },
      angry:         { face: '#2E0A0A', eye: '#FF3355', accent: '#880022', circuit: '#FF6B35', spark: '#FF3355' },
      love:          { face: '#2E0A1A', eye: '#FF88CC', accent: '#880044', circuit: '#FF6B35', spark: '#FF88CC' },
      cool:          { face: '#0A1A2E', eye: '#00D4FF', accent: '#004488', circuit: '#00FF88', spark: '#FFFFFF' },
      nervous:       { face: '#1A1A0A', eye: '#FFAA00', accent: '#886600', circuit: '#FF6B35', spark: '#FFAA00' },
      success:       { face: '#0A2E0A', eye: '#00FF88', accent: '#008844', circuit: '#00D4FF', spark: '#FFFF00' },
      loading:       { face: '#0A0A2E', eye: '#00D4FF', accent: '#0044AA', circuit: '#00FF88', spark: '#00D4FF' },
    };

    const palette = stateColors[state] || stateColors['idle'];
    const glowStrength = this.intensity * alpha;

    // Blink offset
    const blinkScale = this.isBlinking ? Math.sin(this.blinkProgress * Math.PI) : 0;

    for (let row = 0; row < Math.min(rows.length, 32); row++) {
      const line = rows[row] || '';
      for (let col = 0; col < 32; col++) {
        const ch = line[col] || ' ';
        const px = col * s;
        const py = row * s;

        ctx.globalAlpha = alpha;

        switch (ch) {
          case '█':
          case '▓':
            ctx.fillStyle = palette.face;
            ctx.fillRect(px, py, s, s);
            break;

          case 'O': // Glowing eye
            if (blinkScale > 0.5) {
              ctx.fillStyle = palette.face;
              ctx.fillRect(px, py - blinkScale * s / 2, s, s * blinkScale);
            } else {
              ctx.fillStyle = palette.eye;
              ctx.fillRect(px, py, s, s);
              // Glow effect
              if (glowStrength > 0.3) {
                ctx.save();
                ctx.globalAlpha = glowStrength * alpha * 0.6;
                ctx.shadowColor = palette.eye;
                ctx.shadowBlur = 8 * s;
                ctx.fillStyle = palette.eye;
                ctx.fillRect(px - s * 0.5, py - s * 0.5, s * 2, s * 2);
                ctx.restore();
              }
            }
            break;

          case 'o': // Dim eye
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px, py, s, s);
            break;

          case '>': // Right eye (angry/surprised)
            ctx.fillStyle = palette.eye;
            ctx.fillRect(px, py + s * 0.3, s, s * 0.4);
            break;

          case '<': // Left eye (angry/surprised)
            ctx.fillStyle = palette.eye;
            ctx.fillRect(px, py + s * 0.3, s, s * 0.4);
            break;

          case 'X': // Error eye
            ctx.fillStyle = palette.eye;
            ctx.fillRect(px, py, s * 0.4, s * 0.4);
            ctx.fillRect(px + s * 0.6, py + s * 0.6, s * 0.4, s * 0.4);
            ctx.fillRect(px + s * 0.6, py, s * 0.4, s * 0.4);
            ctx.fillRect(px, py + s * 0.6, s * 0.4, s * 0.4);
            break;

          case '-': // Horizontal line / neutral mouth
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px, py + s * 0.4, s, s * 0.2);
            break;

          case '─': // Thin line
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px, py + s * 0.45, s, s * 0.1);
            break;

          case '═': // Double line
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px, py + s * 0.3, s, s * 0.15);
            ctx.fillRect(px, py + s * 0.55, s, s * 0.15);
            break;

          case '~': // Wave accent
          case '♦':
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px + s * 0.2, py + s * 0.3, s * 0.6, s * 0.4);
            break;

          case 'C': // Circuit node
          case '+':
            ctx.fillStyle = palette.circuit;
            ctx.fillRect(px + s * 0.3, py + s * 0.3, s * 0.4, s * 0.4);
            break;

          case '*': // Spark
            ctx.fillStyle = palette.spark;
            ctx.globalAlpha = alpha * (0.5 + Math.sin(now / 200 + row * 0.5) * 0.5);
            ctx.fillRect(px + s * 0.35, py + s * 0.35, s * 0.3, s * 0.3);
            ctx.globalAlpha = alpha;
            break;

          case 'z':
          case 'Z': // Sleep Z
            ctx.fillStyle = palette.accent;
            ctx.globalAlpha = alpha * 0.7;
            ctx.font = `bold ${Math.round(s * 0.8)}px Rajdhani`;
            ctx.textAlign = 'left';
            ctx.fillText(ch, px, py + s * 0.8);
            ctx.globalAlpha = alpha;
            break;

          case '│': // Vertical circuit line
            ctx.fillStyle = palette.circuit;
            ctx.fillRect(px + s * 0.45, py, s * 0.1, s);
            break;

          case '┌': case '┐': case '└': case '┘':
          case '╔': case '╗': case '╚': case '╝':
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px + s * 0.4, py + s * 0.4, s * 0.2, s * 0.2);
            break;

          case '║':
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px + s * 0.4, py, s * 0.2, s);
            break;

          case '│':
            ctx.fillStyle = palette.accent;
            ctx.fillRect(px + s * 0.45, py, s * 0.1, s);
            break;

          default:
            // space or unknown = transparent
            break;
        }
      }
    }

    // Reset
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;
  }

  // ===== STATE MACHINE =====
  setState(stateName) {
    if (stateName === this.currentState) return;
    this.targetState = stateName;
    this.transitionProgress = 0;
  }

  setEmotionIntensity(val) {
    this.intensity = Math.max(0, Math.min(1, val));
  }

  // ===== ANIMATION LOOP =====
  _loop() {
    const now = performance.now();
    const dt = now - (this.lastTime || now);
    this.lastTime = now;

    const ctx = this.ctx;
    const s = this.scale;
    const w = this.canvas.width;
    const h = this.canvas.height;

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = 'rgba(10,14,26,0.9)';
    ctx.fillRect(0, 0, w, h);

    // Corner circuit decorations
    this._drawCircuitCorners(ctx, s);

    // Handle transition
    if (this.transitionProgress < 1) {
      this.transitionProgress = Math.min(1, this.transitionProgress + dt / 200);
      // Cross-fade
      if (this.transitionProgress < 0.5) {
        this._drawState(this.currentState, 1 - this.transitionProgress * 2);
      } else {
        this._drawState(this.targetState, (this.transitionProgress - 0.5) * 2);
      }
      if (this.transitionProgress >= 1) {
        this.currentState = this.targetState;
      }
    } else {
      this._drawState(this.currentState, 1);
    }

    // Blink timer
    this.blinkTimer += dt;
    if (!this.isBlinking && this.blinkTimer > this.blinkInterval) {
      this.isBlinking = true;
      this.blinkTimer = 0;
      this.blinkInterval = 2500 + Math.random() * 3000;
    }
    if (this.isBlinking) {
      this.blinkProgress += dt / 120; // 120ms blink
      if (this.blinkProgress >= 1) {
        this.isBlinking = false;
        this.blinkProgress = 0;
      }
    }

    // Border glow
    const primary = this.currentState === 'error' ? '#FF3355'
                  : this.currentState === 'thinking' ? '#FF6B35'
                  : '#00D4FF';
    ctx.strokeStyle = primary;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.3 + Math.sin(now / 800) * 0.15;
    ctx.strokeRect(1, 1, w - 2, h - 2);
    ctx.globalAlpha = 1;

    requestAnimationFrame(() => this._loop());
  }

  _drawCircuitCorners(ctx, s) {
    const w = this.canvas.width;
    const h = this.canvas.height;
    const len = s * 3;
    ctx.strokeStyle = 'rgba(0,212,255,0.25)';
    ctx.lineWidth = 1;
    ctx.setLineDash([]);

    // Top-left
    ctx.beginPath();
    ctx.moveTo(2, 2 + len); ctx.lineTo(2, 2); ctx.lineTo(2 + len, 2);
    ctx.stroke();
    // Top-right
    ctx.beginPath();
    ctx.moveTo(w - 2 - len, 2); ctx.lineTo(w - 2, 2); ctx.lineTo(w - 2, 2 + len);
    ctx.stroke();
    // Bottom-left
    ctx.beginPath();
    ctx.moveTo(2, h - 2 - len); ctx.lineTo(2, h - 2); ctx.lineTo(2 + len, h - 2);
    ctx.stroke();
    // Bottom-right
    ctx.beginPath();
    ctx.moveTo(w - 2 - len, h - 2); ctx.lineTo(w - 2, h - 2); ctx.lineTo(w - 2, h - 2 - len);
    ctx.stroke();
  }
}

window.EmojiEngine = EmojiEngine;
