"""
Basalam MCP Tools Definitions and Handlers
Exposes 18 comprehensive tools for artisan commerce, vendor appraisals, and customer interactions.
"""

from typing import Any, Dict, List
from .client import BasalamClient
from .analytics import appraise_vendor, deal_analysis

_client = BasalamClient()

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "basalam_search_products",
        "description": "جستجوی محصولات، خوراکی‌ها، صنایع دستی، پوشاک و تولیدات خانگی در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "نام محصول یا عبارت جستجو (مثلاً 'زعفران', 'عسل طبیعی', 'کیف چرم')"},
                "page": {"type": "integer", "description": "شماره صفحه (پیش‌فرض: 1)", "default": 1},
                "price_min": {"type": "integer", "description": "حداقل قیمت به تومان"},
                "price_max": {"type": "integer", "description": "حداکثر قیمت به تومان"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "basalam_get_product_details",
        "description": "دریافت جزئیات کامل محصول، قیمت، مشخصات، موجودی و اطلاعات غرفه‌دار در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "شناسه محصول باسلام"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "basalam_get_vendor_details",
        "description": "دریافت اطلاعات غرفه، رضایت مشتریان، تعداد کالاها و سابقه فروشنده در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "شناسه یا نام کاربری غرفه"},
            },
            "required": ["vendor_id"],
        },
    },
    {
        "name": "basalam_get_vendor_products",
        "description": "مشاهده تمام کالاهای ارائه‌شده توسط یک غرفه خاص در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "شناسه غرفه"},
                "page": {"type": "integer", "description": "شماره صفحه (پیش‌فرض: 1)", "default": 1},
            },
            "required": ["vendor_id"],
        },
    },
    {
        "name": "basalam_get_similar_products",
        "description": "دریافت کالاهای مشابه و پیشنهادی بر اساس سیستم هوش مصنوعی باسلام (More Like This)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "شناسه محصول"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "basalam_get_popular_searches",
        "description": "مشاهده کلمات و محصولات پرجستجو و ترند در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "basalam_get_product_reviews",
        "description": "دریافت نظرات و بازخوردهای خریداران درباره یک محصول در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "شناسه محصول"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "basalam_get_product_questions",
        "description": "مشاهده پرسش‌ها و پاسخ‌های ثبت‌شده برای یک کالا در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "شناسه محصول"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "basalam_appraise_vendor",
        "description": "ارزیابی و نمره‌دهی هوشمند به اعتبار و رضایت مشتریان غرفه در باسلام (Trust Score)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "شناسه یا نام غرفه"},
            },
            "required": ["vendor_id"],
        },
    },
    {
        "name": "basalam_deal_analysis",
        "description": "تحلیل هوشمند ارزش خرید و ارزیابی اقتصادی محصول در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "شناسه محصول"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "basalam_list_categories",
        "description": "فهرست دسته‌بندی‌های اصلی بازار باسلام (مواد غذایی، صنایع دستی، پوشاک و...)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "basalam_auth_send_otp",
        "description": "ارسال کد پیامکی یکبار مصرف (OTP) برای ورود به حساب باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "شماره همراه کاربر"},
            },
            "required": ["phone_number"],
        },
    },
    {
        "name": "basalam_auth_verify_otp",
        "description": "تایید کد پیامکی و ذخیره توکن ورود به باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "شماره همراه"},
                "code": {"type": "string", "description": "کد دریافتی از پیامک"},
            },
            "required": ["phone_number", "code"],
        },
    },
    {
        "name": "basalam_auth_set_token",
        "description": "تنظیم دستی توکن احراز هویت باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "توکن معتبر کاربر باسلام"},
            },
            "required": ["token"],
        },
    },
    {
        "name": "basalam_auth_status",
        "description": "بررسی وضعیت لاگین و نشست فعال کاربر در باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "basalam_auth_logout",
        "description": "خروج از حساب کاربری و پاکسازی توکن باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "basalam_status",
        "description": "بررسی وضعیت سرور و سلامت اتصال به باسلام",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "basalam_help",
        "description": "راهنمای کاربری و دستورات ابزارهای Basalam MCP",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute Basalam tool call."""
    if name == "basalam_search_products":
        return _client.search_products(
            query=args.get("query", ""),
            page=args.get("page", 1),
            price_min=args.get("price_min"),
            price_max=args.get("price_max"),
        )

    elif name == "basalam_get_product_details":
        return _client.get_product_details(product_id=args.get("product_id", ""))

    elif name == "basalam_get_vendor_details":
        return _client.get_vendor_details(vendor_id=args.get("vendor_id", ""))

    elif name == "basalam_get_vendor_products":
        return _client.get_vendor_products(vendor_id=args.get("vendor_id", ""), page=args.get("page", 1))

    elif name == "basalam_get_similar_products":
        return _client.get_similar_products(product_id=args.get("product_id", ""))

    elif name == "basalam_get_popular_searches":
        return _client.get_popular_searches()

    elif name == "basalam_get_product_reviews":
        return _client.get_product_reviews(product_id=args.get("product_id", ""))

    elif name == "basalam_get_product_questions":
        return _client.get_product_questions(product_id=args.get("product_id", ""))

    elif name == "basalam_appraise_vendor":
        v = _client.get_vendor_details(vendor_id=args.get("vendor_id", ""))
        return appraise_vendor(v)

    elif name == "basalam_deal_analysis":
        p = _client.get_product_details(product_id=args.get("product_id", ""))
        return deal_analysis(p)

    elif name == "basalam_list_categories":
        return {"categories": _client.list_categories()}

    elif name == "basalam_auth_send_otp":
        return _client.send_otp(phone_number=args.get("phone_number", ""))

    elif name == "basalam_auth_verify_otp":
        return _client.verify_otp(phone_number=args.get("phone_number", ""), code=args.get("code", ""))

    elif name == "basalam_auth_set_token":
        _client.set_token(token=args.get("token", ""))
        return {"status": "success", "message": "Basalam token updated"}

    elif name == "basalam_auth_status":
        return {
            "authenticated": bool(_client.token),
            "has_token": bool(_client.token),
            "token_preview": f"{_client.token[:6]}...{_client.token[-4:]}" if _client.token else None,
        }

    elif name == "basalam_auth_logout":
        success = _client.logout()
        return {"status": "logged_out", "success": success}

    elif name == "basalam_status":
        return {
            "service": "basalam-mcp",
            "status": "operational",
            "version": "1.0.0",
            "tools_count": len(TOOLS),
            "network_note": "Direct Iran Domestic Connectivity with Cloudflare Edge support",
        }

    elif name == "basalam_help":
        return {
            "service": "Basalam MCP Server",
            "description": "بازار اجتماعی باسلام (Basalam) - خرید و فروش مستقیم محصولات خانگی، محلی و صنایع دستی",
            "tools": [{"name": t["name"], "description": t["description"]} for t in TOOLS],
        }

    else:
        raise ValueError(f"Unknown tool: {name}")
