"""
Generate market analysis charts for NINJA 400 HK market.
Outputs PNG files to ./charts/ directory.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from analyzer import full_analysis

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

KAWASAKI_GREEN = "#00A550"
DARK = "#1A1A2E"
ACCENT = "#E94560"
LIGHT_BG = "#F5F5F5"

plt.rcParams.update({
    "figure.facecolor": LIGHT_BG,
    "axes.facecolor": "white",
    "axes.edgecolor": "#CCCCCC",
    "axes.labelcolor": DARK,
    "text.color": DARK,
    "xtick.color": DARK,
    "ytick.color": DARK,
    "font.family": "DejaVu Sans",
    "axes.grid": True,
    "grid.color": "#E0E0E0",
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
})

HKD_FMT = mticker.FuncFormatter(lambda x, _: f"HK${x:,.0f}")


def chart_price_trend(data: dict) -> str:
    trend = data["price_trend"]
    years = [t["year"] for t in trend]
    prices = [t["avg_price"] for t in trend]
    yoy = [t["yoy_change_pct"] for t in trend]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()

    ax1.plot(years, prices, "o-", color=KAWASAKI_GREEN, linewidth=2.5,
             markersize=8, label="平均叫價 Avg Ask Price")
    ax1.fill_between(years, prices, alpha=0.1, color=KAWASAKI_GREEN)
    ax1.yaxis.set_major_formatter(HKD_FMT)
    ax1.set_ylabel("平均叫價 (HK$)", color=KAWASAKI_GREEN)
    ax1.tick_params(axis="y", labelcolor=KAWASAKI_GREEN)

    yoy_safe = [v if v is not None else 0 for v in yoy]
    colors = [ACCENT if v < 0 else "#2196F3" for v in yoy_safe]
    ax2.bar([y + 0.3 for y in years], yoy_safe, width=0.4,
            color=colors, alpha=0.7, label="按年升跌 % YoY")
    ax2.axhline(0, color="#999", linewidth=0.8)
    ax2.set_ylabel("按年變動 % YoY", color=DARK)
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter())

    ax1.set_xticks(years)
    ax1.set_xlabel("年份")
    ax1.set_title("Kawasaki NINJA 400 香港二手市場 — 價格走勢 (2022–2026)", fontsize=13, pad=12)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "price_trend.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_by_year_avg(data: dict) -> str:
    by_year = data["by_year"]
    years = list(by_year.keys())
    avgs = [by_year[y]["avg"] for y in years]
    dep_pcts = [by_year[y]["depreciation_pct"] for y in years]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(years, avgs, color=KAWASAKI_GREEN, alpha=0.85, edgecolor="white", linewidth=1.2)

    ax.axhline(data["new_price_hkd"], color=ACCENT, linewidth=2,
               linestyle="--", label=f"新車價 HK${data['new_price_hkd']:,}")

    for bar, avg, dep in zip(bars, avgs, dep_pcts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 400,
                f"HK${avg:,}\n(-{dep}%)", ha="center", va="bottom", fontsize=8.5, color=DARK)

    ax.yaxis.set_major_formatter(HKD_FMT)
    ax.set_xlabel("出廠年份")
    ax.set_ylabel("平均二手叫價 (HK$)")
    ax.set_title("NINJA 400 各年份二手均價 vs 新車價", fontsize=13, pad=12)
    ax.legend()
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "by_year_avg.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_platform_distribution(data: dict) -> str:
    platforms = data["platforms"]["platforms"]
    names = list(platforms.keys())
    counts = [p["approx_listings"] for p in platforms.values()]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [KAWASAKI_GREEN, "#2196F3", "#FF9800", "#9C27B0", "#607D8B"]
    wedges, texts, autotexts = ax.pie(
        counts, labels=names, autopct="%1.0f%%",
        colors=colors[:len(names)], startangle=140,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
        textprops={"fontsize": 10},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")

    total = sum(counts)
    ax.set_title(
        f"NINJA 400 各平台刊登數量分佈\n(估算總計: ~{total} 架, 2026年5月)",
        fontsize=12, pad=15
    )
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "platform_distribution.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_depreciation_curve(data: dict) -> str:
    by_year = data["by_year"]
    years = sorted(by_year.keys())
    ages = [by_year[y]["age_years"] for y in years]
    retained = [by_year[y]["pct_of_new"] for y in years]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(ages, retained, "s-", color=KAWASAKI_GREEN, linewidth=2.5, markersize=9)
    ax.fill_between(ages, retained, alpha=0.12, color=KAWASAKI_GREEN)

    for age, pct, yr in zip(ages, retained, years):
        ax.annotate(f"{yr}年\n{pct}%", (age, pct),
                    textcoords="offset points", xytext=(6, 6), fontsize=8)

    ax.axhline(100, color=ACCENT, linestyle="--", linewidth=1.5, label="新車價基準 100%")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_xlabel("車齡 (年)")
    ax.set_ylabel("保值率 (% 相對新車價)")
    ax.set_title("NINJA 400 保值率曲線 (香港二手市場)", fontsize=13, pad=12)
    ax.legend()
    ax.set_ylim(0, 120)
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "depreciation_curve.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_all() -> list[str]:
    data = full_analysis()
    paths = [
        chart_price_trend(data),
        chart_by_year_avg(data),
        chart_platform_distribution(data),
        chart_depreciation_curve(data),
    ]
    print("Charts saved:")
    for p in paths:
        print(f"  {p}")
    return paths


if __name__ == "__main__":
    generate_all()
