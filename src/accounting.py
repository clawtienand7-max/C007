"""
TFNK™ 記帳整合模組（Accounting Module）— G8
整合現有 expense-tracker（C:\\Users\\User\\expense-tracker）
功能：拍照 OCR 抽取單據 → 自動記帳、分單、圖表分析
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from PIL import Image
import pytesseract

from src.config import get_settings
from src.screen_translate import ScreenTranslator

DATA_FILE = Path("memory/expenses.json")


class AccountingManager:
    """記帳管理器 — 整合 expense-tracker 功能"""

    def __init__(self):
        self.settings = get_settings()
        self.translator = ScreenTranslator()
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not DATA_FILE.exists():
            DATA_FILE.write_text(json.dumps({"expenses": [], "categories": [], "next_id": 1}))

    # ── 資料操作 ─────────────────────────────────────────────────────────────

    def _load(self) -> dict:
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"expenses": [], "categories": [], "next_id": 1}

    def _save(self, data: dict):
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_expenses(self, limit: int = 100, category: str = None,
                     date_from: str = None, date_to: str = None) -> list[dict]:
        data = self._load()
        exps = data["expenses"]
        if category:
            exps = [e for e in exps if e.get("category") == category]
        if date_from:
            exps = [e for e in exps if e.get("date", "") >= date_from]
        if date_to:
            exps = [e for e in exps if e.get("date", "") <= date_to]
        return sorted(exps, key=lambda x: x.get("date", ""), reverse=True)[:limit]

    def add_expense(self, amount: float, category: str, description: str,
                    date: str = None, currency: str = "HKD",
                    items: list[dict] = None, receipt_path: str = None) -> dict:
        data = self._load()
        exp = {
            "id":          data["next_id"],
            "amount":      round(amount, 2),
            "category":    category,
            "description": description,
            "date":        date or datetime.now().strftime("%Y-%m-%d"),
            "currency":    currency,
            "items":       items or [],
            "receipt_path":receipt_path,
            "created_at":  datetime.now().isoformat(),
        }
        data["expenses"].append(exp)
        data["next_id"] += 1
        if category and category not in data.get("categories", []):
            data.setdefault("categories", []).append(category)
        self._save(data)
        return exp

    def update_expense(self, expense_id: int, **updates) -> Optional[dict]:
        data = self._load()
        for exp in data["expenses"]:
            if exp["id"] == expense_id:
                exp.update(updates)
                self._save(data)
                return exp
        return None

    def delete_expense(self, expense_id: int) -> bool:
        data = self._load()
        before = len(data["expenses"])
        data["expenses"] = [e for e in data["expenses"] if e["id"] != expense_id]
        if len(data["expenses"]) < before:
            self._save(data)
            return True
        return False

    # ── 拍照 OCR 抽取單據 ────────────────────────────────────────────────────

    async def ocr_receipt(self, image_path: str) -> dict:
        """
        用 Tesseract OCR 識別收據，返回結構化資料
        支援中英文混排收據
        """
        img = Image.open(image_path).convert("RGB")
        # Try Traditional Chinese + English
        text = pytesseract.image_to_string(img, lang="chi_tra+eng")
        return self._parse_receipt_text(text, image_path)

    def _parse_receipt_text(self, text: str, image_path: str) -> dict:
        """從 OCR 文字提取收據資訊"""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        result = {
            "raw_text":     text,
            "image_path":   image_path,
            "items":        [],
            "total":        None,
            "date":         None,
            "merchant":     None,
            "currency":     "HKD",
        }

        # Detect currency
        if re.search(r'HK\$|港元|HKD', text):
            result["currency"] = "HKD"
        elif re.search(r'CNY|人民幣|¥(?![\d\s]*HK)', text):
            result["currency"] = "CNY"
        elif re.search(r'USD|\$(?!\s*HK)', text):
            result["currency"] = "USD"

        # Extract merchant (usually first line)
        if lines:
            result["merchant"] = lines[0]

        # Extract date
        date_patterns = [
            r'(\d{4}[-/]\d{2}[-/]\d{2})',
            r'(\d{2}[-/]\d{2}[-/]\d{4})',
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
        ]
        for pat in date_patterns:
            m = re.search(pat, text)
            if m:
                raw_date = m.group(1)
                # Normalize to YYYY-MM-DD
                raw_date = raw_date.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                result["date"] = raw_date
                break

        # Extract items and prices
        price_pattern = re.compile(r'(.{2,30}?)\s+[$HK$]*(\d+\.?\d{0,2})')
        for line in lines:
            m = price_pattern.search(line)
            if m and 'total' not in line.lower() and '合計' not in line and '總計' not in line:
                try:
                    price = float(m.group(2))
                    if 0 < price < 100000:
                        result["items"].append({
                            "name":   m.group(1).strip(),
                            "price":  price,
                            "selected": True,
                        })
                except ValueError:
                    pass

        # Extract total
        total_pattern = re.compile(r'(?:total|合計|總計|總額|TOTAL)[：:\s]*[$HK$]*(\d+\.?\d{0,2})', re.IGNORECASE)
        m = total_pattern.search(text)
        if m:
            result["total"] = float(m.group(1))
        elif result["items"]:
            result["total"] = round(sum(i["price"] for i in result["items"]), 2)

        return result

    async def auto_record_from_receipt(self, image_path: str, category: str = "餐飲") -> dict:
        """一鍵拍照→OCR→自動記帳"""
        receipt = await self.ocr_receipt(image_path)
        total = receipt.get("total") or sum(i["price"] for i in receipt.get("items", []) if i.get("selected"))
        description = receipt.get("merchant") or "收據"
        expense = self.add_expense(
            amount=total,
            category=category,
            description=description,
            date=receipt.get("date"),
            currency=receipt.get("currency", "HKD"),
            items=receipt.get("items"),
            receipt_path=image_path,
        )
        return {"expense": expense, "receipt": receipt}

    def split_bill(self, expense_id: int, selected_item_indices: list[int]) -> dict:
        """分單 — 只計算選中的項目"""
        data = self._load()
        exp = next((e for e in data["expenses"] if e["id"] == expense_id), None)
        if not exp:
            return {"error": "找不到記錄"}
        items = exp.get("items", [])
        selected_items = [items[i] for i in selected_item_indices if i < len(items)]
        subtotal = sum(i["price"] for i in selected_items)
        return {
            "expense_id":     expense_id,
            "selected_items": selected_items,
            "subtotal":       round(subtotal, 2),
            "currency":       exp.get("currency", "HKD"),
        }

    # ── 統計分析 ─────────────────────────────────────────────────────────────

    def get_summary(self, period: str = "month") -> dict:
        """取得支出摘要（today / week / month / year）"""
        now = datetime.now()
        if period == "today":
            date_from = now.strftime("%Y-%m-%d")
        elif period == "week":
            date_from = (now - __import__("datetime").timedelta(days=7)).strftime("%Y-%m-%d")
        elif period == "month":
            date_from = now.strftime("%Y-%m-01")
        else:  # year
            date_from = now.strftime("%Y-01-01")

        exps = self.get_expenses(limit=10000, date_from=date_from)
        total = sum(e["amount"] for e in exps)

        # By category
        by_cat: dict[str, float] = {}
        for e in exps:
            cat = e.get("category") or "其他"
            by_cat[cat] = round(by_cat.get(cat, 0) + e["amount"], 2)

        # By date
        by_date: dict[str, float] = {}
        for e in exps:
            d = e.get("date", "")[:10]
            by_date[d] = round(by_date.get(d, 0) + e["amount"], 2)

        return {
            "period":     period,
            "total":      round(total, 2),
            "count":      len(exps),
            "by_category":dict(sorted(by_cat.items(), key=lambda x: x[1], reverse=True)),
            "by_date":    dict(sorted(by_date.items())),
            "average":    round(total / len(exps), 2) if exps else 0,
            "top_expense":max(exps, key=lambda x: x["amount"]) if exps else None,
        }

    def get_categories(self) -> list[str]:
        data = self._load()
        default = ["餐飲", "交通", "購物", "娛樂", "醫療", "住宿", "工作", "其他"]
        saved = data.get("categories", [])
        return list(dict.fromkeys(default + saved))


_manager: Optional[AccountingManager] = None


def get_accounting_manager() -> AccountingManager:
    global _manager
    if _manager is None:
        _manager = AccountingManager()
    return _manager
