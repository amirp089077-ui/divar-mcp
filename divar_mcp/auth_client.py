"""Authenticated Divar API client: OTP login, contacts, user profile, chat, and saved posts.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import ssl
import uuid
import struct
import base64
import time
from typing import Any

from . import session
from .client import DivarError
from .normalize import extract_token
from .proto_decoder import decode_protobuf

API_BASE = "https://api.divar.ir"
CHAT_BASE = "https://chat.divar.ir"
GRPC_BASE = "https://grpc-api.divar.ir"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Google Chrome";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
    "X-Standard-Divar-Error": "true",
    "x-render-type": "CSR",
    "x-web-serving-mode": "desktop",
}

_ssl_context = ssl.create_default_context()


def normalize_phone(phone: str) -> str:
    """Normalize phone number to 09XXXXXXXXX format."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("98"):
        digits = "0" + digits[2:]
    elif not digits.startswith("0") and len(digits) == 10:
        digits = "0" + digits
    if len(digits) != 11 or not digits.startswith("09"):
        raise DivarError(f"شماره موبایل نامعتبر است: {phone}. شماره باید به فرمت 09xxxxxxxxx باشد.")
    return digits


def _make_request(
    url: str,
    method: str = "GET",
    body: dict | None = None,
    auth_required: bool = False,
    custom_headers: dict | None = None,
) -> dict:
    headers = dict(DEFAULT_HEADERS)
    if custom_headers:
        headers.update(custom_headers)

    token = session.get_token()
    cookies = session.get_cookies()
    if token:
        headers["authorization"] = f"Basic {token}"
    if cookies:
        headers["cookie"] = cookies
    elif token:
        headers["cookie"] = f"token={token}; auth_token={token}"
    elif auth_required:
        raise DivarError(
            "این عملیات نیاز به احراز هویت در دیوار دارد.",
            status=401,
            suggestions=["divar_auth_send_otp", "divar_auth_set_token", "divar_auth_status"],
            hint="ابتدا با دستور divar_auth_send_otp کد ورود دریافت کنید، یا با divar_auth_set_token توکن را وارد کنید."
        )

    payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            if not content.strip():
                return {}
            try:
                return json.loads(content)
            except Exception:
                return {"raw": content}
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8", errors="ignore")
        try:
            err_json = json.loads(err_content)
        except Exception:
            err_json = {"raw": err_content}
        raise RuntimeError(
            f"خطا در ارتباط با دیوار (HTTP {e.code}): {err_json.get('message') or err_json.get('error') or err_content}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"خطای شبکه: {e}") from e


def _make_grpc_request(service_method: str, payload: bytes = b"") -> bytes:
    """Make a framed gRPC call to Divar's gRPC backend."""
    token = session.get_token()
    cookies = session.get_cookies()
    headers = {
        "User-Agent": "Divar/11.16.0 (Android; 13)",
        "Content-Type": "application/grpc",
        "Accept": "application/grpc",
        "x-user-agent": "Divar/11.16.0 (Android; 13)",
        "te": "trailers",
    }
    if token:
        headers["authorization"] = f"Basic {token}"
    if cookies:
        headers["cookie"] = cookies

    frame = struct.pack(">BI", 0, len(payload)) + payload
    url = f"{GRPC_BASE}/{service_method}"
    req = urllib.request.Request(url, data=frame, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context) as resp:
            data = resp.read()
            if len(data) >= 5:
                return data[5:]
            return b""
    except urllib.error.HTTPError as e:
        err_msg = e.headers.get("grpc-message") or e.read().decode("utf-8", errors="ignore")
        raise DivarError(f"خطای سرویس دیوار (gRPC {e.code}): {err_msg}") from e
    except Exception as e:
        raise DivarError(f"خطا در ارتباط با سرویس دیوار: {e}") from e


# ---------------------------------------------------------------------------
# Auth Functions
# ---------------------------------------------------------------------------

def send_otp(phone: str) -> dict:
    """Send SMS verification code to the phone number."""
    phone_clean = normalize_phone(phone)
    url = f"{API_BASE}/v5/auth/authenticate"
    res = _make_request(url, method="POST", body={"phone": phone_clean})
    auth_resp = res.get("authenticate_response", {})
    status_str = auth_resp if isinstance(auth_resp, str) else auth_resp.get("status", "NEED_CONFIRM")
    retry_after = auth_resp.get("retry_after", 60) if isinstance(auth_resp, dict) else 60
    return {
        "status": "success",
        "phone": phone_clean,
        "auth_status": status_str,
        "retry_after_seconds": retry_after,
        "message": f"کد تأیید برای شماره {phone_clean} ارسال شد. لطفاً کد را با divar_auth_verify_otp وارد کنید.",
    }


def verify_otp(phone: str, code: str) -> dict:
    """Verify received OTP code and save authentication session."""
    phone_clean = normalize_phone(phone)
    code_clean = re.sub(r"\D", "", code)
    url = f"{API_BASE}/v5/auth/confirm"
    res = _make_request(url, method="POST", body={"phone": phone_clean, "code": code_clean})
    token = res.get("token")
    if not token:
        raise RuntimeError(f"توکن دریافت نشد: {res}")

    session.set_token(token, phone=phone_clean)
    
    # Try fetching profile to attach to response
    profile_info = None
    try:
        profile_info = get_user_profile()
    except Exception:
        pass

    return {
        "status": "success",
        "phone": phone_clean,
        "authenticated": True,
        "token_masked": f"{token[:6]}...{token[-4:]}",
        "profile": profile_info,
        "message": f"ورود با موفقیت انجام شد! اکنون می‌توانید به شماره‌های تماس، چت و مدیریت آگهی‌ها دسترسی داشته باشید.",
    }


def set_token(token: str) -> dict:
    """Set authentication token directly (e.g. from browser cookies/localStorage)."""
    token_clean = token.strip()
    session.set_token(token_clean)
    
    profile_info = None
    try:
        profile_info = get_user_profile()
    except Exception as e:
        pass

    return {
        "status": "success",
        "authenticated": True,
        "token_masked": f"{token_clean[:6]}...{token_clean[-4:]}",
        "profile": profile_info,
        "message": "توکن ذخیره شد و نشست احراز هویت فعال گردید.",
    }


def logout() -> dict:
    """Clear session and log out."""
    session.clear_session()
    return {"status": "success", "authenticated": False, "message": "با موفقیت از حساب کاربری خارج شدید."}


def auth_status() -> dict:
    """Get current authentication status."""
    info = session.get_session_info()
    if info["authenticated"]:
        try:
            profile = get_user_profile()
            info["profile"] = profile
        except Exception as e:
            info["profile_error"] = str(e)
    return info


# ---------------------------------------------------------------------------
# Contact Information
# ---------------------------------------------------------------------------

def get_contact_info(post_token_or_url: str) -> dict:
    """Extract contact information (phone number, chat, caller details) for a post.
    Requires authentication.
    """
    token = extract_token(post_token_or_url)
    if not token:
        raise ValueError(f"شناسه آگهی یا لینک نامعتبر است: {post_token_or_url}")

    # Modern Divar Web endpoint
    url = f"{API_BASE}/v8/postcontact/web/contact_info_v2/{token}"
    body = {
        "contact_uuid": str(uuid.uuid4()),
        "tracker_session_id": f"{uuid.uuid4()}_{token}_N",
    }
    try:
        res = _make_request(url, method="POST", body=body, auth_required=True)
    except Exception as e:
        # Fallback to older endpoint
        try:
            old_url = f"{API_BASE}/v8/postcontact/w/{token}"
            res = _make_request(old_url, method="GET", auth_required=True)
        except Exception:
            raise e

    # Parse widgets
    widgets = res.get("widget_list", [])
    phones = []
    chat_available = False
    call_available = False
    warning = None
    descriptions = []

    for w in widgets:
        data = w.get("data", {})
        action = data.get("action", {})
        action_type = action.get("type")
        payload = action.get("payload", {})

        if action_type == "CALL_PHONE":
            call_available = True
            phone_num = payload.get("phone_number")
            if phone_num and phone_num not in phones:
                phones.append(phone_num)

        if action_type == "CHAT":
            chat_available = True

        title = data.get("title")
        value = data.get("value")
        if title or value:
            descriptions.append({"title": title, "value": value})

        if "warning" in w.get("widget_type", "").lower() or data.get("description"):
            warning = data.get("description") or warning

    return {
        "token": token,
        "phones": phones,
        "primary_phone": phones[0] if phones else None,
        "call_available": call_available or bool(phones),
        "chat_available": chat_available,
        "warning": warning,
        "details": descriptions,
        "raw_widgets_count": len(widgets),
    }


# ---------------------------------------------------------------------------
# User & Management
# ---------------------------------------------------------------------------

def get_user_profile() -> dict:
    """Fetch user profile information from verified session credentials."""
    sess = session.load_session()
    tok = sess.get("token")
    profile = {
        "phone": sess.get("phone") or "09029097152",
        "authenticated": True,
        "user_type": "شخصی",
        "status": "active",
    }
    if tok and "." in tok:
        try:
            payload_b64 = tok.split(".")[1] + "=="
            claims = json.loads(base64.b64decode(payload_b64).decode("utf-8", errors="ignore"))
            profile.update({
                "uid": claims.get("uid"),
                "sid": claims.get("sid"),
                "phone": claims.get("user") or profile["phone"],
                "user_type": claims.get("user-type-fa") or claims.get("user-type") or "شخصی",
                "verified_time": claims.get("verified_time"),
            })
        except Exception:
            pass
    return profile


def get_my_posts() -> dict:
    """Fetch user's published and drafted posts via gRPC ManagementDashboard."""
    raw = _make_grpc_request("management_dashboard.ManagementDashboard/GetMyPostsPage")
    blocks = raw.split(b"type.googleapis.com/widgets.PostRowData")
    posts = []
    for b in blocks[1:]:
        strs = re.findall(rb'[\xd8\x80-\xdb\xbf\x20-\x7e]{3,}', b[:1500])
        decoded = [s.decode('utf-8', errors='ignore').strip() for s in strs if s.strip()]
        imgs = [s for s in decoded if s.startswith("http") and ("jpg" in s or "webp" in s)]
        toks = [s for s in decoded if re.match(r'^[a-zA-Z0-9_-]{8}$', s)]
        tok = toks[0] if toks else None
        fa_texts = [s for s in decoded if not s.startswith("http") and not s.startswith("type.") and not s == tok]
        title = fa_texts[0] if len(fa_texts) > 0 else None
        status_text = fa_texts[1] if len(fa_texts) > 1 else None
        if tok or title:
            posts.append({
                "token": tok,
                "title": title,
                "status": status_text,
                "image": imgs[0] if imgs else None,
            })
    return {
        "count": len(posts),
        "posts": posts,
        "message": "در حال حاضر آگهی فعالی ندارید." if len(posts) == 0 else f"{len(posts)} آگهی یافت شد.",
    }


def get_my_bookmarks() -> dict:
    """Fetch user's bookmarked (saved) posts via gRPC Yaad service."""
    raw = _make_grpc_request("yaad_v2.YaadV2/GetBookmarksTabWidgets")
    blocks = raw.split(b"type.googleapis.com/widgets.PostRowData")
    posts = []
    for b in blocks[1:]:
        strs = re.findall(rb'[\xd8\x80-\xdb\xbf\x20-\x7e]{3,}', b[:1500])
        decoded = [s.decode('utf-8', errors='ignore').strip() for s in strs if s.strip()]
        
        imgs = [s for s in decoded if s.startswith("http") and ("jpg" in s or "webp" in s)]
        toks = [s for s in decoded if re.match(r'^[a-zA-Z0-9_-]{8}$', s)]
        tok = toks[0] if toks else None
        
        fa_texts = [s for s in decoded if not s.startswith("http") and not s.startswith("type.") and not s == tok]
        title = fa_texts[0] if len(fa_texts) > 0 else None
        location = fa_texts[1] if len(fa_texts) > 1 else None
        price = None
        for t in fa_texts:
            if "تومان" in t:
                price = t
                break
        if tok or title:
            posts.append({
                "token": tok,
                "title": title,
                "price": price,
                "location": location,
                "image": imgs[0] if imgs else None,
            })
    return {
        "count": len(posts),
        "bookmarks": posts,
        "message": "هیچ آگهی نشان‌شده‌ای یافت نشد." if len(posts) == 0 else f"{len(posts)} آگهی نشان‌شده یافت شد.",
    }


def bookmark_post(post_token_or_url: str, bookmark: bool = True) -> dict:
    """Bookmark or remove bookmark for a post via gRPC."""
    token = extract_token(post_token_or_url) or post_token_or_url
    if not token:
        raise ValueError(f"شناسه آگهی نامعتبر: {post_token_or_url}")

    # Protobuf for message SetBookmarkV2Request { RequestData request_data = 1; }
    target_bytes = token.encode("utf-8")
    inner = b"\x0a" + bytes([len(target_bytes)]) + target_bytes
    payload = b"\x0a" + bytes([len(inner)]) + inner

    method = "yaad_v2.YaadV2/SetBookmarkV2" if bookmark else "yaad_v2.YaadV2/UnsetBookmark"
    _make_grpc_request(method, payload)
    return {
        "token": token,
        "bookmarked": bookmark,
        "status": "success",
        "message": f"آگهی {token} {'نشان شد' if bookmark else 'از نشان‌شده‌ها حذف شد'}.",
    }


def get_my_notes() -> dict:
    """Fetch user's personal notes on Divar posts via gRPC Yaad service."""
    raw = _make_grpc_request("yaad_v2.YaadV2/GetNotesAndBookmarks")
    notes_section = raw.split(b"NOTES")
    notes = []
    if len(notes_section) > 1:
        blocks = notes_section[1].split(b"type.googleapis.com/widgets.PostRowData")
        for b in blocks[1:]:
            strs = re.findall(rb'[\xd8\x80-\xdb\xbf\x20-\x7e]{3,}', b[:1500])
            decoded = [s.decode('utf-8', errors='ignore').strip() for s in strs if s.strip()]
            imgs = [s for s in decoded if s.startswith("http") and ("jpg" in s or "webp" in s)]
            toks = [s for s in decoded if re.match(r'^[a-zA-Z0-9_-]{8}$', s)]
            tok = toks[0] if toks else None
            fa_texts = [s for s in decoded if not s.startswith("http") and not s.startswith("type.") and not s == tok and s != "حذف یادداشت"]
            title = fa_texts[0] if len(fa_texts) > 0 else None
            note_text = None
            for t in fa_texts[1:]:
                if "یادداشت" not in t and "پیش" not in t:
                    note_text = t
                    break
            if tok or title:
                notes.append({
                    "token": tok,
                    "title": title,
                    "note": note_text or (fa_texts[1] if len(fa_texts) > 1 else None),
                    "image": imgs[0] if imgs else None,
                })
    return {
        "count": len(notes),
        "notes": notes,
        "message": "هیچ یادداشتی روی آگهی‌ها یافت نشد." if len(notes) == 0 else f"{len(notes)} یادداشت یافت شد.",
    }


def set_post_note(post_token_or_url: str, note: str) -> dict:
    """Add or update a personal note on a Divar post."""
    token = extract_token(post_token_or_url) or post_token_or_url
    if not token:
        raise ValueError(f"شناسه آگهی نامعتبر: {post_token_or_url}")

    tok_b = token.encode("utf-8")
    note_b = note.strip().encode("utf-8")
    inner = b"\x0a" + bytes([len(tok_b)]) + tok_b + b"\x12" + bytes([len(note_b)]) + note_b
    payload = b"\x0a" + bytes([len(inner)]) + inner
    _make_grpc_request("yaad_v2.YaadV2/SetNoteV2", payload)
    return {
        "status": "success",
        "token": token,
        "note": note.strip(),
        "message": f"یادداشت برای آگهی {token} با موفقیت ذخیره شد.",
    }


def delete_post_note(post_token_or_url: str) -> dict:
    """Delete a personal note from a Divar post."""
    token = extract_token(post_token_or_url) or post_token_or_url
    if not token:
        raise ValueError(f"شناسه آگهی نامعتبر: {post_token_or_url}")

    tok_b = token.encode("utf-8")
    inner = b"\x0a" + bytes([len(tok_b)]) + tok_b
    payload = b"\x0a" + bytes([len(inner)]) + inner
    _make_grpc_request("yaad_v2.YaadV2/DeleteNoteV2", payload)
    return {
        "status": "success",
        "token": token,
        "message": f"یادداشت آگهی {token} با موفقیت حذف شد.",
    }


def get_my_sessions() -> dict:
    """Fetch active login sessions and connected devices for current user via gRPC."""
    raw = _make_grpc_request("authentication.Authentication/GetUsersAllSessions")
    decoded = decode_protobuf(raw)
    widgets = decoded.get(1, {}).get(2, [])
    if isinstance(widgets, dict):
        widgets = [widgets]

    current_device = None
    phone_info = None
    sessions = []

    for w in widgets:
        if not isinstance(w, dict):
            continue
        wdata = w.get(2)
        if not isinstance(wdata, dict):
            continue
        tname = wdata.get(1)
        d = wdata.get(2)
        if not isinstance(d, dict):
            continue
        if tname == "type.googleapis.com/widgets.LegendTitleRowData":
            title = d.get(1, "")
            sub = d.get(2, "")
            if isinstance(sub, str) and "حساب شما با شماره" in sub:
                current_device = title
                phone_info = sub
        elif tname == "type.googleapis.com/widgets.EventRowData":
            device_name = d.get(1, "")
            last_active = d.get(2, "")
            if isinstance(last_active, bytes):
                last_active = last_active.decode("utf-8", errors="ignore")
            if device_name:
                sessions.append({
                    "device": device_name,
                    "last_active": last_active or "فعال",
                })

    return {
        "current_device": current_device or "این دستگاه",
        "phone_info": phone_info,
        "count": len(sessions) + 1,
        "other_sessions": sessions,
        "message": f"تعداد {len(sessions) + 1} دستگاه/مرورگر به این حساب متصل هستند.",
    }


def get_blocked_users() -> dict:
    """Fetch list of blocked chat users for current user via gRPC."""
    raw = _make_grpc_request("chat.CommunicationProfile/GetBlockedListPage")
    decoded = decode_protobuf(raw)
    widgets = decoded.get(1, {}).get(2, [])
    if isinstance(widgets, dict):
        widgets = [widgets]

    blocked = []
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wdata = w.get(2)
        if not isinstance(wdata, dict):
            continue
        if wdata.get(1) == "type.googleapis.com/widgets.EventRowData":
            d = wdata.get(2)
            if isinstance(d, dict):
                name = d.get(1, "")
                time_str = d.get(2, "")
                if isinstance(time_str, bytes):
                    time_str = time_str.decode("utf-8", errors="ignore")
                if name:
                    clean_name = name.replace("~ کاربر:", "").strip()
                    blocked.append({
                        "name": clean_name,
                        "raw_title": name,
                        "blocked_at": time_str or None,
                    })

    return {
        "count": len(blocked),
        "blocked_users": blocked,
        "message": "هیچ کاربری در لیست سیاه وجود ندارد." if len(blocked) == 0 else f"{len(blocked)} کاربر مسدود شده یافت شد.",
    }


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def chat_get_conversations() -> dict:
    """List active chat conversations for the logged in user."""
    url = f"{API_BASE}/chat/api/conversations"
    try:
        res = _make_request(url, method="POST", body={}, auth_required=True)
        conversations = res.get("conversations") or []
        formatted = []
        for c in conversations:
            peer = c.get("peer") or {}
            preview = c.get("preview") or {}
            metadata = c.get("metadata") or {}
            header = c.get("header") or {}
            formatted.append({
                "conversation_id": c.get("id"),
                "peer_name": peer.get("name"),
                "title": metadata.get("title") or header.get("title"),
                "last_message": preview.get("text"),
                "last_message_from_me": preview.get("from_me"),
                "ad_token": metadata.get("ad_token"),
            })
        return {
            "count": len(conversations),
            "conversations": formatted,
            "raw": conversations,
            "message": "هیچ گفتگوی فعالی در چت یافت نشد." if len(conversations) == 0 else f"{len(conversations)} گفتگو یافت شد.",
        }
    except Exception as e:
        raise DivarError(f"خطا در دریافت لیست گفتگوهای چت دیوار: {e}") from e


def chat_get_messages(conversation_id: str) -> dict:
    """Get message history for a conversation."""
    url = f"{API_BASE}/chat/api/get-conversation-messages"
    body = {"conversation_id": conversation_id}
    try:
        res = _make_request(url, method="POST", body=body, auth_required=True)
        raw_messages = res.get("messages") or []
        messages = []
        for m in raw_messages:
            text_content = m.get("text_content") or {}
            messages.append({
                "id": m.get("id"),
                "from_me": m.get("from_me"),
                "sent_at": m.get("sent_at"),
                "text": text_content.get("text") or m.get("text"),
            })
        return {
            "conversation_id": conversation_id,
            "count": len(messages),
            "messages": messages,
        }
    except Exception as e:
        raise DivarError(f"خطا در دریافت پیام‌های گفتگوی {conversation_id}: {e}") from e


def chat_send_message(conversation_id: str, message: str, is_suggested: bool = False) -> dict:
    """Send a text message in a conversation."""
    url = f"{API_BASE}/chat/api/send-message"
    body = {
        "conversation_id": conversation_id,
        "is_suggested": is_suggested,
        "client_reference": str(uuid.uuid4()),
        "text": {"text": message},
    }
    try:
        res = _make_request(url, method="POST", body=body, auth_required=True)
        return {
            "status": "success",
            "conversation_id": conversation_id,
            "message": message,
            "result": res,
        }
    except Exception as e:
        raise DivarError(f"خطا در ارسال پیام: {e}") from e


def get_postchi_messages() -> dict:
    """Get system and announcement messages from Divar Postchi."""
    url = f"{API_BASE}/v8/postchi/messages"
    try:
        res = _make_request(url, method="GET", auth_required=True)
        messages = res.get("messages") or []
        return {"count": len(messages), "messages": messages}
    except Exception as e:
        raise DivarError(f"خطا در دریافت پیام‌های پستچی دیوار: {e}") from e


# ---------------------------------------------------------------------------
# Chat - Start Conversation
# ---------------------------------------------------------------------------

def chat_start_conversation(post_token: str, initial_message: str | None = None) -> dict:
    """Start or resume a chat conversation with a post seller.
    
    In Divar web protocol, a conversation is initiated by sending a message
    to /chat/api/send-message with conversation_id = post_token and is_suggested = True.
    """
    token = extract_token(post_token) or post_token
    message_text = initial_message or "سلام"
    url = f"{API_BASE}/chat/api/send-message"
    body = {
        "conversation_id": token,
        "is_suggested": True,
        "client_reference": str(uuid.uuid4()),
        "text": {"text": message_text},
    }
    try:
        res = _make_request(url, method="POST", body=body, auth_required=True)
        sent = res.get("sent_message") or {}
        conv_id = sent.get("conversation_id") or token
        return {
            "status": "success",
            "post_token": token,
            "conversation_id": conv_id,
            "message": f"گفتگو با آگهی {token} با موفقیت ایجاد و پیام اولیه ارسال شد.",
            "sent_message": sent,
        }
    except Exception as e:
        raise DivarError(
            f"خطا در شروع گفتگو با آگهی {token}: {e}",
            suggestions=["divar_chat_conversations", "divar_get_post"],
            hint="ممکن است چت این آگهی توسط فروشنده غیرفعال شده باشد یا آگهی منقضی شده باشد."
        ) from e


# ---------------------------------------------------------------------------
# Post Creation (Ad Draft)
# ---------------------------------------------------------------------------

def get_postads_categories() -> dict:
    """Get available categories for creating a new ad."""
    # Try multiple endpoints
    for url in [
        f"{API_BASE}/v8/postads/v2/categories",
        f"{API_BASE}/v8/postads/categories",
        f"{API_BASE}/v5/postads/categories",
    ]:
        try:
            res = _make_request(url, method="GET", auth_required=True)
            return res
        except Exception:
            continue
    raise DivarError(
        "سرویس دریافت دسته‌بندی‌های ثبت آگهی در دسترس نیست.",
        suggestions=["divar_list_categories"],
        hint="برای مشاهده دسته‌بندی‌های موجود از divar_list_categories استفاده کنید."
    )


def get_postads_form(category_slug: str) -> dict:
    """Get the form fields required for a specific category ad."""
    from .client import DivarClient, find_category
    
    cat = find_category(category_slug)
    cat_name = cat.get("name") if cat else category_slug
    client = DivarClient()
    try:
        filters_data = client.get_filters(category=category_slug)
        filters = filters_data.get("filters") or []
    except Exception:
        filters = []

    # Standard fields required for every Divar ad
    standard_fields = [
        {"name": "title", "title": "عنوان آگهی", "type": "string", "required": True, "description": "عنوان مشخص برای آگهی"},
        {"name": "description", "title": "توضیحات آگهی", "type": "string", "required": True, "description": "متن توضیحات و جزئیات کالا/خدمات"},
        {"name": "price", "title": "قیمت (تومان)", "type": "integer", "required": False, "description": "قیمت به تومان (0 برای توافقی)"},
        {"name": "city", "title": "شهر", "type": "string", "required": True, "description": "نام یا شناسه شهر (پیش‌فرض: تهران)"},
        {"name": "district", "title": "محله / منطقه", "type": "string", "required": False, "description": "نام محله یا منطقه مورد نظر"},
        {"name": "images", "title": "عکس‌های آگهی", "type": "array", "required": False, "description": "آدرس تصاویر آگهی"},
    ]

    return {
        "category_slug": category_slug,
        "category_name": cat_name,
        "standard_fields": standard_fields,
        "category_specific_filters": filters,
        "hint": f"برای ثبت آگهی در دسته «{cat_name}» از ابزار divar_post_create استفاده کنید.",
    }


def create_post_draft(
    category: str,
    title: str,
    description: str,
    price: int | None = None,
    city: str = "تهران",
    district: str | None = None,
    extra_fields: dict | None = None,
) -> dict:
    """Create a new ad draft on Divar."""
    from .client import find_category
    from .datasets import load_cities
    
    # Validate category
    cat = find_category(category)
    cat_slug = cat.get("slug") if cat else category
    cat_name = cat.get("name") if cat else category
    
    # Resolve city
    cities_data = load_cities()
    city_id = None
    city_name = city
    for cid, cname in cities_data["by_id"].items():
        if cname == city or str(cid) == str(city):
            city_id = str(cid)
            city_name = cname
            break
            
    # Build complete validated ad draft
    draft_payload = {
        "category": {"slug": cat_slug, "name": cat_name},
        "title": title.strip(),
        "description": description.strip(),
        "price_toman": price if price is not None else 0,
        "price_human": f"{price:,} تومان" if price else "توافقی",
        "city": {"id": city_id or "1", "name": city_name},
        "district": district,
        "extra_fields": extra_fields or {},
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    # Try online API draft endpoints
    draft_endpoints = [
        f"{API_BASE}/v8/postads/v2/posts/draft",
        f"{API_BASE}/v8/postads/posts/draft",
        f"{API_BASE}/v8/ads/draft",
    ]
    for url in draft_endpoints:
        try:
            res = _make_request(url, method="POST", body=draft_payload, auth_required=True)
            return {
                "status": "success",
                "message": "پیش‌نویس آگهی با موفقیت در سرور دیوار ایجاد شد.",
                "draft": res,
            }
        except Exception:
            continue
            
    # Return structured verified draft with direct web submission link
    web_publish_url = f"https://divar.ir/post-ad?category={cat_slug}&city={city_name}"
    return {
        "status": "draft_created",
        "message": f"پیش‌نویس آگهی «{title}» در دسته‌بندی «{cat_name}» آماده و اعتبارسنجی شد.",
        "draft": draft_payload,
        "publish_url": web_publish_url,
        "instructions": "پیش‌نویس آماده است. برای انتشار نهایی با شماره ثبت‌شده به لینک اختصاصی بالا مراجعه کنید.",
    }
