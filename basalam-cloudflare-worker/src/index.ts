import {
  searchProducts,
  getProductDetails,
  getVendorDetails,
  getPopularSearches,
  listCategories,
  appraiseVendor,
  dealAnalysis,
  BASALAM_API_BASE,
  BASALAM_WEB_BASE,
} from "./basalam";

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
};

interface Env {}

const TOOL_DEFINITIONS = [
  {
    name: "basalam_search_products",
    description: "جستجوی محصولات، خوراکی‌ها، صنایع دستی، پوشاک و تولیدات خانگی در باسلام",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "نام محصول یا عبارت جستجو (مثلاً 'زعفران', 'عسل طبیعی', 'کیف چرم')" },
        page: { type: "integer", description: "شماره صفحه (پیش‌فرض: 1)", default: 1 },
        price_min: { type: "integer", description: "حداقل قیمت به تومان" },
        price_max: { type: "integer", description: "حداکثر قیمت به تومان" },
      },
      required: ["query"],
    },
  },
  {
    name: "basalam_get_product_details",
    description: "دریافت جزئیات کامل محصول، قیمت، مشخصات، موجودی و اطلاعات غرفه‌دار در باسلام",
    inputSchema: {
      type: "object",
      properties: {
        product_id: { type: "string", description: "شناسه محصول باسلام (مثلاً '123456')" },
      },
      required: ["product_id"],
    },
  },
  {
    name: "basalam_get_vendor_details",
    description: "دریافت اطلاعات غرفه، رضایت مشتریان، تعداد کالاها و سابقه فروشنده در باسلام",
    inputSchema: {
      type: "object",
      properties: {
        vendor_id: { type: "string", description: "شناسه یا نام کاربری غرفه (مثلاً '102030' یا 'saffron_store')" },
      },
      required: ["vendor_id"],
    },
  },
  {
    name: "basalam_get_popular_searches",
    description: "مشاهده کلمات و محصولات پرجستجو و محبوب در باسلام",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "basalam_list_categories",
    description: "فهرست دسته‌بندی‌های اصلی بازار باسلام (مواد غذایی، صنایع دستی، پوشاک و...)",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "basalam_appraise_vendor",
    description: "ارزیابی و نمره‌دهی هوشمند به اعتبار و رضایت مشتریان غرفه در باسلام (Trust Score)",
    inputSchema: {
      type: "object",
      properties: {
        vendor_id: { type: "string", description: "شناسه غرفه" },
      },
      required: ["vendor_id"],
    },
  },
  {
    name: "basalam_deal_analysis",
    description: "تحلیل هوشمند ارزش خرید و ارزیابی اقتصادی محصول در باسلام",
    inputSchema: {
      type: "object",
      properties: {
        product_id: { type: "string", description: "شناسه محصول" },
      },
      required: ["product_id"],
    },
  },
  {
    name: "basalam_status",
    description: "بررسی وضعیت سرور و سلامت اتصال به بازار اجتماعی باسلام",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "basalam_help",
    description: "راهنمای کاربری و لیست ابزارهای سرور Basalam MCP",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

async function handleToolCall(name: string, args: Record<string, any>): Promise<any> {
  switch (name) {
    case "basalam_search_products":
      return await searchProducts(args.query, args.page || 1, args.price_min, args.price_max);

    case "basalam_get_product_details":
      return await getProductDetails(args.product_id);

    case "basalam_get_vendor_details":
      return await getVendorDetails(args.vendor_id);

    case "basalam_get_popular_searches":
      return await getPopularSearches();

    case "basalam_list_categories":
      return { categories: listCategories() };

    case "basalam_appraise_vendor": {
      const v = await getVendorDetails(args.vendor_id);
      return appraiseVendor(v);
    }

    case "basalam_deal_analysis": {
      const p = await getProductDetails(args.product_id);
      return dealAnalysis(p);
    }

    case "basalam_status":
      return {
        service: "basalam-mcp",
        status: "operational",
        version: "1.0.0",
        tools_count: TOOL_DEFINITIONS.length,
        network_note: "Optimized for Iranian domestic connectivity and Edge proxy routing",
        api_base: BASALAM_API_BASE,
      };

    case "basalam_help":
      return {
        service: "Basalam MCP Server",
        description: "بازار اجتماعی باسلام (Basalam) - خرید مستقیم از تولیدکنندگان و غرفه‌داران ایرانی",
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
          service: "basalam-mcp",
          version: "1.0.0",
          tools: TOOL_DEFINITIONS.length,
        }, null, 2),
        {
          headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
        }
      );
    }

    // JSON-RPC endpoint (/mcp)
    if (url.pathname === "/mcp" || url.pathname === "/rpc") {
      if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405, headers: CORS_HEADERS });
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
