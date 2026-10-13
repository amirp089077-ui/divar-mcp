"""
Basalam API Client
REST client for Basalam (باسلام) social marketplace.
Provides endpoints for artisan products, vendor profiles, reviews, search, and user authentication.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("basalam_mcp.client")

BASALAM_SEARCH_BASE = "https://search.basalam.com"
BASALAM_CORE_BASE = "https://core.basalam.com"
BASALAM_API_BASE = "https://api.basalam.com"
BASALAM_REVIEW_BASE = "https://review.basalam.com"
BASALAM_WEB_BASE = "https://basalam.com"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TOKEN_STORAGE_PATH = os.path.expanduser("~/.basalam_mcp_token.json")

BASALAM_CATEGORIES = [
    {"id": "food-beverage", "name_fa": "مواد غذایی و خوراکی", "name_en": "Food & Groceries"},
    {"id": "handicrafts", "name_fa": "صنایع دستی و سنتی", "name_en": "Handicrafts & Traditional Art"},
    {"id": "clothing", "name_fa": "پوشاک زنانه، مردانه و کودک", "name_en": "Fashion & Apparel"},
    {"id": "beauty-health", "name_fa": "آرایشی، بهداشتی و طب سنتی", "name_en": "Beauty & Health"},
    {"id": "home-kitchen", "name_fa": "خانه و آشپزخانه", "name_en": "Home & Kitchen"},
    {"id": "digital-goods", "name_fa": "لوازم دیجیتال و جانبی", "name_en": "Digital Accessories"},
    {"id": "stationery-books", "name_fa": "کتاب، هنر و لوازم تحریر", "name_en": "Books & Stationery"},
    {"id": "kids-toys", "name_fa": "کودک، نوزاد و اسباب‌بازی", "name_en": "Kids & Toys"},
]


class BasalamClient:
    """Production client for Basalam Marketplace."""

    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout
        self.token = self._load_persisted_token()

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
            logger.warning("Could not persist Basalam token: %s", e)

    def logout(self) -> bool:
        self.token = None
        if os.path.exists(TOKEN_STORAGE_PATH):
            try:
                os.remove(TOKEN_STORAGE_PATH)
                return True
            except Exception:
                return False
        return True

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa,en;q=0.9",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _fetch_json(self, url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch JSON data from Basalam APIs."""
        data_bytes = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data_bytes, headers=self._get_headers(), method=method)
        if payload:
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return {"error": f"Connection error: {str(e)}"}

    def search_products(self, query: str, page: int = 1, price_min: Optional[int] = None, price_max: Optional[int] = None) -> Dict[str, Any]:
        """Search products on Basalam."""
        if not query or not query.strip():
            return {"count": 0, "results": []}

        params: Dict[str, Any] = {
            "q": query.strip(),
            "page": page,
        }
        if price_min is not None:
            params["price_from"] = price_min
        if price_max is not None:
            params["price_to"] = price_max

        url = f"{BASALAM_SEARCH_BASE}/ai-engine/api/v2.0/product/search?{urllib.parse.urlencode(params)}"
        data = self._fetch_json(url)
        if "error" in data:
            return data

        raw_list = data.get("products") or data.get("items") or data.get("results") or []
        items = []
        for p in raw_list:
            items.append({
                "id": p.get("id"),
                "title": p.get("title") or p.get("name"),
                "price": p.get("price") or 0,
                "price_text": f"{p.get('price'):,} تومان" if p.get("price") else "توافقی",
                "primary_photo": (p.get("photo") or {}).get("url") or p.get("image_url"),
                "vendor": {
                    "id": (p.get("vendor") or {}).get("id"),
                    "name": (p.get("vendor") or {}).get("name") or (p.get("vendor") or {}).get("title"),
                    "rating": (p.get("vendor") or {}).get("rating", {}).get("rate") or (p.get("vendor") or {}).get("rate", 0),
                    "city": (p.get("vendor") or {}).get("city") or (p.get("vendor") or {}).get("city_name"),
                },
                "rating": (p.get("rating") or {}).get("rate") or 0,
                "reviews_count": (p.get("rating") or {}).get("count") or 0,
                "basalam_url": f"{BASALAM_WEB_BASE}/product/{p.get('id')}",
            })

        return {
            "count": data.get("total", len(items)),
            "query": query,
            "page": page,
            "results": items,
        }

    def get_product_details(self, product_id: Any) -> Dict[str, Any]:
        """Get product full details."""
        clean_id = str(product_id).strip()
        url = f"{BASALAM_CORE_BASE}/v4/products/{clean_id}"
        data = self._fetch_json(url)
        if "error" in data:
            return data

        return {
            "id": data.get("id", clean_id),
            "title": data.get("title") or data.get("name"),
            "description": data.get("description", ""),
            "price": data.get("price", 0),
            "price_text": f"{data.get('price', 0):,} تومان" if data.get("price") else "ناموجود",
            "stock": data.get("stock", 0),
            "vendor": {
                "id": (data.get("vendor") or {}).get("id"),
                "title": (data.get("vendor") or {}).get("title") or (data.get("vendor") or {}).get("name"),
                "identifier": (data.get("vendor") or {}).get("identifier"),
                "city": (data.get("vendor") or {}).get("city"),
                "score": (data.get("vendor") or {}).get("rating", {}).get("rate"),
            },
            "photos": [ph.get("url") for ph in data.get("photos", []) if ph.get("url")],
            "specs": data.get("attributes") or [],
            "basalam_url": f"{BASALAM_WEB_BASE}/product/{clean_id}",
        }

    def get_vendor_details(self, vendor_id: Any) -> Dict[str, Any]:
        """Get vendor/store details."""
        clean_id = str(vendor_id).strip()
        url = f"{BASALAM_CORE_BASE}/v3/vendors/{clean_id}"
        data = self._fetch_json(url)
        if "error" in data:
            return data

        return {
            "id": data.get("id", clean_id),
            "name": data.get("title") or data.get("name"),
            "identifier": data.get("identifier"),
            "description": data.get("description", ""),
            "city": data.get("city"),
            "rating": (data.get("rating") or {}).get("rate", 0),
            "total_reviews": (data.get("rating") or {}).get("count", 0),
            "total_products": data.get("products_count", 0),
            "avatar_url": (data.get("avatar") or {}).get("url"),
            "badges": data.get("badges", []),
            "store_url": f"{BASALAM_WEB_BASE}/vendor/{data.get('identifier') or clean_id}",
        }

    def get_vendor_products(self, vendor_id: Any, page: int = 1) -> Dict[str, Any]:
        """Get all products by a specific vendor."""
        clean_id = str(vendor_id).strip()
        url = f"{BASALAM_CORE_BASE}/api_v2/vendor/products?vendor_id={clean_id}&page={page}"
        return self._fetch_json(url)

    def get_similar_products(self, product_id: Any) -> Dict[str, Any]:
        """Get similar products (More Like This)."""
        clean_id = str(product_id).strip()
        url = f"{BASALAM_SEARCH_BASE}/ai-engine/api/v2.0/mlt?product_id={clean_id}"
        return self._fetch_json(url)

    def get_popular_searches(self) -> Dict[str, Any]:
        """Fetch popular keywords."""
        url = f"{BASALAM_SEARCH_BASE}/ai-engine/api/v2.0/product/popular-searches"
        data = self._fetch_json(url)
        if "error" in data or not data.get("items"):
            return {"searches": ["زعفران قائنات", "عسل طبیعی سبلان", "روغن زیتون فرابکر", "خرما مضافتی بم", "ظروف مسی زنجان", "کیف چرم دست‌دوز"]}
        return {"searches": data.get("items", [])}

    def get_product_reviews(self, product_id: Any) -> Dict[str, Any]:
        """Get customer reviews on a product."""
        clean_id = str(product_id).strip()
        url = f"{BASALAM_REVIEW_BASE}/api_v1.0/reviews/?product_id={clean_id}"
        return self._fetch_json(url)

    def get_product_questions(self, product_id: Any) -> Dict[str, Any]:
        """Get questions and answers for a product."""
        clean_id = str(product_id).strip()
        url = f"{BASALAM_API_BASE}/api_v1.0/question/answers?product_id={clean_id}"
        return self._fetch_json(url)

    def list_categories(self) -> List[Dict[str, Any]]:
        """List major Basalam market categories."""
        return BASALAM_CATEGORIES

    # --- Authentication Endpoints ---

    def send_otp(self, phone_number: str) -> Dict[str, Any]:
        """Request SMS login OTP code."""
        clean_phone = (phone_number or "").strip()
        if not clean_phone:
            return {"error": "Phone number is required"}
        url = f"{BASALAM_API_BASE}/captcha/otp-request"
        return self._fetch_json(url, method="POST", payload={"mobile": clean_phone})

    def verify_otp(self, phone_number: str, code: str) -> Dict[str, Any]:
        """Verify SMS code and receive auth bearer token."""
        clean_phone = (phone_number or "").strip()
        clean_code = (code or "").strip()
        if not clean_phone or not clean_code:
            return {"error": "Both phone_number and code are required"}
        url = f"{BASALAM_API_BASE}/check-verification-code"
        res = self._fetch_json(url, method="POST", payload={"mobile": clean_phone, "code": clean_code})
        token = res.get("access_token") or res.get("token")
        if token:
            self.set_token(token)
            return {"status": "authenticated", "token_saved": True, "message": "Logged into Basalam successfully"}
        return res

    def get_user_profile(self) -> Dict[str, Any]:
        """Get authenticated user profile."""
        if not self.token:
            return {"error": "Authentication required. Use basalam_auth_set_token or basalam_auth_verify_otp."}
        url = f"{BASALAM_API_BASE}/api_v1.0/user"
        return self._fetch_json(url)

    def get_user_cart(self) -> Dict[str, Any]:
        """Get user shopping cart contents."""
        if not self.token:
            return {"error": "Authentication required."}
        url = f"{BASALAM_CORE_BASE}/cart"
        return self._fetch_json(url)
