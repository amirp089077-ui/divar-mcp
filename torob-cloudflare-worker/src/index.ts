import {
  searchProducts,
  getProductDetails,
  getPriceChart,
  getSpecialOffers,
  searchSuggestions,
  compareStores,
  appraiseDeal,
  listCategories,
  TOROB_API_BASE,
  DEFAULT_USER_AGENT,
} from "./torob";

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
};

interface Env {}

const TOOL_DEFINITIONS = [
  {
    name: "torob_search_products",
    description: "جستجوی انواع محصولات، گوشی، لپ‌تاپ، لوازم خانگی و پوشاک در ترب با مقایسه لحظه‌ای قیمت فروشگاه‌ها",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "نام محصول یا مدل (مثلاً 'iPhone 13', 'لپ تاپ ایسوس', 'تلویزیون سامسونگ')" },
        page: { type: "integer", description: "شماره صفحه (پیش‌فرض: 1)", default: 1 },
        price_min: { type: "integer", description: "حداقل قیمت به تومان" },
        price_max: { type: "integer", description: "حداکثر قیمت به تومان" },
      },
      required: ["query"],
    },
  },
  {
    name: "torob_get_product_details",
    description: "دریافت مشخصات کامل کالا و فهرست تمام فروشگاه‌های ارائه‌دهنده (با قیمت، گارانتی، امتیاز و لینک خرید)",
    inputSchema: {
      type: "object",
      properties: {
        prk: { type: "string", description: "شناسه تصادفی یا کلید اختصاصی محصول ترب (random_key یا prk مانند '13528091-f204-4f10-ba78-57143406a9a1')" },
      },
      required: ["prk"],
    },
  },
  {
    name: "torob_get_price_chart",
    description: "دریافت تاریخچه و نمودار تغییرات قیمت کالا در طول روزها و ماه‌های گذشته",
    inputSchema: {
      type: "object",
      properties: {
        prk: { type: "string", description: "شناسه محصول ترب (prk)" },
      },
      required: ["prk"],
    },
  },
  {
    name: "torob_get_special_offers",
    description: "دریافت تخفیف‌های ویژه، شگفت‌انگیز و پیشنهادهای روز ترب با درصد تخفیف بالا",
    inputSchema: {
      type: "object",
      properties: {
        page: { type: "integer", description: "شماره صفحه (پیش‌فرض: 1)", default: 1 },
      },
    },
  },
  {
    name: "torob_get_suggestions",
    description: "دریافت پیشنهادهای تکمیل خودکار کلمات جستجو (Autosuggest) از موتور ترب",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "عبارت جستجو برای پیشنهاد کلمات" },
      },
      required: ["query"],
    },
  },
  {
    name: "torob_compare_stores",
    description: "مقایسه هوشمند فروشندگان یک محصول در ترب: یافتن ارزان‌ترین، بالاترین امتیاز، درصد اختلاف قیمت و صرفه‌جویی",
    inputSchema: {
      type: "object",
      properties: {
        prk: { type: "string", description: "شناسه محصول ترب (prk)" },
      },
      required: ["prk"],
    },
  },
  {
    name: "torob_appraise_deal",
    description: "ارزیابی و تحلیل هوشمند ارزش خرید کالا در ترب با محاسبه رقابت فروشندگان و فرصت تخفیف (Deal Score)",
    inputSchema: {
      type: "object",
      properties: {
        prk: { type: "string", description: "شناسه محصول ترب (prk)" },
      },
      required: ["prk"],
    },
  },
  {
    name: "torob_list_categories",
    description: "فهرست دسته‌بندی‌های اصلی ترب (موبایل، لپ‌تاپ، لوازم خانگی، مد، ابزار، خودرو)",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "torob_status",
    description: "بررسی وضعیت دسترسی، تعداد ابزارها و سلامت ارتباط سرور ترب MCP",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "torob_help",
    description: "راهنمای کاربری و دستورات سرور Torob MCP",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

async function handleToolCall(name: string, args: Record<string, any>): Promise<any> {
  switch (name) {
    case "torob_search_products":
      return await searchProducts(args.query, args.page || 1, args.price_min, args.price_max);

    case "torob_get_product_details":
      return await getProductDetails(args.prk);

    case "torob_get_price_chart":
      return await getPriceChart(args.prk);

    case "torob_get_special_offers":
      return await getSpecialOffers(args.page || 1);

    case "torob_get_suggestions":
      return await searchSuggestions(args.query);

    case "torob_compare_stores":
      return await compareStores(args.prk);

    case "torob_appraise_deal":
      return await appraiseDeal(args.prk);

    case "torob_list_categories":
      return { categories: listCategories() };

    case "torob_status":
      return {
        service: "torob-mcp",
        status: "operational",
        version: "1.0.0",
        tools_count: TOOL_DEFINITIONS.length,
        api_base: TOROB_API_BASE,
      };

    case "torob_help":
      return {
        service: "Torob MCP Server",
        description: "موتور جستجو و مقایسه قیمت هوشمند ترب (Torob)",
        tools: TOOL_DEFINITIONS.map(t => ({ name: t.name, description: t.description })),
      };

    default:
      throw new Error(`Tool not found: ${name}`);
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    // Health check
    if (url.pathname === "/health" || url.pathname === "/") {
      return new Response(
        JSON.stringify({
          status: "healthy",
          service: "torob-mcp",
          version: "1.0.0",
          tools: TOOL_DEFINITIONS.length,
        }, null, 2),
        {
          headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
        }
      );
    }

    // Proxy endpoint for local clients needing direct API routing through Cloudflare edge
    if (url.pathname.startsWith("/api/proxy")) {
      const targetPath = url.pathname.replace("/api/proxy", "");
      const targetUrl = `${TOROB_API_BASE}${targetPath}${url.search}`;
      try {
        const resp = await fetch(targetUrl, {
          method: request.method,
          headers: {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa,en;q=0.9",
          },
          body: request.method === "POST" ? await request.text() : undefined,
        });
        const body = await resp.text();
        return new Response(body, {
          status: resp.status,
          headers: {
            ...CORS_HEADERS,
            "Content-Type": resp.headers.get("Content-Type") || "application/json",
          },
        });
      } catch (err: any) {
        return new Response(JSON.stringify({ error: err.message }), {
          status: 502,
          headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
        });
      }
    }

    // JSON-RPC endpoint (/mcp)
    if (url.pathname === "/mcp" || url.pathname === "/rpc") {
      if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 455, headers: CORS_HEADERS });
      }

      let rpcRequest: any;
      try {
        rpcRequest = await request.json();
      } catch {
        return new Response(
          JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }),
          { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
        );
      }

      const { jsonrpc = "2.0", id = null, method, params = {} } = rpcRequest;

      try {
        if (method === "tools/list") {
          return new Response(
            JSON.stringify({ jsonrpc, id, result: { tools: TOOL_DEFINITIONS } }),
            { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
          );
        }

        if (method === "tools/call") {
          const { name, arguments: toolArgs = {} } = params;
          const result = await handleToolCall(name, toolArgs);
          return new Response(
            JSON.stringify({
              jsonrpc,
              id,
              result: {
                content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
              },
            }),
            { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
          );
        }

        if (method === "ping") {
          return new Response(
            JSON.stringify({ jsonrpc, id, result: {} }),
            { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
          );
        }

        return new Response(
          JSON.stringify({ jsonrpc, id, error: { code: -32601, message: `Method not found: ${method}` } }),
          { status: 404, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
        );
      } catch (err: any) {
        return new Response(
          JSON.stringify({
            jsonrpc,
            id,
            result: {
              content: [{ type: "text", text: JSON.stringify({ error: err.message }) }],
              isError: true,
            },
          }),
          { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
        );
      }
    }

    return new Response("Not Found", { status: 404, headers: CORS_HEADERS });
  },
};
