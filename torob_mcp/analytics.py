"""
Torob Intelligence & Market Analytics
Smart analysis engine for store comparison, deal appraisal, and price fluctuation tracking.
"""

from typing import Any, Dict, List


def compare_stores(details: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze and compare all available stores offering the product."""
    if "error" in details:
        return details

    prk = details.get("prk", "")
    title = details.get("title", "")
    sellers: List[Dict[str, Any]] = details.get("sellers") or []

    if not sellers:
        return {
            "prk": prk,
            "title": title,
            "total_stores": 0,
            "message": "هیچ فروشگاهی در حال حاضر این کالا را موجود ندارد.",
        }

    cheapest = sellers[0]
    most_expensive = sellers[-1]
    best_rated = max(sellers, key=lambda s: s.get("shop_score") or 0)

    price_diff = (most_expensive.get("price") or 0) - (cheapest.get("price") or 0)
    diff_percent = round((price_diff / cheapest["price"]) * 100, 1) if cheapest.get("price", 0) > 0 else 0

    return {
        "prk": prk,
        "product_title": title,
        "total_stores": len(sellers),
        "cheapest_store": {
            "shop_name": cheapest.get("shop_name"),
            "price": cheapest.get("price"),
            "price_text": cheapest.get("price_text"),
            "warranty": cheapest.get("warranty"),
            "city": cheapest.get("city"),
            "score": cheapest.get("shop_score"),
            "buy_url": cheapest.get("buy_url"),
        },
        "best_rated_store": {
            "shop_name": best_rated.get("shop_name"),
            "score": best_rated.get("shop_score"),
            "price": best_rated.get("price_text"),
            "buy_url": best_rated.get("buy_url"),
        },
        "price_summary": {
            "lowest": cheapest.get("price_text"),
            "highest": most_expensive.get("price_text"),
            "difference_toman": f"{price_diff:,} تومان",
            "savings_potential": f"{diff_percent}% اختلاف قیمت بین ارزان‌ترین و گران‌ترین فروشنده",
        },
        "top_sellers": sellers[:5],
    }


def appraise_deal(details: Dict[str, Any]) -> Dict[str, Any]:
    """Appraise the deal score (0-100) based on seller competition, price dispersion, and store ratings."""
    if "error" in details:
        return details

    prk = details.get("prk", "")
    title = details.get("title", "")
    sellers: List[Dict[str, Any]] = details.get("sellers") or []
    shops_count = len(sellers) or details.get("shops_count", 0)

    # 1. Competition Score (0 - 40)
    if shops_count >= 20:
        competition_score = 40.0
    elif shops_count >= 10:
        competition_score = 32.0
    elif shops_count >= 4:
        competition_score = 25.0
    elif shops_count >= 1:
        competition_score = 15.0
    else:
        competition_score = 5.0

    # 2. Price Dispersion & Savings Factor (0 - 40)
    transparency_score = 25.0
    if len(sellers) > 1 and sellers[0].get("price", 0) > 0:
        p_min = sellers[0]["price"]
        p_max = sellers[-1]["price"]
        spread = ((p_max - p_min) / p_min) * 100
        if spread >= 15:
            transparency_score = 40.0
        elif spread >= 5:
            transparency_score = 35.0

    # 3. Seller Reliability Score (0 - 20)
    scores = [s.get("shop_score") or 0 for s in sellers if s.get("shop_score")]
    avg_score = (sum(scores) / len(scores)) if scores else 3.5
    reliability_score = round(min(20.0, avg_score * 4.0), 1)

    total_score = round(min(100.0, competition_score + transparency_score + reliability_score), 1)

    if total_score >= 85:
        verdict = "High Savings Opportunity (تنوع فروشنده و اختلاف قیمت بالا - خرید به شدت به‌صرفه)"
        rec = "پیشنهاد می‌شود از ارزان‌ترین فروشنده با امتیاز بالا خرید نمایید."
    elif total_score >= 70:
        verdict = "Good Deal (خرید مطمئن و رقابتی)"
        rec = "قیمت بازار متعادل است. خرید از فروشندگان برتر پیشنهاد می‌شود."
    elif total_score >= 50:
        verdict = "Fair Deal (معامله معمولی)"
        rec = "تعداد فروشندگان محدود است. گارانتی و سابقه فروشگاه را بررسی فرمایید."
    else:
        verdict = "Limited Sellers (انحصار یا کمبود کالا در بازار)"
        rec = "با توجه به کم بودن فروشندگان، قیمت‌ها را با بازار حضوری نیز مقایسه فرمایید."

    return {
        "prk": prk,
        "title": title,
        "min_price": details.get("min_price_text"),
        "shops_count": shops_count,
        "deal_score": total_score,
        "verdict": verdict,
        "recommendation": rec,
    }


def analyze_price_trend(chart_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze historical price fluctuation trend from price chart data."""
    if "error" in chart_data:
        return chart_data

    prk = chart_data.get("prk", "")
    history = chart_data.get("history") or []

    if len(history) < 2:
        return {
            "prk": prk,
            "points": len(history),
            "trend": "Insufficient Data (داده‌های تاریخی کافی موجود نیست)",
            "recommendation": "تاریخچه تغییرات قیمت برای این محصول کم است.",
        }

    prices = [p.get("price") for p in history if p.get("price")]
    if not prices:
        return {"prk": prk, "error": "No price points available"}

    first_price = prices[0]
    last_price = prices[-1]
    min_price = min(prices)
    max_price = max(prices)

    change = last_price - first_price
    pct_change = round((change / first_price) * 100, 1) if first_price > 0 else 0

    if pct_change < -5:
        trend = "Downward Trend (روند نزولی - قیمت کاهش یافته است)"
        advice = "قیمت در حال حاضر نسبت به دوره‌های قبل پایین‌تر آمده و زمان مناسبی برای خرید است."
    elif pct_change > 5:
        trend = "Upward Trend (روند صعودی - قیمت افزایش یافته است)"
        advice = "قیمت اخیراً رو به رشد بوده است."
    else:
        trend = "Stable Trend (روند پایدار و کم‌نوسان)"
        advice = "نوسان قیمت در بازه زمانی اخیر ناچیز و پایدار بوده است."

    return {
        "prk": prk,
        "recorded_points": len(prices),
        "current_price": f"{last_price:,} تومان",
        "lowest_recorded": f"{min_price:,} تومان",
        "highest_recorded": f"{max_price:,} تومان",
        "net_change_percentage": f"{pct_change}%",
        "trend_assessment": trend,
        "advice": advice,
    }
