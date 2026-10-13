/**
 * Torob (ترب) API Client for Cloudflare Workers
 */

export const TOROB_API_BASE = "https://api.torob.com/v4";
export const TOROB_WEB_BASE = "https://torob.com";
export const DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

export const TOROB_CATEGORIES = [
  { id: 94, name_fa: "موبایل و تبلت", name_en: "Mobile & Tablet", slug: "mobile-phone" },
  { id: 99, name_fa: "لپ‌تاپ و کامپیوتر", name_en: "Laptops & Computers", slug: "laptop" },
  { id: 104, name_fa: "هدفون، هدست و هندزفری", name_en: "Headphones & Audio", slug: "headphone" },
  { id: 80, name_fa: "لوازم خانگی", name_en: "Home Appliances", slug: "home-appliances" },
  { id: 257, name_fa: "صوتی و تصویری", name_en: "TV & Audio", slug: "tv-audio" },
  { id: 180, name_fa: "آرایشی و بهداشتی", name_en: "Beauty & Health", slug: "beauty-health" },
  { id: 310, name_fa: "مد و پوشاک", name_en: "Fashion & Clothing", slug: "fashion" },
  { id: 450, name_fa: "ابزارآلات و صنعتی", name_en: "Tools & Industrial", slug: "tools" },
  { id: 520, name_fa: "خودرو و لوازم یدکی", name_en: "Car & Vehicle Parts", slug: "car-parts" },
  { id: 610, name_fa: "کتاب و لوازم تحریر", name_en: "Books & Stationery", slug: "stationery" },
  { id: 700, name_fa: "کالاهای سوپرمارکتی", name_en: "Supermarket & Groceries", slug: "supermarket" },
];

function getHeaders(): Record<string, string> {
  return {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
  };
}

export async function searchProducts(query: string, page = 1, priceMin?: number, priceMax?: number): Promise<any> {
  if (!query || !query.trim()) return { count: 0, results: [] };
  const cleanQ = query.trim();

  const params = new URLSearchParams();
  params.set("q", cleanQ);
  params.set("page", String(page));
  if (priceMin != null) params.set("price__gte", String(priceMin));
  if (priceMax != null) params.set("price__lte", String(priceMax));

  const url = `${TOROB_API_BASE}/base-product/search/?${params.toString()}`;
  const resp = await fetch(url, { headers: getHeaders() });
  const data = await resp.json() as any;

  const rawList = data?.results || [];
  const items: any[] = [];

  for (const it of rawList) {
    items.push({
      prk: it.random_key,
      title: it.name1 || it.name2,
      title_en: it.name2,
      price: it.price || 0,
      price_text: it.price_text || (it.price ? `${Number(it.price).toLocaleString()} تومان` : "ناموجود"),
      shops_count: it.num_shops || it.shops_count || 1,
      image_url: it.image_url,
      category_id: it.category_id,
      torob_url: it.web_client_absolute_url || `${TOROB_WEB_BASE}/p/${it.random_key}/`,
      badges: it.badges || [],
    });
  }

  return {
    query: cleanQ,
    page,
    count: data?.count || items.length,
    max_pages: data?.max_pages || 1,
    results: items,
  };
}

export async function getProductDetails(prk: string): Promise<any> {
  if (!prk) return { error: "Missing prk" };
  const cleanPrk = prk.trim();
  const url = `${TOROB_API_BASE}/base-product/details-log-click/?prk=${cleanPrk}`;

  const resp = await fetch(url, { headers: getHeaders() });
  if (!resp.ok) {
    return { error: `Product details error (${resp.status})`, prk: cleanPrk };
  }

  const data = await resp.json() as any;

  // Extract sellers & shops
  const sellersRaw = data?.products_info?.result || data?.sellers || [];
  const sellers: any[] = [];

  for (const s of sellersRaw) {
    sellers.push({
      shop_id: s.shop_id,
      shop_name: s.shop_name,
      shop_name_en: s.shop_name_en,
      shop_score: s.shop_score || 0,
      price: s.price || 0,
      price_text: s.price_text || (s.price ? `${Number(s.price).toLocaleString()} تومان` : "ناموجود"),
      city: s.city_name || "ایران",
      warranty: s.warranty,
      is_available: s.is_available !== false,
      buy_url: s.page_url ? (s.page_url.startsWith("http") ? s.page_url : `${TOROB_WEB_BASE}${s.page_url}`) : null,
      last_price_change: s.last_price_change_date,
    });
  }

  // Sort sellers by price ascending
  sellers.sort((a, b) => (a.price || 0) - (b.price || 0));

  return {
    prk: cleanPrk,
    title: data?.name1 || data?.name2,
    title_en: data?.name2,
    description: data?.description || "",
    min_price: data?.price || (sellers.length ? sellers[0].price : 0),
    min_price_text: data?.price_text || (sellers.length ? sellers[0].price_text : "ناموجود"),
    max_price: sellers.length ? sellers[sellers.length - 1].price : data?.price,
    shops_count: sellers.length || data?.num_shops || 0,
    image_url: data?.image_url,
    category_id: data?.category_id,
    category_name: data?.category_name,
    specs: data?.attributes || [],
    sellers,
    torob_url: `${TOROB_WEB_BASE}/p/${cleanPrk}/`,
  };
}

export async function getPriceChart(prk: string): Promise<any> {
  if (!prk) return { error: "Missing prk" };
  const cleanPrk = prk.trim();
  const url = `${TOROB_API_BASE}/base-product/price-chart/?prk=${cleanPrk}`;

  const resp = await fetch(url, { headers: getHeaders() });
  if (!resp.ok) {
    return { error: `Price chart error (${resp.status})`, prk: cleanPrk };
  }

  const data = await resp.json() as any;
  const history = (data?.chart || data?.history || []).map((pt: any) => ({
    date: pt.date || pt.time,
    price: pt.price,
    price_formatted: `${Number(pt.price || 0).toLocaleString()} تومان`,
  }));

  return {
    prk: cleanPrk,
    chart_points_count: history.length,
    min_price_seen: data?.min_price || 0,
    max_price_seen: data?.max_price || 0,
    history,
  };
}

export async function searchSuggestions(query: string): Promise<any> {
  if (!query || !query.trim()) return [];
  const url = `${TOROB_API_BASE}/suggestion/search/?q=${encodeURIComponent(query.trim())}`;
  const resp = await fetch(url, { headers: getHeaders() });
  const data = await resp.json() as any;
  return data?.results || [];
}

export async function getSpecialOffers(page = 1): Promise<any> {
  const url = `${TOROB_API_BASE}/special-offers/?page=${page}`;
  const resp = await fetch(url, { headers: getHeaders() });
  const data = await resp.json() as any;
  return {
    count: data?.count || 0,
    results: (data?.results || []).map((it: any) => ({
      prk: it.random_key,
      title: it.name1 || it.name2,
      price: it.price,
      price_text: it.price_text,
      discount_percent: it.discount_percent,
      image_url: it.image_url,
      torob_url: `${TOROB_WEB_BASE}/p/${it.random_key}/`,
    })),
  };
}

export async function compareStores(prk: string): Promise<any> {
  const details = await getProductDetails(prk);
  if (details.error) return details;

  const sellers = details.sellers || [];
  if (!sellers.length) {
    return {
      title: details.title,
      prk,
      message: "هیچ فروشگاهی در حال حاضر این کالا را موجود ندارد.",
    };
  }

  const cheapest = sellers[0];
  const mostExpensive = sellers[sellers.length - 1];
  const bestRated = [...sellers].sort((a, b) => (b.shop_score || 0) - (a.shop_score || 0))[0];

  const priceDiff = (mostExpensive.price || 0) - (cheapest.price || 0);
  const diffPercent = cheapest.price > 0 ? Number(((priceDiff / cheapest.price) * 100).toFixed(1)) : 0;

  return {
    product_title: details.title,
    prk,
    total_stores: sellers.length,
    cheapest_store: {
      shop_name: cheapest.shop_name,
      price: cheapest.price,
      price_text: cheapest.price_text,
      warranty: cheapest.warranty,
      city: cheapest.city,
      score: cheapest.shop_score,
      buy_url: cheapest.buy_url,
    },
    best_rated_store: {
      shop_name: bestRated.shop_name,
      score: bestRated.shop_score,
      price: bestRated.price_text,
      buy_url: bestRated.buy_url,
    },
    price_range: {
      min: cheapest.price_text,
      max: mostExpensive.price_text,
      difference_toman: `${priceDiff.toLocaleString()} تومان`,
      savings_percentage: `${diffPercent}% اختلاف بین ارزان‌ترین و گران‌ترین فروشنده`,
    },
    top_5_stores: sellers.slice(0, 5),
  };
}

export async function appraiseDeal(prk: string): Promise<any> {
  const details = await getProductDetails(prk);
  if (details.error) return details;

  const sellers = details.sellers || [];
  const minPrice = details.min_price || 0;
  const shopsCount = details.shops_count || 0;

  // Calculate competition score (0-40)
  let competitionScore = 20.0;
  if (shopsCount >= 20) competitionScore = 40.0;
  else if (shopsCount >= 10) competitionScore = 32.0;
  else if (shopsCount >= 4) competitionScore = 25.0;
  else competitionScore = 15.0;

  // Calculate pricing transparency score (0-40)
  let transparencyScore = 30.0;
  const priceDiff = sellers.length > 1 ? (sellers[sellers.length - 1].price - sellers[0].price) : 0;
  if (sellers.length > 1 && sellers[0].price > 0) {
    const spreadPercent = (priceDiff / sellers[0].price) * 100;
    if (spreadPercent > 15) transparencyScore = 40.0; // High savings opportunity found by Torob!
  }

  // Seller reliability factor (0-20)
  const avgScore = sellers.length ? sellers.reduce((acc, s) => acc + (s.shop_score || 0), 0) / sellers.length : 0;
  const reliabilityScore = Number((avgScore * 4).toFixed(1));

  const totalScore = Number(Math.min(100.0, competitionScore + transparencyScore + reliabilityScore).toFixed(1));

  let verdict = "Fair Deal (معامله منصفانه)";
  if (totalScore >= 85) verdict = "High Savings Opportunity (تنوع فروشنده و اختلاف قیمت بالا - خرید به شدت به‌صرفه)";
  else if (totalScore >= 70) verdict = "Good Deal (خرید مطمئن و رقابتی)";
  else if (totalScore < 50) verdict = "Limited Sellers (تعداد فروشندگان محدود - ممکن است در آینده تخفیف بیشتری بخورد)";

  return {
    prk,
    title: details.title,
    min_price: details.min_price_text,
    shops_count: shopsCount,
    deal_score: totalScore,
    verdict,
    recommendation: shopsCount > 3 ? "پیشنهاد می‌شود از ارزان‌ترین فروشنده با امتیاز بالا خرید نمایید." : "با توجه به کم بودن فروشندگان، قیمت‌ها را با بازار حضوری نیز مقایسه فرمایید.",
  };
}

export function listCategories() {
  return TOROB_CATEGORIES;
}
