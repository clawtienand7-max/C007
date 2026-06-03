"""
TFNK™ 快捷提示詞模組（Quick Prompt Templates）— G8
預設最佳提示詞樣板，分類：財經 / 圖形設計 / 影片設計+生成 / 程式編寫 / 除錯 / 資料蒐集
填表式、常用喺前、快捷鍵支援
"""
import json
from pathlib import Path
from typing import Optional

PROMPTS_FILE = Path("memory/custom_prompts.json")

# 內建提示詞樣板
BUILTIN_TEMPLATES = [
    # ── 財經 ───────────────────────────────────────────────────────────────
    {
        "id": "finance-analysis",
        "category": "財經",
        "name": "股票分析報告",
        "shortcut": "Ctrl+F1",
        "usage_count": 0,
        "fields": [
            {"key": "symbol",   "label": "股票代碼",   "placeholder": "AAPL / 0700.HK", "required": True},
            {"key": "period",   "label": "分析時段",   "placeholder": "1個月 / 1季 / 1年", "required": True},
            {"key": "focus",    "label": "分析重點",   "placeholder": "技術面 / 基本面 / 消息面", "required": False},
        ],
        "template": "請對股票 {symbol} 進行詳細分析，時段：{period}。{focus}。請用繁體中文回覆，包含：1) 近期走勢分析 2) 關鍵支撐/阻力位 3) 基本面概況 4) 風險提示 5) 操作建議。",
    },
    {
        "id": "finance-compare",
        "category": "財經",
        "name": "多股比較",
        "shortcut": "Ctrl+F2",
        "usage_count": 0,
        "fields": [
            {"key": "symbols",  "label": "股票代碼（逗號分隔）", "placeholder": "AAPL, MSFT, GOOGL", "required": True},
            {"key": "criteria", "label": "比較維度",             "placeholder": "市值 / PE / 成長率", "required": False},
        ],
        "template": "請比較以下股票：{symbols}。比較維度：{criteria}。用表格形式展示，最後給出綜合評級，繁體中文回覆。",
    },
    {
        "id": "finance-news",
        "category": "財經",
        "name": "財經新聞摘要",
        "shortcut": "Ctrl+F3",
        "usage_count": 0,
        "fields": [
            {"key": "topic", "label": "主題或公司", "placeholder": "加息 / 科技股 / 港股", "required": True},
            {"key": "days",  "label": "時間範圍",   "placeholder": "過去7天",               "required": False},
        ],
        "template": "請搜尋並摘要關於「{topic}」的最新財經新聞（{days}）。重點整理：1) 主要事件 2) 市場影響 3) 後市展望。繁體中文，精簡明確。",
    },

    # ── 程式編寫 ───────────────────────────────────────────────────────────
    {
        "id": "code-write",
        "category": "程式編寫",
        "name": "寫新功能",
        "shortcut": "Ctrl+C1",
        "usage_count": 0,
        "fields": [
            {"key": "language",    "label": "程式語言",   "placeholder": "Python / TypeScript / Rust", "required": True},
            {"key": "function",    "label": "功能描述",   "placeholder": "HTTP 客戶端，支援重試", "required": True},
            {"key": "constraints", "label": "限制/要求",  "placeholder": "無外部依賴 / 異步 / 有測試", "required": False},
        ],
        "template": "請用 {language} 撰寫以下功能：{function}。要求：{constraints}。請提供完整可運行的代碼，包含適當的錯誤處理。",
    },
    {
        "id": "code-refactor",
        "category": "程式編寫",
        "name": "重構代碼",
        "shortcut": "Ctrl+C2",
        "usage_count": 0,
        "fields": [
            {"key": "goal",    "label": "重構目標", "placeholder": "提升性能 / 增加可讀性 / 減少重複", "required": True},
            {"key": "context", "label": "背景說明", "placeholder": "這段代碼用於…",                    "required": False},
        ],
        "template": "請重構以下代碼，目標：{goal}。背景：{context}。請解釋每個改動的原因，並保持功能不變。",
    },

    # ── 除錯 ───────────────────────────────────────────────────────────────
    {
        "id": "debug-error",
        "category": "除錯",
        "name": "分析錯誤訊息",
        "shortcut": "Ctrl+D1",
        "usage_count": 0,
        "fields": [
            {"key": "error",    "label": "錯誤訊息/Stack Trace", "placeholder": "貼上完整錯誤…", "required": True, "multiline": True},
            {"key": "context",  "label": "發生情境",             "placeholder": "當我執行…時出現", "required": False},
            {"key": "language", "label": "程式語言/框架",        "placeholder": "Python 3.11 / FastAPI", "required": False},
        ],
        "template": "請分析以下錯誤：\n```\n{error}\n```\n發生情境：{context}\n語言/框架：{language}\n請：1) 解釋錯誤原因 2) 提供修復方案 3) 說明如何預防。",
    },
    {
        "id": "debug-perf",
        "category": "除錯",
        "name": "性能優化分析",
        "shortcut": "Ctrl+D2",
        "usage_count": 0,
        "fields": [
            {"key": "bottleneck", "label": "慢點描述",    "placeholder": "API 回應慢 / 記憶體洩漏", "required": True},
            {"key": "metrics",    "label": "性能指標",    "placeholder": "回應時間 500ms，CPU 90%",  "required": False},
        ],
        "template": "請幫我分析以下性能問題：{bottleneck}。當前指標：{metrics}。請提供：1) 可能原因 2) 診斷步驟 3) 優化方案，從最高影響的開始。",
    },

    # ── 圖形設計 ───────────────────────────────────────────────────────────
    {
        "id": "design-prompt",
        "category": "圖形設計",
        "name": "圖像生成提示詞",
        "shortcut": "Ctrl+G1",
        "usage_count": 0,
        "fields": [
            {"key": "subject",  "label": "主題/內容",   "placeholder": "賽博朋克城市夜景", "required": True},
            {"key": "style",    "label": "風格",         "placeholder": "超現實主義 / 8-bit / 水墨", "required": False},
            {"key": "mood",     "label": "氛圍/情感",   "placeholder": "神秘 / 活潑 / 史詩感", "required": False},
            {"key": "ratio",    "label": "畫面比例",    "placeholder": "16:9 / 1:1 / 9:16", "required": False},
        ],
        "template": "請為我生成一個高質量的圖像提示詞（prompt），主題：{subject}，風格：{style}，氛圍：{mood}，比例：{ratio}。請同時提供英文版（用於 Midjourney/DALL-E）和描述說明。",
    },
    {
        "id": "design-ui",
        "category": "圖形設計",
        "name": "UI 設計建議",
        "shortcut": "Ctrl+G2",
        "usage_count": 0,
        "fields": [
            {"key": "component", "label": "UI 元件",     "placeholder": "登入頁 / 數據儀表盤 / 導航欄", "required": True},
            {"key": "style",     "label": "設計風格",    "placeholder": "賽博朋克 / 極簡 / Material", "required": False},
            {"key": "platform",  "label": "平台",         "placeholder": "桌面 / 手機 / 平板", "required": False},
        ],
        "template": "請為以下 UI 元件提供詳細設計建議：{component}。風格：{style}，平台：{platform}。包含：顏色方案、佈局建議、互動動效、可訪問性考慮。如可能請提供 CSS/Tailwind 代碼範例。",
    },

    # ── 影片設計+生成 ──────────────────────────────────────────────────────
    {
        "id": "video-script",
        "category": "影片設計",
        "name": "影片腳本",
        "shortcut": "Ctrl+V1",
        "usage_count": 0,
        "fields": [
            {"key": "topic",    "label": "影片主題", "placeholder": "AI 技術教程", "required": True},
            {"key": "duration", "label": "時長",     "placeholder": "60秒 / 5分鐘", "required": True},
            {"key": "platform", "label": "平台",     "placeholder": "YouTube / TikTok / Instagram", "required": True},
            {"key": "tone",     "label": "語氣風格", "placeholder": "專業 / 輕鬆 / 幽默", "required": False},
        ],
        "template": "請為以下影片撰寫完整腳本：主題「{topic}」，時長 {duration}，平台 {platform}，語氣 {tone}。包含：開場白（吸引注意）、主要內容（分段）、CTA（行動呼籲）、旁白文字及畫面建議。",
    },

    # ── 資料蒐集 ───────────────────────────────────────────────────────────
    {
        "id": "research-topic",
        "category": "資料蒐集",
        "name": "主題深入研究",
        "shortcut": "Ctrl+R1",
        "usage_count": 0,
        "fields": [
            {"key": "topic",   "label": "研究主題",     "placeholder": "量子計算的商業應用", "required": True},
            {"key": "depth",   "label": "深度",         "placeholder": "概覽 / 中等 / 深入", "required": False},
            {"key": "format",  "label": "輸出格式",     "placeholder": "報告 / 條列 / 思維導圖", "required": False},
            {"key": "sources", "label": "資料來源偏好", "placeholder": "學術 / 新聞 / 官方文件", "required": False},
        ],
        "template": "請對「{topic}」進行{depth}研究，優先參考{sources}資料。以{format}格式輸出，繁體中文。包含：1) 背景概述 2) 最新發展 3) 關鍵數據 4) 主要挑戰 5) 未來趨勢。",
    },
    {
        "id": "research-compare",
        "category": "資料蒐集",
        "name": "產品/服務比較",
        "shortcut": "Ctrl+R2",
        "usage_count": 0,
        "fields": [
            {"key": "items",    "label": "比較對象（逗號分隔）", "placeholder": "ChatGPT, Claude, Gemini", "required": True},
            {"key": "criteria", "label": "比較維度",             "placeholder": "功能 / 價格 / 易用性",  "required": False},
            {"key": "usecase",  "label": "使用場景",             "placeholder": "程式開發 / 寫作 / 分析", "required": False},
        ],
        "template": "請比較以下產品/服務：{items}。比較維度：{criteria}。使用場景：{usecase}。用表格形式展示優缺點，最後給出針對不同需求的推薦建議。繁體中文。",
    },
]


class PromptsManager:
    """快捷提示詞管理器"""

    def __init__(self):
        PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not PROMPTS_FILE.exists():
            PROMPTS_FILE.write_text(json.dumps({"custom": []}, ensure_ascii=False))

    def _load_custom(self) -> list[dict]:
        try:
            return json.loads(PROMPTS_FILE.read_text(encoding="utf-8")).get("custom", [])
        except Exception:
            return []

    def _save_custom(self, custom: list[dict]):
        PROMPTS_FILE.write_text(
            json.dumps({"custom": custom}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_all(self, category: str = None) -> list[dict]:
        """取得所有提示詞樣板（內建 + 自定義），按使用次數排序"""
        all_templates = BUILTIN_TEMPLATES + self._load_custom()
        if category:
            all_templates = [t for t in all_templates if t.get("category") == category]
        return sorted(all_templates, key=lambda x: x.get("usage_count", 0), reverse=True)

    def get_categories(self) -> list[str]:
        """取得所有分類"""
        cats = list(dict.fromkeys(t["category"] for t in BUILTIN_TEMPLATES + self._load_custom()))
        return cats

    def get_by_id(self, template_id: str) -> Optional[dict]:
        all_t = BUILTIN_TEMPLATES + self._load_custom()
        return next((t for t in all_t if t["id"] == template_id), None)

    def render(self, template_id: str, values: dict[str, str]) -> str:
        """渲染提示詞（替換佔位符）"""
        tmpl = self.get_by_id(template_id)
        if not tmpl:
            raise ValueError(f"找不到樣板：{template_id}")
        text = tmpl["template"]
        for k, v in values.items():
            text = text.replace(f"{{{k}}}", v)
        # Increment usage count
        self._increment_usage(template_id)
        return text

    def _increment_usage(self, template_id: str):
        # For builtins, update in-memory (won't persist across restarts)
        for t in BUILTIN_TEMPLATES:
            if t["id"] == template_id:
                t["usage_count"] = t.get("usage_count", 0) + 1
                return
        # For custom, persist
        custom = self._load_custom()
        for t in custom:
            if t["id"] == template_id:
                t["usage_count"] = t.get("usage_count", 0) + 1
        self._save_custom(custom)

    def add_custom(self, template: dict) -> dict:
        """新增自定義提示詞樣板"""
        custom = self._load_custom()
        if not template.get("id"):
            template["id"] = f"custom-{len(custom) + 1}"
        template.setdefault("usage_count", 0)
        template.setdefault("category", "自定義")
        custom.append(template)
        self._save_custom(custom)
        return template

    def delete_custom(self, template_id: str) -> bool:
        custom = self._load_custom()
        before = len(custom)
        custom = [t for t in custom if t["id"] != template_id]
        if len(custom) < before:
            self._save_custom(custom)
            return True
        return False

    def search(self, query: str) -> list[dict]:
        """搜尋提示詞"""
        q = query.lower()
        return [
            t for t in self.get_all()
            if q in t["name"].lower()
            or q in t.get("category", "").lower()
            or q in t.get("template", "").lower()
        ]


_manager: Optional[PromptsManager] = None


def get_prompts_manager() -> PromptsManager:
    global _manager
    if _manager is None:
        _manager = PromptsManager()
    return _manager
