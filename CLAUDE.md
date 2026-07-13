# C007 — TFNK™ Neural Agent Desktop App

> 呢份檔記低專案背景、進度同跨裝置同步流程,等任何裝置(手機 / 桌面 / 網頁)開新 session 都即刻有 context。

## 專案概覽

**TFNK™ Neural Agent Desktop App** — 一個桌面 AI agent 應用程式。

- 技術方向:**Electron + 前端框架**(可跨平台 Mac / Windows / Linux)
- Repo:`clawtienand7-max/C007`

## 路線圖(Roadmap）

| 代號 | 任務 | 狀態 |
|------|------|------|
| G1 | 建 TFNK™ 主使用介面 | ⬜ 未開始 |
| G2 | 建 TFNK™ Agent 核心 + 任務排程 | ⬜ 未開始 |
| G3 / G4 / G6 | 建設資資產:像素表情包 + 關聯圖 + 進階 viz | ⬜ 未開始 |
| G5 | 建情報中心:模型 / 代理比較 + 新聞 + 免費模型 | ⬜ 未開始 |
| G8 | 建財經 + 記帳 + 快捷提示詞 | ⬜ 未開始 |
| — | General coding session | ⬜ 進行中 |

> 更新狀態:每完成一個任務,改返上表嘅狀態(⬜ 未開始 / 🟡 進行中 / ✅ 完成),咁跨裝置接手就睇到進度。

## 跨裝置同步流程(重要)

本機 CLI session 嘅**對話記錄**只留喺本機,唔會上雲端;跨裝置靠 **GitHub 同步代碼**:

```
某裝置做嘢  →  git commit + git push 上 GitHub
                        ↓
另一裝置開「雲端 session」揀返同一個 repo 同分支  →  接住做
```

- 同步嘅係**代碼**,唔係**對話**。接手嘅 session 唔會記得之前嘅對話,但會睇到所有 push 咗嘅 code 同呢份 `CLAUDE.md`。
- 想交代背景 / 進度,就更新呢份 `CLAUDE.md` 或者寫清楚 commit message。

## 開發慣例

- 每次有實質進度就 commit + push,等其他裝置接得返。
- 完成功能後更新上面嘅路線圖狀態表。
