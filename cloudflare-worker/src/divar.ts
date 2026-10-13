import { decodeGrpcFrame, decodeProtobuf, encodeGrpcFrame } from "./proto";
import citiesData from "./data/cities.json";
import categoriesData from "./data/categories.json";

export interface Env {
  DIVAR_TOKEN?: string;
  DIVAR_COOKIES?: string;
  DIVAR_PHONE?: string;
}

const API_BASE = "https://api.divar.ir";
const GRPC_BASE = "https://grpc-api.divar.ir";

const DEFAULT_HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
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
};

export function extractToken(input: string): string {
  if (!input) return "";
  const match = input.match(/\/v\/[^\/]+\/([a-zA-Z0-9_-]+)/);
  if (match) return match[1];
  const cleaned = input.trim().replace(/^.*[\/=]/, "");
  return cleaned;
}

export function resolveCityId(query: string = "tehran"): string {
  const q = query.trim().toLowerCase();
  const cities = citiesData as Record<string, string>;
  if (cities[q]) return cities[q];
  for (const [name, id] of Object.entries(cities)) {
    if (name.toLowerCase() === q || name === query) return id;
  }
  return "1"; // Default Tehran
}

// ---------------------------------------------------------------------------
// gRPC Request Helper
// ---------------------------------------------------------------------------

async function makeGrpcRequest(serviceMethod: string, payload: Uint8Array = new Uint8Array(), env?: Env): Promise<Uint8Array> {
  const token = env?.DIVAR_TOKEN;
  const frame = encodeGrpcFrame(payload);

  const headers: Record<string, string> = {
    "Content-Type": "application/grpc",
    "User-Agent": "Divar/11.16.0 (Android; 13)",
    "te": "trailers",
  };
  if (token) {
    headers["authorization"] = `Basic ${token}`;
  }

  const res = await fetch(`${GRPC_BASE}/${serviceMethod}`, {
    method: "POST",
    headers,
    body: frame,
  });

  if (!res.ok) {
    throw new Error(`gRPC ${serviceMethod} returned HTTP ${res.status}`);
  }

  const rawBytes = new Uint8Array(await res.arrayBuffer());
  return decodeGrpcFrame(rawBytes);
}

// ---------------------------------------------------------------------------
// Search & Public Listings
// ---------------------------------------------------------------------------

export async function search(params: {
  query?: string;
  city?: string;
  category?: string;
  price_min?: number;
  price_max?: number;
}) {
  const cityId = resolveCityId(params.city);
  const formData: Record<string, any> = {};

  if (params.category && params.category.toUpperCase() !== "ROOT") {
    formData["category"] = { str: { value: params.category } };
  }
  if (params.price_min !== undefined || params.price_max !== undefined) {
    const rng: Record<string, number> = {};
    if (params.price_min !== undefined) rng["minimum"] = params.price_min;
    if (params.price_max !== undefined) rng["maximum"] = params.price_max;
    formData["price"] = { number_range: rng };
  }

  const searchData: Record<string, any> = {};
  if (params.query) searchData["query"] = params.query;
  if (Object.keys(formData).length > 0) {
    searchData["form_data"] = { data: formData };
  }

  const payload: Record<string, any> = {
    city_ids: [cityId],
    pagination_data: {
      "@type": "type.googleapis.com/post_list.PaginationData",
      page: 1,
      page_size: 24,
    },
  };
  if (Object.keys(searchData).length > 0) {
    payload["search_data"] = searchData;
  }

  const res = await fetch(`${API_BASE}/v8/postlist/w/search`, {
    method: "POST",
    headers: DEFAULT_HEADERS,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Search request failed with status ${res.status}`);
  }

  const data = (await res.json()) as any;
  const widgets = data?.list_widgets || [];
  const posts: any[] = [];

  for (const w of widgets) {
    if (w.widget_type === "POST_ROW" && w.data) {
      const d = w.data;
      const payloadAction = (d.action || {}).payload || {};
      const token = d.token || payloadAction.token || "";
      posts.push({
        token,
        title: d.title,
        top_description_text: d.top_description_text,
        middle_description_text: d.middle_description_text,
        bottom_description_text: d.bottom_description_text,
        image_url: d.image_url?.[0]?.src || d.image || null,
        district: d.district || payloadAction.web_info?.district_persian || null,
        city: params.city || payloadAction.web_info?.city_persian || "تهران",
        url: `https://divar.ir/v/${token}`,
      });
    }
  }

  return {
    count: posts.length,
    city: params.city || "تهران",
    posts,
  };
}

export async function getPost(postTokenOrUrl: string) {
  const token = extractToken(postTokenOrUrl);
  if (!token) throw new Error("Invalid post token or URL");

  const res = await fetch(`${API_BASE}/v8/posts-v2/web/${token}`, {
    headers: DEFAULT_HEADERS,
  });

  if (!res.ok) {
    throw new Error(`Post ${token} not found (status ${res.status})`);
  }

  const data = (await res.json()) as any;
  const sections = data?.sections || [];
  let title = null;
  let description = null;
  const images: string[] = [];
  const attributes: Record<string, any> = {};

  for (const sec of sections) {
    for (const w of sec?.widgets || []) {
      if (w.widget_type === "TITLE_ROW") {
        title = w.data?.title || title;
      } else if (w.widget_type === "DESCRIPTION_ROW") {
        description = w.data?.text || description;
      } else if (w.widget_type === "IMAGE_CAROUSEL") {
        for (const it of w.data?.items || []) {
          if (it.image?.url) images.push(it.image.url);
        }
      } else if (w.widget_type === "GROUP_INFO_ROW") {
        for (const it of w.data?.items || []) {
          if (it.title && it.value) attributes[it.title] = it.value;
        }
      }
    }
  }

  return {
    token,
    title,
    description,
    images,
    attributes,
    url: `https://divar.ir/v/${token}`,
  };
}

// ---------------------------------------------------------------------------
// Contact extraction
// ---------------------------------------------------------------------------

export async function getContact(postTokenOrUrl: string, env: Env) {
  const token = extractToken(postTokenOrUrl);
  if (!token) throw new Error("Invalid post token or URL");

  const headers: Record<string, string> = { ...DEFAULT_HEADERS };
  if (env.DIVAR_COOKIES) headers["Cookie"] = env.DIVAR_COOKIES;
  if (env.DIVAR_TOKEN) headers["Authorization"] = `Basic ${env.DIVAR_TOKEN}`;

  const res = await fetch(`${API_BASE}/v8/postcontact/web/contact_info_v2/${token}`, {
    method: "POST",
    headers,
    body: JSON.stringify({}),
  });

  if (!res.ok) {
    throw new Error(`Contact request failed with status ${res.status}`);
  }

  const data = (await res.json()) as any;
  const widgets = data?.widget_list || [];
  const phones: string[] = [];
  let chatAvailable = false;
  let callAvailable = false;

  for (const w of widgets) {
    const d = w.data || {};
    const title = d.title || "";
    const action = d.action || {};
    if (action.type === "CALL" || title.includes("تماس")) {
      callAvailable = true;
      if (action.payload?.phone_number) phones.push(action.payload.phone_number);
    }
    if (action.type === "CHAT" || title.includes("چت")) {
      chatAvailable = true;
    }
  }

  return {
    token,
    phones,
    primary_phone: phones[0] || null,
    call_available: callAvailable,
    chat_available: chatAvailable,
  };
}

// ---------------------------------------------------------------------------
// Account & Yaad (Bookmarks & Notes)
// ---------------------------------------------------------------------------

export async function getMyBookmarks(env: Env) {
  const raw = await makeGrpcRequest("yaad_v2.YaadV2/GetBookmarksTabWidgets", new Uint8Array(), env);
  const text = new TextDecoder("utf-8").decode(raw);
  const tokens = [...text.matchAll(/[a-zA-Z0-9_-]{8}/g)].map((m) => m[0]);
  const uniqueTokens = [...new Set(tokens)].filter((t) => !["widgets.", "PostRowD"].includes(t));

  return {
    count: uniqueTokens.length,
    bookmarks: uniqueTokens.map((t) => ({ token: t, url: `https://divar.ir/v/${t}` })),
  };
}

export async function bookmarkPost(postTokenOrUrl: string, bookmark: boolean, env: Env) {
  const token = extractToken(postTokenOrUrl);
  const tokenBytes = new TextEncoder().encode(token);
  // Protobuf SetBookmarkV2Request
  const inner = new Uint8Array(2 + tokenBytes.length);
  inner[0] = 0x0a;
  inner[1] = tokenBytes.length;
  inner.set(tokenBytes, 2);

  const payload = new Uint8Array(2 + inner.length);
  payload[0] = 0x0a;
  payload[1] = inner.length;
  payload.set(inner, 2);

  const method = bookmark ? "yaad_v2.YaadV2/SetBookmarkV2" : "yaad_v2.YaadV2/UnsetBookmark";
  await makeGrpcRequest(method, payload, env);

  return {
    token,
    bookmarked: bookmark,
    status: "success",
    message: bookmark ? `آگهی ${token} نشان شد.` : `آگهی ${token} از نشان‌ها حذف شد.`,
  };
}

export async function getMyNotes(env: Env) {
  const raw = await makeGrpcRequest("yaad_v2.YaadV2/GetNotesAndBookmarks", new Uint8Array(), env);
  const decoded = decodeProtobuf(raw);
  return {
    status: "success",
    raw_size: raw.length,
    message: "یادداشت‌های کاربر با موفقیت استخراج شدند.",
  };
}

export async function getMySessions(env: Env) {
  const raw = await makeGrpcRequest("authentication.Authentication/GetUsersAllSessions", new Uint8Array(), env);
  const decoded = decodeProtobuf(raw);
  const widgets = decoded[1]?.[2] || [];
  const list = Array.isArray(widgets) ? widgets : [widgets];

  let currentDevice = "این دستگاه";
  let phoneInfo = null;
  const sessions: any[] = [];

  for (const w of list) {
    const wdata = w?.[2];
    const type = wdata?.[1];
    const d = wdata?.[2];
    if (type === "type.googleapis.com/widgets.LegendTitleRowData") {
      if (typeof d?.[2] === "string" && d[2].includes("شماره")) {
        currentDevice = d[1] || currentDevice;
        phoneInfo = d[2];
      }
    } else if (type === "type.googleapis.com/widgets.EventRowData") {
      if (d?.[1]) {
        sessions.push({ device: d[1], last_active: d[2] || "فعال" });
      }
    }
  }

  return {
    current_device: currentDevice,
    phone_info: phoneInfo,
    count: sessions.length + 1,
    other_sessions: sessions,
  };
}

export async function getBlockedUsers(env: Env) {
  const raw = await makeGrpcRequest("chat.CommunicationProfile/GetBlockedListPage", new Uint8Array(), env);
  const decoded = decodeProtobuf(raw);
  const widgets = decoded[1]?.[2] || [];
  const list = Array.isArray(widgets) ? widgets : [widgets];

  const blocked: any[] = [];
  for (const w of list) {
    const wdata = w?.[2];
    if (wdata?.[1] === "type.googleapis.com/widgets.EventRowData") {
      const d = wdata[2];
      if (d?.[1]) {
        blocked.push({
          name: String(d[1]).replace("~ کاربر:", "").trim(),
          blocked_at: d[2] || null,
        });
      }
    }
  }

  return {
    count: blocked.length,
    blocked_users: blocked,
  };
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export async function getConversations(env: Env) {
  const headers: Record<string, string> = { ...DEFAULT_HEADERS };
  if (env.DIVAR_COOKIES) headers["Cookie"] = env.DIVAR_COOKIES;
  if (env.DIVAR_TOKEN) headers["Authorization"] = `Basic ${env.DIVAR_TOKEN}`;

  const res = await fetch(`${API_BASE}/chat/api/conversations`, {
    method: "POST",
    headers,
    body: JSON.stringify({}),
  });

  if (!res.ok) throw new Error(`Chat API error: status ${res.status}`);
  const data = (await res.json()) as any;
  const convs = data.conversations || [];

  return {
    count: convs.length,
    conversations: convs.map((c: any) => ({
      conversation_id: c.id,
      title: c.title,
      type: c.type,
      unread_count: c.unread_count || 0,
      post_token: c.post_token || null,
    })),
  };
}

export async function getMessages(conversationId: string, env: Env) {
  const headers: Record<string, string> = { ...DEFAULT_HEADERS };
  if (env.DIVAR_COOKIES) headers["Cookie"] = env.DIVAR_COOKIES;
  if (env.DIVAR_TOKEN) headers["Authorization"] = `Basic ${env.DIVAR_TOKEN}`;

  const res = await fetch(`${API_BASE}/chat/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers,
    body: JSON.stringify({}),
  });

  if (!res.ok) throw new Error(`Chat messages error: status ${res.status}`);
  const data = (await res.json()) as any;
  const msgs = data.messages || [];

  return {
    conversation_id: conversationId,
    count: msgs.length,
    messages: msgs.map((m: any) => ({
      id: m.id,
      text: m.text,
      sender: m.type === "sent" ? "me" : "other",
      sent_at: m.created_at,
    })),
  };
}

// ---------------------------------------------------------------------------
// Metadata & Status
// ---------------------------------------------------------------------------

export function listCities(query?: string) {
  const cities = citiesData as Record<string, string>;
  const list = Object.entries(cities).map(([name, id]) => ({ name, id }));
  if (!query) return { count: list.length, cities: list.slice(0, 50) };
  const filtered = list.filter((c) => c.name.includes(query) || c.id === query);
  return { count: filtered.length, cities: filtered };
}

export function listCategories(query?: string) {
  const cats = categoriesData as Array<{ slug: string; name: string }>;
  if (!query) return { count: cats.length, categories: cats.slice(0, 50) };
  const filtered = cats.filter((c) => c.slug.includes(query) || c.name.includes(query));
  return { count: filtered.length, categories: filtered };
}
