# TFNK™ Neural Agent Desktop

```
  ████████╗███████╗███╗   ██╗██╗  ██╗
  ╚══██╔══╝██╔════╝████╗  ██║██║ ██╔╝
     ██║   █████╗  ██╔██╗ ██║█████╔╝
     ██║   ██╔══╝  ██║╚██╗██║██╔═██╗
     ██║   ██║     ██║ ╚████║██║  ██╗
     ╚═╝   ╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═╝

  TFNK™  神經代理桌面  —  自主 AI 代理工作站
  版本 1.0.0  |  com.tfnk.app
```

---

## 什麼是 TFNK™？

**TFNK™** 是一個面向未來的自主 AI 代理桌面工作站。它將本地語言模型 (Ollama)、語音辨識 (faster-whisper)、工作流排程與 Tauri 原生桌面殼層整合成一個統一的操作環境。

核心特點：
- **自主代理執行** — 任務可在無人看守的情況下排程與繼續
- **本地優先** — 所有推論在本機執行，資料不離開您的電腦
- **跨平台原生殼層** — Tauri v1 包裝 WebView，輸出 `.msi` / `.exe`
- **系統托盤常駐** — 最小化到托盤，全域快捷鍵隨時喚醒
- **排程續傳** — 每 4.5 小時自動恢復待處理任務，跨越會話限制

---

## 架構概覽

```
┌───────────────────────────────────────────────────────────┐
│                    TFNK™ 桌面應用程式                      │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              Tauri Shell (Rust)                      │ │
│  │  • 系統托盤 / 全域快捷鍵 / 視窗管理                    │ │
│  │  • 單一實例保護 (OS mutex / lockfile)                 │ │
│  │  • 啟動 FastAPI sidecar 並自動重啟                    │ │
│  │  • 透過 tauri::event 與前端通訊                       │ │
│  └───────────────────┬──────────────────────────────────┘ │
│                      │ WebView (localhost:8000)            │
│  ┌───────────────────▼──────────────────────────────────┐ │
│  │           FastAPI Backend (Python)                   │ │
│  │  webui/server.py — REST API + 靜態前端               │ │
│  │  • 代理執行引擎 (agent_runtime.py)                    │ │
│  │  • Ollama LLM 整合                                    │ │
│  │  • faster-whisper 語音辨識                            │ │
│  │  • 任務佇列 (logs/task_queue.json)                    │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │           OS Scheduler (排程器)                      │ │
│  │  Windows: Task Scheduler  |  Linux/macOS: cron       │ │
│  │  每 4.5 小時執行 python -m tfnk.resume_tasks          │ │
│  └──────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘

外部依賴
  Ollama (:11434) ──── 本地 LLM 推論
  Tailscale ────────── 行動推播通知 (選用)
```

---

## 快速開始

### 1. 環境需求

| 工具 | 最低版本 |
|------|---------|
| Python | 3.11+ |
| Rust + Cargo | 1.70+ |
| Node.js | 18+ |
| Ollama | latest |
| Tauri CLI | 1.5.x |

### 2. 初始化設定

```bash
# 複製專案
git clone <repo-url> C007
cd C007

# 執行安裝腳本（建立 .env、安裝 Python 套件、建立目錄）
python scripts/setup.py
```

### 3. 啟動 FastAPI 伺服器

**Linux / macOS**
```bash
bash scripts/start.sh
```

**Windows**
```bat
scripts\start.bat
```

### 4. 啟動 Tauri 開發模式

```bash
cd tauri
npm install
npm run dev
```

### 5. 建置 Windows 安裝包

```bash
cd tauri
npm run build
# 輸出: tauri/src-tauri/target/release/bundle/msi/TFNK™_1.0.0_x64_en-US.msi
```

### 6. 設定排程器（跨會話續傳）

```bash
python scripts/scheduler_setup.py
```

---

## 全域快捷鍵

| 快捷鍵 | 動作 |
|--------|------|
| `Ctrl+Shift+T` | 顯示 / 隱藏視窗 |
| `Ctrl+Shift+S` | 緊急停止 (Emergency Stop) |

---

## 系統托盤選單

- **Show / Hide** — 切換視窗可見性
- **Emergency Stop** — 立即終止 FastAPI sidecar
- **Quit TFNK™** — 完整退出（含 sidecar）

---

## 目錄結構

```
C007/
├── tauri/                    # Tauri 殼層
│   ├── package.json
│   └── src-tauri/
│       ├── Cargo.toml
│       ├── build.rs
│       ├── tauri.conf.json
│       └── src/
│           └── main.rs       # Rust 主程式
├── webui/                    # FastAPI 後端
│   └── server.py
├── src/                      # Python 模組
│   ├── agent_runtime.py
│   ├── config.py
│   └── resume_tasks.py       # 排程續傳腳本
├── scripts/
│   ├── setup.py              # 初始化腳本
│   ├── start.sh              # Linux/macOS 啟動
│   ├── start.bat             # Windows 啟動
│   └── scheduler_setup.py    # OS 排程器設定
├── logs/                     # 執行日誌
├── memory/                   # 代理記憶持久化
├── skills/                   # 技能插件
├── backups/                  # 自動備份
├── requirements.txt
└── .env                      # 環境設定（不納入版控）
```

---

## 發展路線圖 (G0–G8)

```
G0  基礎架構    [完成] Tauri 殼層、FastAPI、系統托盤、排程器
G1  代理核心    [進行] LLM 對話、工具調用、記憶管理
G2  語音整合    [計畫] faster-whisper STT、TTS 回應
G3  技能系統    [計畫] 可熱載入技能插件 (skills/)
G4  多代理協作  [計畫] 代理間通訊協定 (MAS)
G5  知識庫      [計畫] 向量資料庫、長期記憶索引
G6  自動化工作流 [計畫] 視覺化流程編輯器
G7  行動同步    [計畫] Tailscale P2P、行動推播
G8  自主優化    [計畫] 代理自我改進、A/B 評估迴路
```

---

## 授權

MIT License — TFNK™ Team
