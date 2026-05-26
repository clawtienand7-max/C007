"""
Generate a markdown + HTML market analysis report for NINJA 400 in HK.
"""

import os
import json
from datetime import date
from analyzer import full_analysis
from charts import generate_all

REPORT_DIR = os.path.dirname(__file__)


def fmt_hkd(v: int | None) -> str:
    return f"HK${v:,}" if v else "N/A"


def trend_arrow(pct: float | None) -> str:
    if pct is None:
        return "—"
    return f"▲ +{pct}%" if pct > 0 else f"▼ {pct}%"


def build_markdown(data: dict) -> str:
    stats = data["overall_stats"]
    trend = data["price_trend"]
    by_year = data["by_year"]
    platforms = data["platforms"]

    lines = [
        "# Kawasaki NINJA 400 香港二手市場分析報告",
        "",
        f"> **資料日期**: {data['reference_date']}  ",
        f"> **新車參考價**: {fmt_hkd(data['new_price_hkd'])}  ",
        f"> **數據來源**: 28car.com、JengCar、Carousell HK、BuyCar.hk",
        "",
        "---",
        "",
        "## 一、市場概況",
        "",
        f"| 指標 | 數值 |",
        f"|------|------|",
        f"| 各平台估算總刊登數 | **~{platforms['total_estimated']} 架** |",
        f"| 二手均價 | **{fmt_hkd(stats['price_avg'])}** |",
        f"| 二手中位價 | **{fmt_hkd(stats['price_median'])}** |",
        f"| 最低叫價 | {fmt_hkd(stats['price_min'])} |",
        f"| 最高叫價 | {fmt_hkd(stats['price_max'])} |",
        f"| 新車價 | {fmt_hkd(data['new_price_hkd'])} |",
        f"| 均價對新車折扣 | "
        f"**{round((1 - stats['price_avg']/data['new_price_hkd'])*100, 1)}% off** |",
        "",
        "---",
        "",
        "## 二、各平台刊登數量",
        "",
        "| 平台 | 估算刊登數 | 備註 |",
        "|------|-----------|------|",
    ]

    for name, info in platforms["platforms"].items():
        lines.append(f"| {name} | ~{info['approx_listings']} 架 | {info['note']} |")

    lines += [
        "",
        "> **注意**: 28car.com 對非香港 IP 實施存取限制，上述數字為跨平台公開數據估算。",
        "",
        "---",
        "",
        "## 三、成交價走勢 (2022–2026)",
        "",
        "| 年份 | 平均叫價 | 刊登量 | 按年變動 | 市場情況 |",
        "|------|---------|--------|---------|---------|",
    ]

    for t in trend:
        lines.append(
            f"| {t['year']} | {fmt_hkd(t['avg_price'])} | "
            f"{t['listings']} 架 | {trend_arrow(t['yoy_change_pct'])} | {t['note']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 四、各出廠年份二手均價 & 保值率",
        "",
        "| 出廠年份 | 車齡 | 均價 | 保值率 | 折舊率 |",
        "|---------|------|------|--------|--------|",
    ]

    for year, info in sorted(by_year.items()):
        lines.append(
            f"| {year} | {info['age_years']} 年 | {fmt_hkd(info['avg'])} | "
            f"{info['pct_of_new']}% | {info['depreciation_pct']}% |"
        )

    lines += [
        "",
        "---",
        "",
        "## 五、市場洞察",
        "",
        "### 保值率分析",
        "- NINJA 400 新車價 **HK$42,617**，二手市場均價約 **HK$40,600–41,000**",
        "- 2022 年出廠車款（車齡約 4 年）保值率仍達 **~95%**，相對同級別車款保值力較強",
        "- 每年折舊率約 **5–9%**，符合 400cc 運動電單車市場規律",
        "",
        "### 供需情況",
        "- 香港各平台合計約 **~41 架**在售，市場供應偏緊",
        "- 28car.com 為最大刊登平台，估算約 15 架",
        "- 近年刊登量由 2022 年約 8 架增至 2025 年約 22 架，供應逐漸寬鬆",
        "",
        "### 價格趨勢",
        "- 2022 年二手市場高峰均價約 **HK$52,000**（疫情後需求爆升）",
        "- 2023–2026 年價格持續回調，累計下跌約 **22%**",
        "- 2026 年均價已回落至約 **HK$40,600**，接近新車價水平",
        "- 未來趨勢：隨新車供應穩定，預期二手價格繼續溫和下調",
        "",
        "### 買家建議",
        "- **最佳性價比**: 2021–2022 年出廠，里數 8,000–15,000km，叫價 HK$38,000–45,000",
        "- **警惕高價**: 二手叫價若超過 HK$48,000，性價比不如購買新車",
        "- **議價空間**: 目前市場議價空間約 **5–10%**",
        "",
        "---",
        "",
        "## 六、圖表",
        "",
        "![價格走勢](charts/price_trend.png)",
        "![各年份均價](charts/by_year_avg.png)",
        "![平台分佈](charts/platform_distribution.png)",
        "![保值率曲線](charts/depreciation_curve.png)",
        "",
        "---",
        "",
        "*本報告由自動化工具整合公開平台數據生成，僅供參考。*  ",
        f"*生成日期: {date.today()}*",
    ]

    return "\n".join(lines)


def generate_report():
    print("Running analysis...")
    data = full_analysis()

    print("Generating charts...")
    generate_all()

    print("Building report...")
    md = build_markdown(data)

    md_path = os.path.join(REPORT_DIR, "NINJA400_HK_Market_Analysis.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved: {md_path}")

    json_path = os.path.join(REPORT_DIR, "ninja400_analysis_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Data saved: {json_path}")

    return md_path, json_path


if __name__ == "__main__":
    generate_report()
