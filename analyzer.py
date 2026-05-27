"""
NINJA 400 HK Market Analyzer
Computes statistics and generates charts from collected listing data.
"""

import statistics
from collections import defaultdict
from market_data import (
    SAMPLE_LISTINGS,
    HISTORIC_AVG_PRICE,
    PLATFORM_COUNTS,
    NEW_PRICE_HKD,
    REFERENCE_DATE,
    TOTAL_ESTIMATED_LISTINGS,
)


def compute_stats(listings: list[tuple]) -> dict:
    prices = [p for _, p, *_ in listings if p]
    mileages = [m for _, _, m, *_ in listings if m]
    years = [y for y, *_ in listings if y]
    return {
        "count": len(listings),
        "price_avg": round(statistics.mean(prices)) if prices else None,
        "price_median": round(statistics.median(prices)) if prices else None,
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "price_stdev": round(statistics.stdev(prices)) if len(prices) > 1 else None,
        "mileage_avg": round(statistics.mean(mileages)) if mileages else None,
        "year_range": (min(years), max(years)) if years else None,
    }


def by_year_stats(listings: list[tuple]) -> dict:
    groups: dict[int, list[int]] = defaultdict(list)
    for year, price, *_ in listings:
        if year and price:
            groups[year].append(price)
    return {
        y: {
            "count": len(prices),
            "avg": round(statistics.mean(prices)),
            "min": min(prices),
            "max": max(prices),
        }
        for y, prices in sorted(groups.items())
    }


def depreciation_vs_new(year_stats: dict) -> dict:
    result = {}
    for year, stats in year_stats.items():
        age = REFERENCE_DATE.year - year
        pct_retained = round(stats["avg"] / NEW_PRICE_HKD * 100, 1)
        result[year] = {
            **stats,
            "age_years": age,
            "pct_of_new": pct_retained,
            "depreciation_pct": round(100 - pct_retained, 1),
        }
    return result


def platform_summary() -> dict:
    return {
        "platforms": PLATFORM_COUNTS,
        "total_estimated": TOTAL_ESTIMATED_LISTINGS,
    }


def price_trend_yoy() -> list[dict]:
    trend = []
    years = sorted(HISTORIC_AVG_PRICE.keys())
    for i, year in enumerate(years):
        data = HISTORIC_AVG_PRICE[year]
        prev = HISTORIC_AVG_PRICE[years[i - 1]]["avg"] if i > 0 else None
        yoy = round((data["avg"] - prev) / prev * 100, 1) if prev else None
        trend.append(
            {
                "year": year,
                "avg_price": data["avg"],
                "listings": data["count"],
                "yoy_change_pct": yoy,
                "note": data["note"],
            }
        )
    return trend


def full_analysis() -> dict:
    stats = compute_stats(SAMPLE_LISTINGS)
    year_stats = by_year_stats(SAMPLE_LISTINGS)
    dep = depreciation_vs_new(year_stats)
    platforms = platform_summary()
    trend = price_trend_yoy()

    return {
        "reference_date": str(REFERENCE_DATE),
        "new_price_hkd": NEW_PRICE_HKD,
        "overall_stats": stats,
        "by_year": dep,
        "price_trend": trend,
        "platforms": platforms,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(full_analysis(), ensure_ascii=False, indent=2))
