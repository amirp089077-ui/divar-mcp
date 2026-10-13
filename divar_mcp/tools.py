"""Tool implementations shared by the MCP server and the CLI.

The MCP layer only transports JSON; everything with meaning lives here so it can
be unit tested and reused (CLI, cron, scripts, another agent framework).

Design rules for agent friendliness:
  * every tool returns a plain dict, always with the same shape for the same tool
  * errors are raised as DivarError, which carries suggestions + a repair hint
  * inputs are forgiving (city by id / Persian name / ASCII slug, category by
    slug or Persian name), and a wrong value comes back with close matches
  * results carry a ``meta`` block (requests, cache, elapsed) so an agent can
    tell a cheap call from an expensive one
"""

from __future__ import annotations

import os
import threading
import urllib.parse
from typing import Any

from .client import DivarClient, DivarError, WEB_BASE, load_categories, load_city_slugs
from .datasets import load_cities
from . import auth_client
from .store import Store, get_store
from . import __version__

SORT_VALUES = ["newest", "price_asc", "price_desc"]

CAVEATS = {
    "price": (
        "Prices are what sellers ask, in Toman, parsed from listing text. A low price can mean a "
        "broken item, a wrong model in the title, or a scam: always read the listing before acting."
    ),
    "phone": (
        "divar.ir does not expose seller phone numbers to logged-out clients. Chat/call happens in "
        "the Divar app; this server never tries to obtain contact details."
    ),
    "history": (
        "Price history is local to this machine and only as old as this server's own observations. "
        "It is not Divar's official history."
    ),
}


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _make_client() -> DivarClient:
    return DivarClient(
        timeout=_float_env("DIVAR_TIMEOUT", 25.0),
        min_interval=_float_env("DIVAR_MIN_INTERVAL", 0.8),
        cache_ttl=_float_env("DIVAR_CACHE_TTL", 180.0),
    )


_client_singleton: DivarClient | None = None
_client_lock = threading.Lock()


def build_client() -> DivarClient:
    """The shared, env-configured client.

    The MCP server is a long-lived process, so one client is reused across tool
    calls: its keep-alive sockets survive between calls (no repeated TLS
    handshakes) and identical requests inside the cache TTL are served locally.
    Set DIVAR_POOL=0 to force a fresh client per call (used by the benchmark and
    by tests that want full isolation).
    """
    global _client_singleton
    if os.environ.get("DIVAR_POOL", "1") == "0":
        return _make_client()
    with _client_lock:
        if _client_singleton is None:
            _client_singleton = _make_client()
        return _client_singleton


def reset_client() -> None:
    """Forget the shared client (after changing env vars, or between tests)."""
    global _client_singleton
    with _client_lock:
        if _client_singleton is not None:
            _client_singleton.close()
        _client_singleton = None


def build_store() -> Store:
    return get_store()


def _age_filter(result: dict, max_age_hours: float | None) -> dict:
    if max_age_hours is None:
        return result
    posts = result.get("posts") or []
    kept = [p for p in posts if p.get("age_hours") is None or p["age_hours"] <= max_age_hours]
    dropped = len(posts) - len(kept)
    result["posts"] = kept
    result["count"] = len(kept)
    if dropped:
        result["filtered_out_by_age"] = dropped
        result["max_age_hours"] = max_age_hours
    return result


def _text_filter(result: dict, exclude_terms: list[str] | None, title_contains: str | None) -> dict:
    posts = result.get("posts") or []
    if exclude_terms:
        needles = [t.strip().lower() for t in exclude_terms if t and t.strip()]
        if needles:
            kept = [
                p for p in posts
                if not any(n in (p.get("title") or "").lower() for n in needles)
            ]
            if len(kept) != len(posts):
                result["filtered_out_by_terms"] = len(posts) - len(kept)
            posts = kept
    if title_contains:
        needle = title_contains.strip().lower()
        kept = [p for p in posts if needle in (p.get("title") or "").lower()]
        result["filtered_out_by_title"] = len(posts) - len(kept)
        posts = kept
    result["posts"] = posts
    result["count"] = len(posts)
    return result


def _client_view(result: dict, brief: bool) -> dict:
    if brief:
        keep = {k: v for k, v in result.items() if k != "posts"}
        keep["posts"] = DivarClient.brief_posts(result.get("posts") or [])
        return keep
    return result


# ------------------------------------------------------------------ core tools


def divar_search(
    query: str | None = None,
    city: str | int | None = "تهران",
    cities: list | None = None,
    category: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    has_photo: bool = False,
    district_ids: list[str] | None = None,
    brand_model: str | None = None,
    sort: str | None = None,
    pages: int = 1,
    page_size: int = 24,
    max_age_hours: float | None = None,
    exclude_terms: list[str] | None = None,
    title_contains: str | None = None,
    limit: int | None = None,
    brief: bool = True,
    client: DivarClient | None = None,
) -> dict:
    """Search live Divar listings and return normalized rows."""
    client = client or build_client()
    if sort and sort not in SORT_VALUES:
        raise DivarError(
            f"unknown sort {sort!r}",
            suggestions=SORT_VALUES,
            hint="Use newest, price_asc or price_desc.",
        )
    result = client.search_many(
        pages=max(1, min(int(pages or 1), 5)),
        city=city,
        cities=cities,
        query=query,
        category=category,
        price_min=price_min,
        price_max=price_max,
        district_ids=district_ids,
        has_photo=bool(has_photo),
        brand_model=brand_model,
        page_size=max(1, min(int(page_size or 24), 60)),
        sort=sort,
    )
    result = _apply_age(result, max_age_hours)
    result = _text_filter(result, exclude_terms, title_contains)
    result = _client_view(result, brief)
    result["source"] = "api.divar.ir (public read-only web API)"
    result["caveat"] = CAVEATS["phone"]
    result.pop("cursor", None)
    if limit and result.get("posts"):
        result["posts"] = result["posts"][: int(limit)]
        result["count"] = len(result["posts"])
    return result


def _apply_age(result: dict, max_age_hours: float | None) -> dict:
    return _age_filter(result, max_age_hours)


def divar_get_post(
    token: str | None = None,
    post_token: str | None = None,
    client: DivarClient | None = None,
) -> dict:
    """Full public view of one post: price, attributes, images, dates, location."""
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    client = client or build_client()
    post = client.get_post(tok)
    post["source"] = "api.divar.ir (public read-only web API)"
    post["caveat"] = CAVEATS["phone"]
    return post


def divar_price_analysis(
    query: str | None = None,
    category: str | None = None,
    city: str | int | None = "تهران",
    cities: list | None = None,
    pages: int = 2,
    price_min: int | None = None,
    price_max: int | None = None,
    has_photo: bool = False,
    client: DivarClient | None = None,
) -> dict:
    """Comparable-listing price distribution, for valuing an item before listing it."""
    client = client or build_client()
    stats = client.price_stats(
        city=city,
        cities=cities,
        query=query,
        category=category,
        pages=max(1, min(int(pages or 2), 6)),
        price_min=price_min,
        price_max=price_max,
        has_photo=bool(has_photo),
    )
    stats["source"] = "api.divar.ir (public read-only web API)"
    stats["how_to_read"] = (
        "suggested_ask_range = 40th-75th percentile of live prices, in Toman. Divar buyers haggle, "
        "so asking near p50-p75 keeps you inside the active band without being the cheapest listing."
    )
    stats["caveat"] = CAVEATS["price"]
    return stats


def divar_find_deals(
    query: str | None = None,
    category: str | None = None,
    city: str | int | None = "تهران",
    cities: list | None = None,
    pages: int = 3,
    price_min: int | None = None,
    price_max: int | None = None,
    min_discount: float = 0.05,
    require_photo: bool = False,
    has_photo: bool = False,
    limit: int = 10,
    client: DivarClient | None = None,
) -> dict:
    """Listings priced below the live market for the same query, ranked and explained."""
    client = client or build_client()
    report = client.find_deals(
        city=city, cities=cities, query=query, category=category,
        pages=max(1, min(int(pages or 3), 6)), price_min=price_min, price_max=price_max,
        min_discount=min_discount, require_photo=bool(require_photo or has_photo),
        has_photo=bool(has_photo), limit=max(1, min(int(limit or 10), 40)),
    )
    report["source"] = "api.divar.ir (public read-only web API)"
    report["caveat"] = CAVEATS["price"]
    return report


def divar_appraise_post(
    token: str | None = None,
    post_token: str | None = None,
    city: str | int | None = None,
    pages: int = 2,
    client: DivarClient | None = None,
) -> dict:
    """Judge one listing's asking price against live comparables (is it overpriced?)."""
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    client = client or build_client()
    report = client.appraise_post(tok, city=city, pages=max(1, min(int(pages or 2), 4)))
    report["source"] = "api.divar.ir (public read-only web API)"
    report["caveat"] = CAVEATS["price"]
    return report


def divar_market_breakdown(
    query: str | None = None,
    category: str | None = None,
    city: str | int | None = "تهران",
    cities: list | None = None,
    pages: int = 2,
    min_listings: int = 1,
    has_photo: bool = False,
    price_min: int | None = None,
    price_max: int | None = None,
    client: DivarClient | None = None,
) -> dict:
    """Where the stock sits: price by district, bands, and how fresh the listings are."""
    client = client or build_client()
    report = client.market_breakdown(
        city=city, cities=cities, query=query, category=category,
        pages=max(1, min(int(pages or 2), 6)), min_listings=int(min_listings or 1),
        has_photo=bool(has_photo), price_min=price_min, price_max=price_max,
    )
    report["source"] = "api.divar.ir (public read-only web API)"
    return report


def divar_price_trend(
    query: str | None = None,
    category: str | None = None,
    city: str | int | None = "تهران",
    days: int = 30,
    client: DivarClient | None = None,
) -> dict:
    """Local price history for this filter, built up by this server's own observations."""
    client = client or build_client()
    report = client.price_trend(query=query, category=category, city=city,
                                days=max(1, min(int(days or 30), 365)))
    report["caveat"] = CAVEATS["history"]
    return report


def divar_similar_posts(
    token: str | None = None,
    post_token: str | None = None,
    city: str | int | None = None,
    limit: int = 12,
    client: DivarClient | None = None,
) -> dict:
    """Listings comparable to one post (same category/brand/city)."""
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    client = client or build_client()
    result = client.similar_posts(tok, city=city, limit=max(1, min(int(limit or 12), 40)))
    result["source"] = "api.divar.ir (public read-only web API)"
    return result


# ------------------------------------------------------------- watch (stateful)


def divar_watch_create(
    name: str,
    query: str | None = None,
    city: str | int | None = "تهران",
    cities: list | None = None,
    category: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    has_photo: bool = False,
    pages: int = 1,
    client: DivarClient | None = None,
) -> dict:
    """Save a search as a named watch; today's listings become the quiet baseline."""
    client = client or build_client()
    params = {
        "query": query, "city": city, "category": category,
        "price_min": price_min, "price_max": price_max, "has_photo": bool(has_photo),
    }
    if cities:
        params["cities"] = cities
    params = {k: v for k, v in params.items() if v not in (None, False)}
    report = client.watch_create(name, params, pages=max(1, min(int(pages or 1), 3)))
    report["next"] = f"divar_watch_check(name={name!r}) reports listings newer than this baseline."
    return report


def divar_watch_check(name: str, pages: int = 1, client: DivarClient | None = None) -> dict:
    """Run a saved watch and report only listings it has never seen before."""
    client = client or build_client()
    return client.watch_check(name, pages=max(1, min(int(pages or 1), 3)))


def divar_watch_list() -> dict:
    """All saved watches with their params and counters."""
    return build_client().watch_list()


def divar_watch_delete(name: str) -> dict:
    """Forget a saved watch."""
    return build_client().watch_delete(name)


# --------------------------------------------------------------- export / meta


def divar_export(
    query: str | None = None,
    category: str | None = None,
    city: str | int | None = "تهران",
    cities: list | None = None,
    pages: int = 3,
    price_min: int | None = None,
    price_max: int | None = None,
    path: str | None = None,
    format: str = "csv",
    full: bool = False,
    has_photo: bool = False,
    client: DivarClient | None = None,
) -> dict:
    """Write listings to a CSV or JSONL file on disk and return the absolute path."""
    client = client or build_client()
    return client.export_rows(
        city=city, cities=cities, query=query, category=category, pages=pages,
        price_min=price_min, price_max=price_max, path=path, fmt=format, full=bool(full),
        has_photo=bool(has_photo),
    )


def divar_status(probe: bool = True, client: DivarClient | None = None) -> dict:
    """Health check: is divar.ir reachable, what data is bundled, how big is the store."""
    client = client or build_client()
    report = client.health(probe=bool(probe))
    report["server"] = {"name": "divar-mcp", "version": __version__}
    report["env"] = {
        "min_interval_seconds": client.min_interval,
        "timeout_seconds": client.timeout,
        "cache_ttl_seconds": client.cache_ttl,
        "store_path": build_store().path,
    }
    return report


def divar_help() -> dict:
    """Capability map: tool index, datasets, units and ready-made recipes."""
    return {
        "server": {"name": "divar-mcp", "version": __version__, "market": "divar.ir (Iran)"},
        "units": {
            "currency": "Toman (Divar displays Toman; its schema.org price is Rial, 10x more)",
            "dates": "Jalali text plus ISO 8601 with +03:30",
            "age": "age_hours parsed from the Persian relative time shown on the listing",
        },
        "datasets": {
            "cities": len(load_cities()["by_id"]),
            "categories": len(load_categories()),
            "city_page_slugs": len(load_city_slugs()),
        },
        "tools": {
            "find": "divar_search (multi-city, filters, sort), divar_search_url",
            "read": "divar_get_post",
            "value": "divar_price_analysis, divar_appraise_post, divar_similar_posts",
            "hunt": "divar_find_deals, divar_market_breakdown, divar_price_trend",
            "watch": "divar_watch_create, divar_watch_check, divar_watch_list, divar_watch_delete",
            "bulk": "divar_export",
            "meta": "divar_status, divar_help, divar_list_cities, divar_list_categories, divar_post_filters",
        },
        "recipes": [
            {
                "task": "I want to sell something and do not know the price",
                "steps": [
                    "divar_list_categories('<what it is in Persian>') -> slug",
                    "divar_price_analysis(query='<model>', category=<slug>, city='تهران', pages=2)",
                    "quote suggested_ask_range and the median, then add 1-2 fresh comparables",
                ],
            },
            {
                "task": "Is this listing overpriced?",
                "steps": ["divar_appraise_post(token_or_url)", "read verdict + percentile + cheaper_alternatives"],
            },
            {
                "task": "Find something underpriced",
                "steps": [
                    "divar_find_deals(query=..., category=..., pages=3)",
                    "each deal carries deal_score, reasons and price_vs_median_pct",
                ],
            },
            {
                "task": "Watch the market over time",
                "steps": [
                    "divar_watch_create(name='iphone-13', query='آیفون ۱۳', city='تهران')",
                    "later: divar_watch_check(name='iphone-13') -> only new listings",
                    "divar_price_trend(query=..., city=...) once a few days of observations exist",
                ],
            },
            {
                "task": "Bulk data",
                "steps": ["divar_export(query=..., category=..., pages=5) -> absolute CSV/JSONL path"],
            },
        ],
        "rules": [
            "Read-only: this server never posts, edits, messages or reports.",
            "No phone numbers or contact data are collected.",
            "City accepts an id, a Persian name or an ASCII slug; a wrong value returns suggestions.",
            "Rate limited politely (default one request per 0.8s) with an LRU cache.",
        ],
        "caveats": CAVEATS,
    }


def divar_list_cities(query: str | None = None, limit: int = 400) -> dict:
    """Divar city ids used by the search filter (Persian names)."""
    from .resolve import suggest_cities

    items = load_cities()["by_id"]
    rows = [{"id": cid, "name": name, "slug": load_city_slugs().get(str(cid))}
            for cid, name in items.items()]
    if query:
        normalised = str(query).replace("\u200c", "").replace("ي", "ی").replace("ك", "ک")
        matches = [
            r for r in rows
            if normalised.lower() in r["name"].replace("\u200c", "").lower()
            or r["id"] == str(query)
            or normalised.lower() in (r["slug"] or "")
        ]
        if not matches:
            suggestions = suggest_cities(str(query), limit=5)
            return {
                "count": 0,
                "cities": [],
                "query": query,
                "suggestions": suggestions,
                "hint": "No city matched that text; the suggestions are the closest names.",
            }
        rows = matches
    return {
        "count": len(rows),
        "cities": rows[: int(limit or 400)],
        "hint": "Pass either the id, the Persian name or the ASCII slug as `city` to divar_search.",
    }


def divar_list_categories(query: str | None = None, limit: int = 200) -> dict:
    """Divar category slugs accepted by the search filter, with Persian names."""
    from .resolve import suggest_categories

    items = load_categories()
    if query:
        q = str(query).lower().replace("\u200c", "")
        matched = []
        for item in items:
            haystack = " ".join([item.get("slug", ""), item.get("name", "")] + list(item.get("parents") or []))
            if q in haystack.lower():
                matched.append(item)
        if not matched:
            return {
                "count": 0,
                "categories": [],
                "query": query,
                "suggestions": suggest_categories(str(query), limit=5),
                "hint": "No category matched that text; the suggestions are the closest slugs.",
            }
        items = matched
    return {
        "count": len(items),
        "categories": items[: int(limit or 200)],
        "hint": "Pass `slug` as `category`. Parents are the breadcrumb shown on divar.ir.",
    }


def divar_post_filters(
    city: str | int | None = "تهران",
    category: str | None = None,
    client: DivarClient | None = None,
) -> dict:
    """The filter widgets Divar currently exposes for a city (and category)."""
    client = client or build_client()
    return client.filters(city=city, category=client.resolve_category(category))


def divar_search_url(
    query: str | None = None,
    city: str | int | None = "تهران",
    category: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
) -> dict:
    """A divar.ir URL a human can open in a browser for the same search."""
    client = build_client()
    city_id, city_name = client.resolve_city(city)
    slug = load_city_slugs().get(str(city_id))
    known_slugs = {entry.get("slug") for entry in load_categories()}
    resolved_category = client.resolve_category(category)
    if not slug:
        return {
            "url": None,
            "city_id": city_id,
            "city": city_name,
            "city_path_segment": None,
            "category": resolved_category,
            "verified": False,
            "note": (
                f"no verified divar.ir page slug for city {city_name!r} (id {city_id}). "
                "Post links from divar_search (https://divar.ir/v/<token>) always work; "
                "run tools/harvest_city_slugs.py to resolve slugs for more cities."
            ),
        }
    path = "/s/" + urllib.parse.quote(slug)
    if resolved_category in known_slugs:
        path += "/" + urllib.parse.quote(resolved_category)
    params = {}
    if query:
        params["q"] = query
    for key, value in (("price_min", price_min), ("price_max", price_max)):
        if value is not None:
            params[key] = int(value)
    url = WEB_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return {
        "url": url,
        "city_id": city_id,
        "city": city_name,
        "city_path_segment": slug,
        "category": resolved_category if resolved_category in known_slugs else None,
        "verified": True,
        "note": "Open in a browser; divar.ir accepts q and price_min/price_max query params.",
    }



# ------------------------------------------------------------------ Auth & Contacts & Chat


def divar_auth_send_otp(phone: str) -> dict:
    """Send SMS OTP verification code to a phone number."""
    return auth_client.send_otp(phone)


def divar_auth_verify_otp(phone: str, code: str) -> dict:
    """Verify received OTP code and log in."""
    return auth_client.verify_otp(phone, code)


def divar_auth_set_token(token: str) -> dict:
    """Set authentication token directly."""
    return auth_client.set_token(token)


def divar_auth_status() -> dict:
    """Check current authentication status."""
    return auth_client.auth_status()


def divar_auth_logout() -> dict:
    """Log out and clear session."""
    return auth_client.logout()


def divar_get_contact(token: str | None = None, post_token: str | None = None) -> dict:
    """Extract contact information (phone number, chat, caller details) for a post."""
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    return auth_client.get_contact_info(tok)


def divar_get_my_posts() -> dict:
    """Get published and drafted posts of current user."""
    return auth_client.get_my_posts()


def divar_get_my_bookmarks() -> dict:
    """Get bookmarked posts of current user."""
    return auth_client.get_my_bookmarks()


def divar_bookmark_post(token: str | None = None, post_token: str | None = None, bookmark: bool = True) -> dict:
    """Bookmark or unbookmark a post."""
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    return auth_client.bookmark_post(tok, bookmark)


def divar_get_my_notes() -> dict:
    """Get personal notes saved on Divar posts."""
    return auth_client.get_my_notes()


def divar_set_post_note(note: str, token: str | None = None, post_token: str | None = None) -> dict:
    """Add or update a personal note on a Divar post."""
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    return auth_client.set_post_note(tok, note)


def divar_delete_post_note(token: str | None = None, post_token: str | None = None) -> dict:
    """Delete a personal note from a Divar post."""
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    return auth_client.delete_post_note(tok)


def divar_get_my_sessions() -> dict:
    """Fetch active login sessions and connected devices for current user."""
    return auth_client.get_my_sessions()


def divar_get_blocked_users() -> dict:
    """Fetch list of blocked chat users for current user."""
    return auth_client.get_blocked_users()


def divar_user_profile() -> dict:
    """Get current user profile."""
    return auth_client.get_user_profile()


def divar_chat_conversations() -> dict:
    """List active chat conversations."""
    return auth_client.chat_get_conversations()


def divar_chat_messages(conversation_id: str) -> dict:
    """Get message history for a conversation."""
    return auth_client.chat_get_messages(conversation_id)


def divar_chat_send(conversation_id: str, message: str) -> dict:
    """Send a message in a conversation."""
    return auth_client.chat_send_message(conversation_id, message)


def divar_chat_start(post_token: str | None = None, token: str | None = None, message: str | None = None) -> dict:
    """Start or resume a chat conversation with the seller of a post.
    
    This is the first step to send a message: it creates (or resumes) a conversation
    linked to a post. Optionally you can include an initial message.
    """
    tok = post_token or token
    if not tok:
        raise DivarError("شناسه آگهی (token یا post_token) الزامی است.")
    return auth_client.chat_start_conversation(tok, message)


def divar_post_create(
    category: str,
    title: str,
    description: str,
    price: int | None = None,
    city: str = "تهران",
    district: str | None = None,
    extra_fields: dict | None = None,
) -> dict:
    """Create a new ad (آگهی) draft on Divar. Requires authentication.
    
    Creates a draft ad that can be reviewed and published.
    Use divar_list_categories to find valid category slugs.
    """
    return auth_client.create_post_draft(
        category=category,
        title=title,
        description=description,
        price=price,
        city=city,
        district=district,
        extra_fields=extra_fields,
    )


def divar_post_ad_form(category: str) -> dict:
    """Get the form fields/schema for creating an ad in a specific category.
    
    Returns the required and optional fields, their types, and allowed values
    for the given category. Use this before divar_post_create.
    """
    return auth_client.get_postads_form(category)


# ------------------------------------------------------------------ MCP spec



def _schema(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


def _out(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": True}


_CITY = {"type": "string", "description": 'City id ("1"), Persian name ("تهران") or slug ("tehran").'}
_CITIES = {"type": "array", "items": {"type": "string"},
           "description": "Search several cities at once (ids, Persian names or slugs)."}
_CATEGORY = {"type": "string",
             "description": "Divar category slug or Persian name, e.g. mobile-phones / موبایل. See divar_list_categories."}
_PRICE = {"type": "integer", "description": "Price in Toman (not Rial)."}
_TOKEN = {"type": "string", "description": "Post token (gaxi5lYL) or any divar.ir post URL."}
_POST_ROW = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "token": {"type": "string"}, "title": {"type": "string"},
            "price_toman": {"type": ["integer", "null"]}, "price_human": {"type": ["string", "null"]},
            "district": {"type": ["string", "null"]}, "city": {"type": ["string", "null"]},
            "time_text": {"type": ["string", "null"]}, "age_hours": {"type": ["number", "null"]},
            "image_count": {"type": ["integer", "null"]}, "url": {"type": ["string", "null"]},
        },
    },
}
_META = {"type": "object", "description": "requests_made, cached_responses, elapsed_seconds"}
_SEARCH_OUT = _out({"count": {"type": "integer"}, "posts": _POST_ROW,
                    "city": {"type": ["string", "null"]}, "cities": {"type": ["array", "null"]},
                    "query": {"type": ["string", "null"]}, "category": {"type": ["string", "null"]},
                    "pages_fetched": {"type": "integer"}, "meta": _META},
                   ["count", "posts"])
_PRICE_OUT = _out({"priced_posts": {"type": "integer"}, "median": {"type": ["integer", "null"]},
                   "p25": {"type": ["integer", "null"]}, "p75": {"type": ["integer", "null"]},
                   "suggested_ask_range": {"type": ["array", "null"]},
                   "suggested_ask_human": {"type": ["string", "null"]},
                   "by_district": {"type": "array"}, "freshness": {"type": "object"}},
                  ["priced_posts"])
_APPRAISE_OUT = _out({"verdict": {"type": "string",
                                  "enum": ["below_market", "fair", "above_market", "not_enough_data"]},
                      "percentile": {"type": ["number", "null"]},
                      "delta_vs_median_pct": {"type": ["number", "null"]},
                      "median_price": {"type": ["integer", "null"]},
                      "comparable_posts": {"type": "integer"},
                      "confidence": {"type": "string"}, "summary": {"type": "string"}},
                     ["verdict", "comparable_posts"])
_DEALS_OUT = _out({"median_price": {"type": ["integer", "null"]}, "deal_count": {"type": "integer"},
                   "deals": {"type": "array"},
                   "suspicious_count": {"type": "integer",
                                        "description": "Prices under 15% of the median, quarantined as implausible"},
                   "suspicious": {"type": "array",
                                  "description": "The quarantined listings with an 'insight' explaining why"},
                   "sampled_posts": {"type": "integer"}},
                  ["deal_count", "deals"])

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "divar_search",
        "title": "Search divar.ir listings",
        "description": (
            "Search live divar.ir listings (Iran's largest classifieds). Read-only, no account. "
            "Honest filters: query, one or several cities, category, Toman price range, photo-only, "
            "numeric district ids, brand/model, plus client-side age and keyword filters that Divar "
            "itself does not offer. Returns compact rows (brief=true by default) with token, title, "
            "price in Toman, city, district, relative time and URL."
        ),
        "inputSchema": _schema({
            "query": {"type": "string", "description": 'Free text in Persian, e.g. "پژو ۲۰۶".'},
            "city": _CITY,
            "cities": _CITIES,
            "category": _CATEGORY,
            "price_min": _PRICE,
            "price_max": _PRICE,
            "has_photo": {"type": "boolean", "description": "Only listings with photos."},
            "district_ids": {"type": "array", "items": {"type": "string"},
                             "description": 'Divar numeric district ids, e.g. ["208"]. Get one from divar_get_post.'},
            "brand_model": {"type": "string",
                            "description": 'Exact model string, e.g. "samsung galaxy s21 5g" (from divar_get_post).'},
            "sort": {"type": "string", "enum": SORT_VALUES, "description": "Sort of the sampled rows."},
            "pages": {"type": "integer", "description": "Cursor pages to fetch (1-5). Each page is a request."},
            "page_size": {"type": "integer", "description": "Rows per page (max 60, default 24)."},
            "max_age_hours": {"type": "number",
                              "description": "Drop listings older than this (Divar's own recency filter does not work)."},
            "exclude_terms": {"type": "array", "items": {"type": "string"},
                              "description": 'Drop rows whose title contains any of these, e.g. ["خراب", "معیوب"].'},
            "title_contains": {"type": "string", "description": "Keep only titles containing this text."},
            "limit": {"type": "integer", "description": "Return at most this many rows."},
            "brief": {"type": "boolean", "description": "Compact rows (default true). false returns every parsed field."},
        }),
        "outputSchema": _SEARCH_OUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_get_post",
        "title": "Read one divar.ir post",
        "description": (
            "Full public detail for one post: title, description, price in Toman, structured attributes "
            "(brand/model, year, mileage...), image URLs, Jalali and ISO posted/updated dates, city and "
            "district plus the district id usable as a divar_search filter, and the category breadcrumb."
        ),
        "inputSchema": _schema({"token": _TOKEN}, ["token"]),
        "outputSchema": _out({"token": {"type": "string"}, "title": {"type": ["string", "null"]},
                              "price_toman": {"type": ["integer", "null"]},
                              "attributes": {"type": "object"}, "images": {"type": "array"},
                              "district_id": {"type": ["string", "null"]},
                              "posted_at": {"type": ["string", "null"]}}, ["token"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_price_analysis",
        "title": "What is this worth?",
        "description": (
            "Price distribution of comparable live listings: min, p25, p40, median, p75, max, mean, "
            "suggested ask range, price bands, freshness split and a per-district median table. Use this "
            "before writing an ad. Prices in Toman."
        ),
        "inputSchema": _schema({
            "query": {"type": "string", "description": 'Product text, e.g. "آیفون ۱۳".'},
            "category": _CATEGORY, "city": _CITY, "cities": _CITIES,
            "pages": {"type": "integer", "description": "Cursor pages to sample (1-6, default 2 ~= 48 listings)."},
            "price_min": _PRICE, "price_max": _PRICE,
        }),
        "outputSchema": _PRICE_OUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_appraise_post",
        "title": "Is this listing overpriced?",
        "description": (
            "Judge one listing's asking price against live comparables (same category, brand/model and "
            "city). Returns verdict (below_market / fair / above_market), percentile, delta versus the "
            "median, a confidence level from the sample size, and cheaper alternatives."
        ),
        "inputSchema": _schema({"token": _TOKEN, "city": _CITY,
                                "pages": {"type": "integer", "description": "Comparable pages to sample (1-4)."}},
                               ["token"]),
        "outputSchema": _APPRAISE_OUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_find_deals",
        "title": "Find underpriced listings",
        "description": (
            "Rank listings that sit below the live market for the same query: each result carries an "
            "explainable deal_score (price advantage, freshness, photo count, price stated) plus reasons. "
            "A low price is a signal to verify, not a verdict; the caveat is included in the response."
        ),
        "inputSchema": _schema({
            "query": {"type": "string"}, "category": _CATEGORY, "city": _CITY, "cities": _CITIES,
            "pages": {"type": "integer", "description": "Pages to sample (1-6, default 3)."},
            "price_min": _PRICE, "price_max": _PRICE,
            "min_discount": {"type": "number", "description": "Minimum discount vs median, 0.05 = 5% (default)."},
            "require_photo": {"type": "boolean", "description": "Skip listings without photos."},
            "limit": {"type": "integer", "description": "Max deals to return (default 10)."},
        }),
        "outputSchema": _DEALS_OUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_market_breakdown",
        "title": "Where the market is",
        "description": (
            "Supply map for one query: distribution summary, median price per district (busiest first), "
            "and how fresh the listings are. Answers 'which neighbourhoods have stock and at what price'."
        ),
        "inputSchema": _schema({
            "query": {"type": "string"}, "category": _CATEGORY, "city": _CITY,
            "pages": {"type": "integer", "description": "Pages to sample (1-6, default 2)."},
            "min_listings": {"type": "integer", "description": "Hide districts with fewer listings."},
        }),
        "outputSchema": _out({"by_district": {"type": "array"}, "summary": {"type": "object"},
                              "freshness": {"type": "object"}, "sampled_posts": {"type": "integer"}}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_price_trend",
        "title": "Price history for this filter",
        "description": (
            "Local day-by-day price history for an exact filter (city + category + query). Every search "
            "this server performs records a price point, so the series grows with use. Returns "
            "status=collecting with a clear note until at least two days exist."
        ),
        "inputSchema": _schema({
            "query": {"type": "string"}, "category": _CATEGORY, "city": _CITY,
            "days": {"type": "integer", "description": "How far back to look (default 30, max 365)."},
        }),
        "outputSchema": _out({"status": {"type": "string", "enum": ["ok", "collecting"]},
                              "days_tracked": {"type": "integer"}, "direction": {"type": ["string", "null"]},
                              "change_pct": {"type": ["number", "null"]}, "series": {"type": "array"}},
                             ["status", "days_tracked"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_similar_posts",
        "title": "Comparables for a post",
        "description": "Listings comparable to an existing post (same category, brand/model and city), excluding itself.",
        "inputSchema": _schema({"token": _TOKEN, "city": _CITY,
                                "limit": {"type": "integer", "description": "Max comparables (default 12)."}},
                               ["token"]),
        "outputSchema": _out({"count": {"type": "integer"}, "posts": _POST_ROW,
                              "source_post": {"type": "object"}}, ["count"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_watch_create",
        "title": "Save a search as a watch",
        "description": (
            "Save a named watch (a search) in local storage. The listings visible right now become the "
            "baseline, and later divar_watch_check calls report only listings that were not part of it. "
            "Designed to be called by a cron or by an agent between sessions."
        ),
        "inputSchema": _schema({
            "name": {"type": "string", "description": "Short id for the watch, e.g. iphone-13-tehran."},
            "query": {"type": "string"}, "city": _CITY, "cities": _CITIES, "category": _CATEGORY,
            "price_min": _PRICE, "price_max": _PRICE, "has_photo": {"type": "boolean"},
        }, ["name"]),
        "outputSchema": _out({"name": {"type": "string"}, "params": {"type": "object"},
                              "baseline_listings": {"type": "integer"}}, ["name"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_watch_check",
        "title": "What is new for a watch?",
        "description": (
            "Run a saved watch and return only the listings it has never reported before, updating the "
            "watch counters. This is the cron-friendly 'anything new today?' call."
        ),
        "inputSchema": _schema({"name": {"type": "string"},
                                "pages": {"type": "integer", "description": "Pages to scan (1-3)."}}, ["name"]),
        "outputSchema": _out({"watch": {"type": "string"}, "new_listings": {"type": "integer"},
                              "new": {"type": "array"}, "checked_at_listings": {"type": "integer"}},
                             ["watch", "new_listings"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_watch_list",
        "title": "List saved watches",
        "description": "Every saved watch with its search params, check counters and how many listings it has seen.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"count": {"type": "integer"}, "watches": {"type": "array"}}, ["count"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_watch_delete",
        "title": "Delete a watch",
        "description": "Forget a saved watch and its seen-listing history.",
        "inputSchema": _schema({"name": {"type": "string"}}, ["name"]),
        "outputSchema": _out({"watch": {"type": "string"}, "deleted": {"type": "boolean"}}, ["deleted"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_export",
        "title": "Export listings to a file",
        "description": (
            "Walk several pages and write the rows to a CSV or JSONL file on this machine, returning the "
            "absolute path. CSV is written utf-8-sig so Excel opens Persian text correctly. Use this for "
            "bulk analysis instead of pulling hundreds of rows through the model."
        ),
        "inputSchema": _schema({
            "query": {"type": "string"}, "category": _CATEGORY, "city": _CITY,
            "pages": {"type": "integer", "description": "Pages to export (1-10, default 3)."},
            "price_min": _PRICE, "price_max": _PRICE,
            "path": {"type": "string", "description": "Absolute output path (default: timestamped file in the cwd)."},
            "format": {"type": "string", "enum": ["csv", "jsonl"], "description": "Default csv."},
            "full": {"type": "boolean", "description": "true exports every parsed field."},
        }),
        "outputSchema": _out({"path": {"type": "string"}, "rows": {"type": "integer"},
                              "format": {"type": "string"}}, ["path", "rows"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_status",
        "title": "Server and API health",
        "description": (
            "Health and capability report: whether divar.ir answers right now (with latency and a clear "
            "hint when it does not), bundled dataset sizes, store size and cache counters. First call to "
            "make when something looks broken."
        ),
        "inputSchema": _schema({"probe": {"type": "boolean",
                                          "description": "Make a live 1-row request to test reachability (default true)."}}),
        "outputSchema": _out({"api": {"type": "object"}, "datasets": {"type": "object"},
                              "store": {"type": "object"}, "server": {"type": "object"}}, ["datasets"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_help",
        "title": "How to use this server",
        "description": (
            "Capability map with a tool index, the units used (Toman, Jalali plus ISO dates), dataset "
            "sizes and ready-made recipes for the common jobs (value an item, appraise a listing, hunt "
            "deals, watch the market, bulk export). No network call."
        ),
        "inputSchema": _schema({}),
        "outputSchema": _out({"tools": {"type": "object"}, "recipes": {"type": "array"},
                              "units": {"type": "object"}}, ["tools", "recipes"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_list_cities",
        "title": "Find a city",
        "description": (
            "Look up divar.ir cities by Persian name, ASCII slug or id. A miss returns the closest names "
            "instead of an empty list."
        ),
        "inputSchema": _schema({"query": {"type": "string", "description": 'e.g. "مشهد" or "mashhad".'}}),
        "outputSchema": _out({"count": {"type": "integer"}, "cities": {"type": "array"},
                              "suggestions": {"type": "array"}}, ["count"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_list_categories",
        "title": "Find a category slug",
        "description": (
            "Look up divar.ir category slugs by Persian or English text, with breadcrumb parents. A miss "
            "returns the closest slugs."
        ),
        "inputSchema": _schema({"query": {"type": "string", "description": 'e.g. "موبایل" or "mobile".'}}),
        "outputSchema": _out({"count": {"type": "integer"}, "categories": {"type": "array"},
                              "suggestions": {"type": "array"}}, ["count"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_post_filters",
        "title": "Filters Divar exposes",
        "description": "Which filter widgets divar.ir currently offers for a city (and category): price range, districts, photo-only.",
        "inputSchema": _schema({"city": _CITY, "category": _CATEGORY}),
        "outputSchema": _out({"filters": {"type": "array"}, "city": {"type": ["string", "null"]}}, ["filters"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_search_url",
        "title": "Browser link for a search",
        "description": (
            "Build a divar.ir URL a human can open in a browser for the same search. Returns "
            "url: null with a reason when no verified city page slug exists, rather than a link that may 404."
        ),
        "inputSchema": _schema({"query": {"type": "string"}, "city": _CITY, "category": _CATEGORY,
                                "price_min": _PRICE, "price_max": _PRICE}),
        "outputSchema": _out({"url": {"type": ["string", "null"]}, "verified": {"type": "boolean"},
                              "city_path_segment": {"type": ["string", "null"]}, "note": {"type": "string"}},
                             ["url"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_auth_send_otp",
        "title": "Send Login OTP SMS",
        "description": "Send SMS verification code to an Iranian mobile number (e.g. 09121234567) to log in to Divar.",
        "inputSchema": _schema({"phone": {"type": "string", "description": "شماره موبایل کاربر (09xxxxxxxxx)"}}, ["phone"]),
        "outputSchema": _out({"status": {"type": "string"}, "phone": {"type": "string"}, "retry_after_seconds": {"type": "integer"}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_auth_verify_otp",
        "title": "Verify Login OTP",
        "description": "Verify SMS OTP code received on mobile and establish authenticated Divar session.",
        "inputSchema": _schema({"phone": {"type": "string", "description": "شماره موبایل"}, "code": {"type": "string", "description": "کد تأیید پیامک شده"}}, ["phone", "code"]),
        "outputSchema": _out({"status": {"type": "string"}, "authenticated": {"type": "boolean"}}, ["status", "authenticated"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_auth_set_token",
        "title": "Set Auth Token Directly",
        "description": "Set Divar authentication token directly from browser cookies or storage without SMS.",
        "inputSchema": _schema({"token": {"type": "string", "description": "توکن احراز هویت دیوار"}}, ["token"]),
        "outputSchema": _out({"status": {"type": "string"}, "authenticated": {"type": "boolean"}}, ["status", "authenticated"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_auth_status",
        "title": "Check Auth Status",
        "description": "Check if currently logged in to Divar, view phone number and session details.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"authenticated": {"type": "boolean"}}, ["authenticated"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_auth_logout",
        "title": "Log Out of Divar",
        "description": "Clear saved session and log out of Divar.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"status": {"type": "string"}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "divar_get_contact",
        "title": "Get Seller Phone & Contact Info",
        "description": "Extract seller phone number, call info, and chat status for a post. Requires logged-in Divar account.",
        "inputSchema": _schema({"token": _TOKEN}, ["token"]),
        "outputSchema": _out({"token": {"type": "string"}, "phones": {"type": "array"}, "primary_phone": {"type": ["string", "null"]}}, ["token"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_get_my_posts",
        "title": "View My Published Ads",
        "description": "Fetch list of ads published or drafted by current user on Divar. Requires logged-in account.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"count": {"type": "integer"}, "posts": {"type": "array"}}, ["count", "posts"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_get_my_bookmarks",
        "title": "View Saved / Bookmarked Ads",
        "description": "Fetch list of saved/bookmarked ads for current user. Requires logged-in account.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"count": {"type": "integer"}, "bookmarks": {"type": "array"}}, ["count", "bookmarks"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_bookmark_post",
        "title": "Bookmark or Unbookmark Ad",
        "description": "Save or unsave an ad in current user's bookmarks.",
        "inputSchema": _schema({"token": _TOKEN, "bookmark": {"type": "boolean", "description": "true to bookmark, false to remove"}}, ["token"]),
        "outputSchema": _out({"status": {"type": "string"}, "bookmarked": {"type": "boolean"}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_get_my_notes",
        "title": "Get Personal Notes on Ads",
        "description": "Fetch user's private personal notes written on Divar ads. Requires logged-in account.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"count": {"type": "integer"}, "notes": {"type": "array"}}, ["count", "notes"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_set_post_note",
        "title": "Add or Edit Note on Ad",
        "description": "Add or update a private personal note on a Divar ad. Requires logged-in account.",
        "inputSchema": _schema({"token": _TOKEN, "note": {"type": "string", "description": "متن یادداشت شخصی"}}, ["token", "note"]),
        "outputSchema": _out({"status": {"type": "string"}, "token": {"type": "string"}, "note": {"type": "string"}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_delete_post_note",
        "title": "Delete Note from Ad",
        "description": "Delete a private personal note from a Divar ad. Requires logged-in account.",
        "inputSchema": _schema({"token": _TOKEN}, ["token"]),
        "outputSchema": _out({"status": {"type": "string"}, "token": {"type": "string"}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_get_my_sessions",
        "title": "Get Active Login Sessions & Devices",
        "description": "Fetch connected devices, browsers, and active login sessions for the logged-in user.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"count": {"type": "integer"}, "current_device": {"type": "string"}, "other_sessions": {"type": "array"}}, ["count"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_get_blocked_users",
        "title": "Get Blocked Users",
        "description": "Fetch list of blocked users in chat for the logged-in account.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"count": {"type": "integer"}, "blocked_users": {"type": "array"}}, ["count", "blocked_users"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_user_profile",
        "title": "Get User Profile",
        "description": "Fetch profile details (phone, status, verification, wallet) of logged-in user.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"phone": {"type": ["string", "null"]}}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_chat_conversations",
        "title": "List Chat Conversations",
        "description": "Fetch active chat conversations of current user. Requires logged-in account.",
        "inputSchema": _schema({}),
        "outputSchema": _out({"count": {"type": "integer"}, "conversations": {"type": "array"}}, ["count"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_chat_messages",
        "title": "Get Chat Messages",
        "description": "Fetch messages history for a conversation. Requires logged-in account.",
        "inputSchema": _schema({"conversation_id": {"type": "string", "description": "شناسه گفتگو"}}, ["conversation_id"]),
        "outputSchema": _out({"conversation_id": {"type": "string"}, "messages": {"type": "array"}}, ["conversation_id"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "divar_chat_send",
        "title": "Send Chat Message",
        "description": "Send a text message in an existing conversation on Divar. Requires logged-in account.",
        "inputSchema": _schema({"conversation_id": {"type": "string", "description": "شناسه گفتگو"}, "message": {"type": "string", "description": "متن پیام"}}, ["conversation_id", "message"]),
        "outputSchema": _out({"status": {"type": "string"}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_chat_start",
        "title": "Start Chat Conversation",
        "description": "Start or resume a chat conversation with the seller of a specific post. Optionally send an initial message. Requires logged-in account.",
        "inputSchema": _schema(
            {"post_token": {"type": "string", "description": "شناسه یا لینک آگهی"},
             "message": {"type": "string", "description": "پیام اولیه (اختیاری)"}},
            ["post_token"],
        ),
        "outputSchema": _out({"status": {"type": "string"}, "conversation_id": {"type": ["string", "null"]}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_post_create",
        "title": "Create New Ad (ثبت آگهی)",
        "description": "Create a new ad/listing draft on Divar. Use divar_list_categories for valid slugs and divar_post_ad_form to see required fields. Requires logged-in account.",
        "inputSchema": _schema(
            {"category": {"type": "string", "description": "دسته‌بندی آگهی (slug)"},
             "title": {"type": "string", "description": "عنوان آگهی"},
             "description": {"type": "string", "description": "متن و توضیحات آگهی"},
             "price": {"type": "integer", "description": "قیمت به تومان (اختیاری، 0 برای توافقی)"},
             "city": {"type": "string", "description": "شهر (پیش‌فرض: تهران)"},
             "district": {"type": "string", "description": "محله یا منطقه (اختیاری)"},
             "extra_fields": {"type": "object", "description": "فیلدهای اضافی مخصوص دسته‌بندی (اختیاری)"}},
            ["category", "title", "description"],
        ),
        "outputSchema": _out({"status": {"type": "string"}, "draft": {"type": "object"}}, ["status"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "divar_post_ad_form",
        "title": "Get Ad Form Schema",
        "description": "Get the form fields/schema for creating an ad in a specific category. Use before divar_post_create to know which fields are required.",
        "inputSchema": _schema({"category": {"type": "string", "description": "دسته‌بندی (slug)"}}, ["category"]),
        "outputSchema": _out({}, []),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
]

REGISTRY = {
    "divar_search": divar_search,
    "divar_get_post": divar_get_post,
    "divar_price_analysis": divar_price_analysis,
    "divar_appraise_post": divar_appraise_post,
    "divar_find_deals": divar_find_deals,
    "divar_market_breakdown": divar_market_breakdown,
    "divar_price_trend": divar_price_trend,
    "divar_similar_posts": divar_similar_posts,
    "divar_watch_create": divar_watch_create,
    "divar_watch_check": divar_watch_check,
    "divar_watch_list": divar_watch_list,
    "divar_watch_delete": divar_watch_delete,
    "divar_export": divar_export,
    "divar_status": divar_status,
    "divar_help": divar_help,
    "divar_list_cities": divar_list_cities,
    "divar_list_categories": divar_list_categories,
    "divar_post_filters": divar_post_filters,
        "divar_search_url": divar_search_url,
    "divar_auth_send_otp": divar_auth_send_otp,
    "divar_auth_verify_otp": divar_auth_verify_otp,
    "divar_auth_set_token": divar_auth_set_token,
    "divar_auth_status": divar_auth_status,
    "divar_auth_logout": divar_auth_logout,
    "divar_get_contact": divar_get_contact,
    "divar_get_my_posts": divar_get_my_posts,
    "divar_get_my_bookmarks": divar_get_my_bookmarks,
    "divar_bookmark_post": divar_bookmark_post,
    "divar_get_my_notes": divar_get_my_notes,
    "divar_set_post_note": divar_set_post_note,
    "divar_delete_post_note": divar_delete_post_note,
    "divar_get_my_sessions": divar_get_my_sessions,
    "divar_get_blocked_users": divar_get_blocked_users,
    "divar_user_profile": divar_user_profile,
    "divar_chat_conversations": divar_chat_conversations,
    "divar_chat_messages": divar_chat_messages,
    "divar_chat_send": divar_chat_send,
    "divar_chat_start": divar_chat_start,
    "divar_post_create": divar_post_create,
    "divar_post_ad_form": divar_post_ad_form,
}

READ_ONLY_TOOLS = {
    name for name, spec in ((s["name"], s) for s in TOOL_SPECS)
    if spec.get("annotations", {}).get("readOnlyHint")
}


def call_tool(name: str, arguments: dict | None) -> Any:
    fn = REGISTRY.get(name)
    if fn is None:
        raise DivarError(
            f"unknown tool: {name}",
            suggestions=sorted(REGISTRY),
            hint="divar_help lists the available tools.",
        )
    return fn(**(arguments or {}))
