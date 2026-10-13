"""
Basalam Intelligence & Marketplace Analytics
Analyzes vendor trustworthiness, artisan product value, and store performance metrics.
"""

from typing import Any, Dict, List


def appraise_vendor(vendor: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate vendor trust score (0-100) based on ratings, review volume, and catalog size."""
    if "error" in vendor:
        return vendor

    name = vendor.get("name") or vendor.get("title", "")
    vendor_id = vendor.get("id", "")
    rating = float(vendor.get("rating") or vendor.get("score") or 0.0)
    reviews_count = int(vendor.get("total_reviews") or vendor.get("reviews_count") or 0)
    products_count = int(vendor.get("total_products") or vendor.get("products_count") or 0)

    # 1. Rating Factor (0 - 50)
    rating_score = min(50.0, (rating / 5.0) * 50.0)

    # 2. Social Proof & Reviews (0 - 30)
    if reviews_count >= 200:
        trust_score = 30.0
    elif reviews_count >= 50:
        trust_score = 24.0
    elif reviews_count >= 10:
        trust_score = 18.0
    elif reviews_count >= 1:
        trust_score = 10.0
    else:
        trust_score = 5.0

    # 3. Product Catalog Consistency (0 - 20)
    if products_count >= 50:
        catalog_score = 20.0
    elif products_count >= 15:
        catalog_score = 16.0
    elif products_count >= 3:
        catalog_score = 12.0
    else:
        catalog_score = 6.0

    total_score = round(min(100.0, rating_score + trust_score + catalog_score), 1)

    if total_score >= 85:
        verdict = "غرفه ممتاز و فوق‌العاده معتبر (Top Rated Artisan)"
        rec = "خرید از این غرفه با اطمینان کامل پیشنهاد می‌شود؛ میزان رضایت مشتریان بسیار بالاست."
    elif total_score >= 70:
        verdict = "غرفه معتبر و قابل اعتماد (Trusted Seller)"
        rec = "غرفه دارای سابقه مثبت و کیفیت تایید شده توسط خریداران است."
    elif total_score >= 50:
        verdict = "غرفه متوسط با سابقه رو به رشد"
        rec = "پیشنهاد می‌شود قبل از ثبت نهایی، از طریق بخش چت باسلام با غرفه‌دار درباره جزئیات هماهنگ فرمایید."
    else:
        verdict = "غرفه نوپا (New Vendor)"
        rec = "غرفه جدید است. توصیه می‌شود ابتدا یک سفارش کوچک ثبت نموده یا نظرات سایر محصولات را بررسی کنید."

    return {
        "vendor_id": vendor_id,
        "vendor_name": name,
        "trust_score": total_score,
        "satisfaction_percentage": f"{int(rating * 20)}%",
        "rating_out_of_5": rating,
        "total_reviews": reviews_count,
        "active_products": products_count,
        "verdict": verdict,
        "recommendation": rec,
    }


def deal_analysis(product: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze economic value and quality proposition of a Basalam product."""
    if "error" in product:
        return product

    title = product.get("title", "")
    prod_id = product.get("id", "")
    price = int(product.get("price") or 0)
    rating = float(product.get("rating") or 0.0)

    score = 70.0
    if rating >= 4.5:
        score += 15.0
    elif rating >= 4.0:
        score += 8.0

    if 0 < price <= 500000:
        score += 10.0
    elif price > 5000000:
        score -= 5.0

    final_score = round(min(100.0, max(10.0, score)), 1)

    return {
        "product_id": prod_id,
        "product_title": title,
        "price_text": product.get("price_text"),
        "value_score": final_score,
        "verdict": "ارزش خرید بالا (High Value Artisan Deal)" if final_score >= 80 else "ارزش متناسب با کیفیت بازار",
        "shopping_advice": "در بازار اجتماعی باسلام، خرید مستقیم از غرفه‌دار هزینه واسطه‌ها را حذف می‌کند و امکان گفتگوی آنلاین وجود دارد.",
    }
