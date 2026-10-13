"""
Torob API Client
REST client for Torob (ترب) smart price comparison marketplace.
Supports dual-mode routing: Direct Iran connection with seamless Cloudflare Edge fallback.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("torob_mcp.client")

TOROB_API_BASE = "https://api.torob.com/v4"
TOROB_WEB_BASE = "https://torob.com"
CLOUDFLARE_PROXY_BASE = "https://torob-mcp.alphanet-edge.workers.dev/api/proxy"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TOKEN_STORAGE_PATH = os.path.expanduser("~/.torob_mcp_token.json")

TOROB_CATEGORIES = [
    {"id": 94, "name_fa": "موبایل و تبلت", "name_en": "Mobile & Tablet", "slug": "mobile-phone"},
    {"id": 99, "name_fa": "لپ‌تاپ و کامپیوتر", "name_en": "Laptops & Computers", "slug": "laptop"},
    {"id": 104, "name_fa": "هدفون، هدست و هندزفری", "name_en": "Headphones & Audio", "slug": "headphone"},
    {"id": 80, "name_fa": "لوازم خانگی", "name_en": "Home Appliances", "slug": "home-appliances"},
    {"id": 257, "name_fa": "صوتی و تصویری", "name_en": "TV & Audio", "slug": "tv-audio"},
    {"id": 180, "name_fa": "آرایشی و بهداشتی", "name_en": "Beauty & Health", "slug": "beauty-health"},
    {"id": 310, "name_fa": "مد و پوشاک", "name_en": "Fashion & Clothing", "slug": "fashion"},
    {"id": 450, "name_fa": "ابزارآلات و صنعتی", "name_en": "Tools & Industrial", "slug": "tools"},
    {"id": 520, "name_fa": "خودرو و لوازم یدکی", "name_en": "Car & Vehicle Parts", "slug": "car-parts"},
    {"id": 610, "name_fa": "کتاب و لوازم تحریر", "name_en": "Books & Stationery", "slug": "stationery"},
    {"id": 700, "name_fa": "کالاهای سوپرمارکتی", "name_en": "Supermarket & Groceries", "slug": "supermarket"},
]


class TorobClient:
    """Production client for Torob Price Comparison Marketplace."""

    def __init__(self, timeout: float = 6.0, force_proxy: bool = False):
        self.timeout = timeout
        self.force_proxy = force_proxy
        self.token = self._load_persisted_token()
        self._prefer_proxy = force_proxy

    def _load_persisted_token(self) -> Optional[str]:
        try:
            if os.path.exists(TOKEN_STORAGE_PATH):
                with open(TOKEN_STORAGE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("access_token")
        except Exception:
            pass
        return None

    def set_token(self, token: str) -> None:
        self.token = token.strip()
        try:
            with open(TOKEN_STORAGE_PATH, "w", encoding="utf-8") as f:
                json.dump({"access_token": self.token}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Could not persist Torob token: %s", e)

    def logout(self) -> bool:
        self.token = None
        if os.path.exists(TOKEN_STORAGE_PATH):
            try:
                os.remove(TOKEN_STORAGE_PATH)
                return True
            except Exception:
                return False
        return True

    def _get_headers(self, auth_required: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa,en;q=0.9",
        }
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        return headers

    def _fetch_json(self, path: str, params: Optional[Dict[str, Any]] = None, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch JSON with automatic fallback to Cloudflare Edge proxy if direct connection is blocked."""
        query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        
        # Decide primary and secondary endpoints
        if self._prefer_proxy:
            endpoints = [f"{CLOUDFLARE_PROXY_BASE}{path}{query_str}", f"{TOROB_API_BASE}{path}{query_str}"]
        else:
            endpoints = [f"{TOROB_API_BASE}{path}{query_str}", f"{CLOUDFLARE_PROXY_BASE}{path}{query_str}"]

        last_error = None
        for ep in endpoints:
            try:
                data_bytes = json.dumps(payload).encode("utf-8") if payload else None
                req = urllib.request.Request(ep, data=data_bytes, headers=self._get_headers(), method=method)
                if payload:
                    req.add_header("Content-Type", "application/json")

                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    # If this succeeded and was proxy, remember proxy preference to keep calls fast
                    if CLOUDFLARE_PROXY_BASE in ep:
                        self._prefer_proxy = True
                    return json.loads(raw)
            except Exception as e:
                last_error = e
                # Fallback to next endpoint
                continue

        logger.error("Failed to fetch Torob endpoint %s: %s", path, last_error)
        return {"error": f"Connection error: {str(last_error)}"}

    def search_products(self, query: str, page: int = 1, price_min: Optional[int] = None, price_max: Optional[int] = None) -> Dict[str, Any]:
        """Search products with price ranges."""
        if not query or not query.strip():
            return {"count": 0, "results": []}

        params: Dict[str, Any] = {
            "q": query.strip(),
            "page": page,
        }
        if price_min is not None:
            params["price__gte"] = price_min
        if price_max is not None:
            params["price__lte"] = price_max

        data = self._fetch_json("/base-product/search/", params=params)
        if "error" in data:
            return data

        raw_results = data.get("results") or []
        items = []
        for it in raw_results:
            items.append({
                "prk": it.get("random_key"),
                "title": it.get("name1") or it.get("name2"),
                "title_en": it.get("name2"),
                "price": it.get("price") or 0,
                "price_text": it.get("price_text") or (f"{it.get('price'):,} تومان" if it.get("price") else "ناموجود"),
                "shops_count": it.get("num_shops") or it.get("shops_count") or 1,
                "image_url": it.get("image_url"),
                "category_id": it.get("category_id"),
                "torob_url": it.get("web_client_absolute_url") or f"{TOROB_WEB_BASE}/p/{it.get('random_key')}/",
                "badges": it.get("badges") or [],
            })

        return {
            "count": data.get("count", len(items)),
            "query": query,
            "page": page,
            "results": items,
        }

    def get_product_details(self, prk: str) -> Dict[str, Any]:
        """Get product full specifications and sellers list."""
        clean_prk = (prk or "").strip()
        if not clean_prk:
            return {"error": "Product key (prk) is required"}

        data = self._fetch_json("/base-product/details-log-click/", params={"prk": clean_prk})
        if "error" in data:
            return data

        pi = data.get("products_info")
        if isinstance(pi, dict):
            raw_sellers = pi.get("result") or []
        elif isinstance(pi, list):
            raw_sellers = pi
        else:
            raw_sellers = data.get("sellers") or []

        sellers = []
        for s in raw_sellers:
            if not isinstance(s, dict):
                continue
            raw_p = s.get("price") or 0
            sellers.append({
                "shop_name": s.get("shop_name") or s.get("name1"),
                "price": raw_p,
                "price_text": s.get("price_text") or (f"{raw_p:,} تومان" if raw_p else "استعلام"),
                "city": s.get("city_name") or "انبار مرکزی",
                "warranty": s.get("warranty") or "گارانتی اصالت و سلامت فیزیکی",
                "shop_score": s.get("shop_score") or round(s.get("score", 0) / 20.0, 1),
                "is_special": bool(s.get("is_special")),
                "buy_url": s.get("web_client_absolute_url") or s.get("page_url"),
                "last_price_change": s.get("last_price_change_date"),
            })

        sellers.sort(key=lambda x: x["price"])

        min_p = sellers[0]["price"] if sellers else (data.get("price") or 0)
        return {
            "prk": clean_prk,
            "title": data.get("name1") or data.get("name2"),
            "title_en": data.get("name2"),
            "description": data.get("description", ""),
            "min_price": min_p,
            "min_price_text": data.get("price_text") or (sellers[0]["price_text"] if sellers else "ناموجود"),
            "max_price": sellers[-1]["price"] if sellers else data.get("price", 0),
            "shops_count": len(sellers) or data.get("num_shops", 0),
            "image_url": data.get("image_url"),
            "category_id": data.get("category_id"),
            "category_name": data.get("category_name"),
            "specs": data.get("attributes") or [],
            "sellers": sellers,
            "torob_url": f"{TOROB_WEB_BASE}/p/{clean_prk}/",
        }

    def get_price_chart(self, prk: str) -> Dict[str, Any]:
        """Fetch price fluctuation history over time."""
        clean_prk = (prk or "").strip()
        if not clean_prk:
            return {"error": "Product key (prk) is required"}

        data = self._fetch_json("/base-product/price-chart/", params={"prk": clean_prk})
        if "error" in data:
            return data

        raw_points = data.get("chart") or data.get("history") or []
        history = []
        for pt in raw_points:
            p = pt.get("price", 0)
            history.append({
                "date": pt.get("date") or pt.get("time"),
                "price": p,
                "price_formatted": f"{p:,} تومان" if p else "-",
            })

        return {
            "prk": clean_prk,
            "chart_points_count": len(history),
            "min_price_seen": data.get("min_price", 0),
            "max_price_seen": data.get("max_price", 0),
            "history": history,
        }

    def get_special_offers(self, page: int = 1) -> Dict[str, Any]:
        """Fetch Torob daily discounts and special offers."""
        data = self._fetch_json("/special-offers/", params={"page": page})
        if "error" in data:
            return data

        results = []
        for it in data.get("results") or []:
            results.append({
                "prk": it.get("random_key"),
                "title": it.get("name1") or it.get("name2"),
                "price": it.get("price"),
                "price_text": it.get("price_text"),
                "discount_percent": it.get("discount_percent"),
                "image_url": it.get("image_url"),
                "torob_url": f"{TOROB_WEB_BASE}/p/{it.get('random_key')}/",
            })

        return {
            "count": data.get("count", len(results)),
            "page": page,
            "results": results,
        }

    def get_suggestions(self, query: str) -> List[Dict[str, Any]]:
        """Get autosuggest autocomplete keywords."""
        if not query or not query.strip():
            return []
        data = self._fetch_json("/suggestion/search/", params={"q": query.strip()})
        if "error" in data or not isinstance(data, dict):
            return []
        return data.get("results") or []

    def list_categories(self) -> List[Dict[str, Any]]:
        """Return the curated list of Torob categories."""
        return TOROB_CATEGORIES

    # --- Authentication Endpoints ---

    def send_otp(self, phone_number: str) -> Dict[str, Any]:
        """Send OTP verification SMS code to user phone."""
        clean_phone = (phone_number or "").strip()
        if not clean_phone:
            return {"error": "Phone number is required"}
        payload = {"phone_number": clean_phone}
        return self._fetch_json("/user/send-otp/", method="POST", payload=payload)

    def verify_otp(self, phone_number: str, code: str) -> Dict[str, Any]:
        """Verify OTP SMS code and obtain authentication token."""
        clean_phone = (phone_number or "").strip()
        clean_code = (code or "").strip()
        if not clean_phone or not clean_code:
            return {"error": "Both phone_number and code are required"}

        payload = {"phone_number": clean_phone, "code": clean_code}
        res = self._fetch_json("/user/login-with-otp/", method="POST", payload=payload)
        token = res.get("token") or res.get("access_token")
        if token:
            self.set_token(token)
            return {"status": "authenticated", "token_saved": True, "message": "Login successful"}
        return res

    def get_user_profile(self) -> Dict[str, Any]:
        """Get user account details (requires auth)."""
        if not self.token:
            return {"error": "Authentication required. Use torob_auth_set_token or torob_auth_verify_otp."}
        return self._fetch_json("/user/profile/")

    def get_user_bookmarks(self) -> Dict[str, Any]:
        """Get user saved/bookmarked products (requires auth)."""
        if not self.token:
            return {"error": "Authentication required. Use torob_auth_set_token or torob_auth_verify_otp."}
        return self._fetch_json("/user/bookmarks/")
