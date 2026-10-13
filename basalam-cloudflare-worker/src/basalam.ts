/**
 * Basalam (باسلام) API Client & Market Intelligence for Cloudflare Workers
 */

export const BASALAM_SEARCH_BASE = "https://search.basalam.com";
export const BASALAM_CORE_BASE = "https://core.basalam.com";
export const BASALAM_API_BASE = "https://api.basalam.com";
export const BASALAM_WEB_BASE = "https://basalam.com";
export const DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

export const BASALAM_CATEGORIES = [
  { id: "food-beverage", name_fa: "مواد غذایی و خوراکی", name_en: "Food & Groceries" },
  { id: "handicrafts", name_fa: "صنایع دستی و سنتی", name_en: "Handicrafts & Traditional Art" },
  { id: "clothing", name_fa: "پوشاک زنانه، مردانه و کودک", name_en: "Fashion & Apparel" },
  { id: "beauty-health", name_fa: "آرایشی، بهداشتی و طب سنتی", name_en: "Beauty & Health" },
  { id: "home-kitchen", name_fa: "خانه و آشپزخانه", name_en: "Home & Kitchen" },
  { id: "digital-goods", name_fa: "لوازم دیجیتال و جانبی", name_en: "Digital Accessories" },
  { id: "stationery-books", name_fa: "کتاب، هنر و لوازم تحریر", name_en: "Books & Stationery" },
  { id: "kids-toys", name_fa: "کودک، نوزاد و اسباب‌بازی", name_en: "Kids & Toys" },
];

function getHeaders(token?: string): Record<string, string> {
  const h: Record<string, string> = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
  };
  if (token) {
    h["Authorization"] = `Bearer ${token}`;
  }
  return h;
}

export async function searchProducts(query: string, page = 1, priceMin?: number, priceMax?: number): Promise<any> {
  if (!query || !query.trim()) return { count: 0, results: [] };
  const cleanQ = query.trim();

  const params = new URLSearchParams();
  params.set("q", cleanQ);
  params.set("page", String(page));
  if (priceMin != null) params.set("price_from", String(priceMin));
  if (priceMax != null) params.set("price_to", String(priceMax));

  const url = `${BASALAM_SEARCH_BASE}/ai-engine/api/v2.0/product/search?${params.toString()}`;
  try {
    const resp = await fetch(url, { headers: getHeaders(), signal: AbortSignal.timeout(5000) });
    if (!resp.ok) {
      return { error: `Search HTTP ${resp.status}`, query: cleanQ };
    }
    const data = await resp.json() as any;
    const rawList = data?.products || data?.items || data?.results || [];
    const items = rawList.map((p: any) => ({
      id: p.id,
      title: p.title || p.name,
      price: p.price || 0,
      price_text: p.price ? `${Number(p.price).toLocaleString()} تومان` : "توافقی",
      primary_photo: p.photo?.url || p.image_url,
      vendor: {
        id: p.vendor?.id,
        name: p.vendor?.name || p.vendor?.title,
        rating: p.vendor?.rating?.rate || p.vendor?.rate || 0,
        city: p.vendor?.city || p.vendor?.city_name,
      },
      rating: p.rating?.rate || 0,
      reviews_count: p.rating?.count || 0,
      basalam_url: `${BASALAM_WEB_BASE}/product/${p.id}`,
    }));

    return {
      count: data?.total || items.length,
      query: cleanQ,
      page,
      results: items,
    };
  } catch (err: any) {
    return {
      query: cleanQ,
      notice: "سرورهای باسلام دارای محدودیت ایران‌اکسس می‌باشند و روی شبکه اینترنت داخلی با بالاترین سرعت پاسخگو هستند.",
      error: err.message,
      sample_result: {
        query: cleanQ,
        info: "جهت دسترسی به دیتای زنده از داخل ایران یا آی‌پی معتبر ایرانی استفاده فرمایید.",
      },
    };
  }
}

export async function getProductDetails(productId: string | number): Promise<any> {
  const cleanId = String(productId).trim();
  const url = `${BASALAM_CORE_BASE}/v4/products/${cleanId}`;
  try {
    const resp = await fetch(url, { headers: getHeaders(), signal: AbortSignal.timeout(5000) });
    if (!resp.ok) return { error: `Product details HTTP ${resp.status}`, product_id: cleanId };
    const data = await resp.json() as any;
    return {
      id: data.id || cleanId,
      title: data.title || data.name,
      description: data.description,
      price: data.price,
      price_text: data.price ? `${Number(data.price).toLocaleString()} تومان` : "ناموجود",
      stock: data.stock,
      vendor: {
        id: data.vendor?.id,
        title: data.vendor?.title || data.vendor?.name,
        identifier: data.vendor?.identifier,
        city: data.vendor?.city,
        score: data.vendor?.rating?.rate,
      },
      photos: (data.photos || []).map((ph: any) => ph.url),
      specs: data.attributes || [],
      basalam_url: `${BASALAM_WEB_BASE}/product/${cleanId}`,
    };
  } catch (err: any) {
    return { error: `Connection failed: ${err.message}`, product_id: cleanId };
  }
}

export async function getVendorDetails(vendorId: string | number): Promise<any> {
  const cleanId = String(vendorId).trim();
  const url = `${BASALAM_CORE_BASE}/v3/vendors/${cleanId}`;
  try {
    const resp = await fetch(url, { headers: getHeaders(), signal: AbortSignal.timeout(5000) });
    if (!resp.ok) return { error: `Vendor details HTTP ${resp.status}`, vendor_id: cleanId };
    const data = await resp.json() as any;
    return {
      id: data.id || cleanId,
      name: data.title || data.name,
      identifier: data.identifier,
      description: data.description,
      city: data.city,
      rating: data.rating?.rate || 0,
      total_reviews: data.rating?.count || 0,
      total_products: data.products_count || 0,
      avatar_url: data.avatar?.url,
      badges: data.badges || [],
      store_url: `${BASALAM_WEB_BASE}/vendor/${data.identifier || cleanId}`,
    };
  } catch (err: any) {
    return { error: `Connection failed: ${err.message}`, vendor_id: cleanId };
  }
}

export async function getPopularSearches(): Promise<any> {
  const url = `${BASALAM_SEARCH_BASE}/ai-engine/api/v2.0/product/popular-searches`;
  try {
    const resp = await fetch(url, { headers: getHeaders(), signal: AbortSignal.timeout(5000) });
    if (!resp.ok) return { searches: ["زعفران قائنات", "عسل طبیعی", "خرما مضافتی", "روغن زیتون", "ظروف مسی", "کیف چرم دست‌دوز"] };
    const data = await resp.json() as any;
    return { searches: data?.items || data?.searches || [] };
  } catch {
    return { searches: ["زعفران قائنات", "عسل طبیعی", "خرما مضافتی", "روغن زیتون", "ظروف مسی", "کیف چرم دست‌دوز"] };
  }
}

export function listCategories() {
  return BASALAM_CATEGORIES;
}

export function appraiseVendor(vendor: any): any {
  if (!vendor || vendor.error) return { error: "اطلاعات غرفه موجود نیست." };

  const rating = Number(vendor.rating || vendor.score || 0);
  const reviewsCount = Number(vendor.total_reviews || vendor.reviews_count || 0);
  const productsCount = Number(vendor.total_products || vendor.products_count || 0);

  // Rating score (0 - 50)
  const ratingScore = Math.min(50.0, (rating / 5.0) * 50.0);

  // Social trust & review count (0 - 30)
  let trustScore = 10.0;
  if (reviewsCount >= 200) trustScore = 30.0;
  else if (reviewsCount >= 50) trustScore = 24.0;
  else if (reviewsCount >= 10) trustScore = 18.0;

  // Catalog variety (0 - 20)
  let varietyScore = 10.0;
  if (productsCount >= 50) varietyScore = 20.0;
  else if (productsCount >= 15) varietyScore = 16.0;

  const totalScore = Number(Math.min(100.0, ratingScore + trustScore + varietyScore).toFixed(1));

  let verdict = "غرفه نوپا و در حال رشد";
  if (totalScore >= 85) verdict = "غرفه ممتاز و فوق‌العاده معتبر (Top Rated Artisan)";
  else if (totalScore >= 70) verdict = "غرفه قابل اعتماد با رضایت مشتری بالا";
  else if (totalScore >= 50) verdict = "غرفه معمولی با سابقه متوسط";

  return {
    vendor_name: vendor.name || vendor.title,
    vendor_id: vendor.id,
    trust_score: totalScore,
    satisfaction_rate: `${(rating * 20).toFixed(0)}%`,
    verdict,
    recommendation: totalScore >= 70
      ? "خرید از این غرفه توصیه می‌شود. میزان رضایت مشتریان قبلی بالاست."
      : "پیش از خرید، از طریق چت با غرفه‌دار گفتگو کرده و از موجودی و کیفیت محصول اطمینان حاصل فرمایید.",
  };
}

export function dealAnalysis(product: any): any {
  if (!product || product.error) return { error: "اطلاعات محصول نامعتبر است." };

  const price = Number(product.price || 0);
  const rating = Number(product.rating || 0);

  let score = 70.0;
  if (rating >= 4.5) score += 15.0;
  else if (rating >= 4.0) score += 10.0;

  if (price > 0 && price < 500000) score += 10.0;

  return {
    product_title: product.title,
    product_id: product.id,
    price_toman: product.price_text,
    value_score: Math.min(100.0, score),
    verdict: score >= 80 ? "ارزش خرید بسیار بالا (High Value Artisan Deal)" : "ارزش خرید متناسب با کیفیت بازار",
    buyer_tip: "محصولات خانگی و محلی باسلام امکان سفارشی‌سازی دارند؛ می‌توانید در بخش گفتگو ویژگی‌های دلخواه را هماهنگ کنید.",
  };
}
