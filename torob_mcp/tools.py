"""
Torob MCP Tools Definitions and Handlers
Exposes 17 tools for public e-commerce search, store comparison, price intelligence, and user accounts.
"""

from typing import Any, Dict, List
from .client import TorobClient
from .analytics import compare_stores, appraise_deal, analyze_price_trend

_client = TorobClient()

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "torob_search_products",
        "description": "جستجوی انواع محصولات، گوشی، لپ‌تاپ، لوازم خانگی و پوشاک در ترب با مقایسه لحظه‌ای قیمت فروشگاه‌ها",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "نام محصول یا مدل (مثلاً 'iPhone 13', 'لپ تاپ ایسوس', 'تلویزیون سامسونگ')"},
                "page": {"type": "integer", "description": "شماره صفحه (پیش‌فرض: 1)", "default": 1},
                "price_min": {"type": "integer", "description": "حداقل قیمت به تومان"},
                "price_max": {"type": "integer", "description": "حداکثر قیمت به تومان"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "torob_get_product_details",
        "description": "دریافت مشخصات کامل کالا و فهرست تمام فروشگاه‌های ارائه‌دهنده (با قیمت، گارانتی، امتیاز و لینک خرید)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prk": {"type": "string", "description": "شناسه محصول ترب (random_key یا prk مانند '13528091-f204-4f10-ba78-57143406a9a1')"},
            },
            "required": ["prk"],
        },
    },
    {
        "name": "torob_get_price_chart",
        "description": "دریافت نمودار و تاریخچه تغییرات قیمت کالا در طول روزها و ماه‌های گذشته",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prk": {"type": "string", "description": "شناسه محصول ترب (prk)"},
            },
            "required": ["prk"],
        },
    },
    {
        "name": "torob_price_trend_analysis",
        "description": "تحلیل هوشمند روند قیمت تاریخی کالا: بررسی روند نزولی یا صعودی و پیشنهاد بهترین زمان خرید",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prk": {"type": "string", "description": "شناسه محصول ترب (prk)"},
            },
            "required": ["prk"],
        },
    },
    {
        "name": "torob_compare_stores",
        "description": "مقایسه هوشمند فروشندگان کالا در ترب: شناسایی ارزان‌ترین فروشگاه، بالاترین امتیاز و پتانسیل صرفه‌جویی",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prk": {"type": "string", "description": "شناسه محصول ترب (prk)"},
            },
            "required": ["prk"],
        },
    },
    {
        "name": "torob_appraise_deal",
        "description": "ارزیابی و تحلیل هوشمند ارزش خرید کالا در ترب با نمره معامله (Deal Score از ۰ تا ۱۰۰)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prk": {"type": "string", "description": "شناسه محصول ترب (prk)"},
            },
            "required": ["prk"],
        },
    },
    {
        "name": "torob_get_special_offers",
        "description": "دریافت تخفیف‌های ویژه، شگفت‌انگیز و پیشنهادهای روز ترب با درصد تخفیف بالا",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "description": "شماره صفحه (پیش‌فرض: 1)", "default": 1},
            },
        },
    },
    {
        "name": "torob_get_suggestions",
        "description": "دریافت پیشنهادهای تکمیل خودکار کلمات جستجو (Autosuggest) از موتور ترب",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "عبارت جستجو برای پیشنهاد کلمات"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "torob_list_categories",
        "description": "فهرست دسته‌بندی‌های اصلی ترب (موبایل، لپ‌تاپ، لوازم خانگی، مد، ابزار، خودرو)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "torob_auth_send_otp",
        "description": "ارسال کد تایید پیامکی (OTP) برای ورود به حساب کاربری ترب",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "شماره همراه کاربر (مثلاً '09123456789')"},
            },
            "required": ["phone_number"],
        },
    },
    {
        "name": "torob_auth_verify_otp",
        "description": "تایید کد پیامکی و ذخیره توکن ورود ترب",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "شماره همراه"},
                "code": {"type": "string", "description": "کد ۵ رقمی دریافتی از پیامک"},
            },
            "required": ["phone_number", "code"],
        },
    },
    {
        "name": "torob_auth_set_token",
        "description": "تنظیم دستی توکن احراز هویت ترب جهت استفاده در نشست‌های بعدی",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "توکن معتبر کاربر ترب"},
            },
            "required": ["token"],
        },
    },
    {
        "name": "torob_auth_status",
        "description": "بررسی وضعیت لاگین و توکن فعال کاربر در ترب",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "torob_auth_logout",
        "description": "خروج از حساب کاربری و حذف توکن ذخیره شده ترب",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "torob_get_bookmarks",
        "description": "مشاهده کالاهای نشان‌شده (Bookmarks) کاربر در ترب (نیازمند لاگین)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "torob_status",
        "description": "بررسی وضعیت سرور و سلامت اتصال به ترب",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "torob_help",
        "description": "راهنمای کاربری و دستورات ابزارهای Torob MCP",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute a Torob tool call by name."""
    if name == "torob_search_products":
        return _client.search_products(
            query=args.get("query", ""),
            page=args.get("page", 1),
            price_min=args.get("price_min"),
            price_max=args.get("price_max"),
        )

    elif name == "torob_get_product_details":
        return _client.get_product_details(prk=args.get("prk", ""))

    elif name == "torob_get_price_chart":
        return _client.get_price_chart(prk=args.get("prk", ""))

    elif name == "torob_price_trend_analysis":
        chart_data = _client.get_price_chart(prk=args.get("prk", ""))
        return analyze_price_trend(chart_data)

    elif name == "torob_compare_stores":
        details = _client.get_product_details(prk=args.get("prk", ""))
        return compare_stores(details)

    elif name == "torob_appraise_deal":
        details = _client.get_product_details(prk=args.get("prk", ""))
        return appraise_deal(details)

    elif name == "torob_get_special_offers":
        return _client.get_special_offers(page=args.get("page", 1))

    elif name == "torob_get_suggestions":
        return _client.get_suggestions(query=args.get("query", ""))

    elif name == "torob_list_categories":
        return {"categories": _client.list_categories()}

    elif name == "torob_auth_send_otp":
        return _client.send_otp(phone_number=args.get("phone_number", ""))

    elif name == "torob_auth_verify_otp":
        return _client.verify_otp(phone_number=args.get("phone_number", ""), code=args.get("code", ""))

    elif name == "torob_auth_set_token":
        _client.set_token(token=args.get("token", ""))
        return {"status": "success", "message": "Torob token updated"}

    elif name == "torob_auth_status":
        return {
            "authenticated": bool(_client.token),
            "has_token": bool(_client.token),
            "token_preview": f"{_client.token[:6]}...{_client.token[-4:]}" if _client.token else None,
        }

    elif name == "torob_auth_logout":
        success = _client.logout()
        return {"status": "logged_out", "success": success}

    elif name == "torob_get_bookmarks":
        return _client.get_user_bookmarks()

    elif name == "torob_status":
        return {
            "service": "torob-mcp",
            "status": "operational",
            "version": "1.0.0",
            "tools_count": len(TOOLS),
            "routing_mode": "Direct + Cloudflare Edge Fallback",
        }

    elif name == "torob_help":
        return {
            "service": "Torob MCP Server",
            "description": "سامانه مقایسه قیمت و هوش بازار ترب (Torob)",
            "tools": [{"name": t["name"], "description": t["description"]} for t in TOOLS],
        }

    else:
        raise ValueError(f"Unknown tool: {name}")
