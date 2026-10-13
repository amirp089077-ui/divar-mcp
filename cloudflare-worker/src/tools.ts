import * as divar from "./divar";

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, any>;
    required?: string[];
  };
}

export const TOOLS: ToolDefinition[] = [
  {
    name: "divar_search",
    description: "Search live divar.ir listings with filters (query, city, category, price range).",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query text in Persian (e.g. پژو ۲۰۶ or پیکان وانت)" },
        city: { type: "string", description: "City name or slug (e.g. شاهرود)" },
        cities: {
          type: "array",
          items: { type: "string" },
          description: "Search multiple cities at once, e.g. ['شاهرود', 'سبزوار']",
        },
        category: { type: "string", description: "Category slug (e.g. vehicles, cars, electronic-devices)" },
        price_min: { type: "integer", description: "Minimum price in Toman" },
        price_max: { type: "integer", description: "Maximum price in Toman" },
        year_min: { type: "integer", description: "Minimum production year (e.g. 1390)" },
        year_max: { type: "integer", description: "Maximum production year (e.g. 1402)" },
      },
    },
  },
  {
    name: "divar_get_post",
    description: "Read full details of a specific Divar post including title, description, attributes, and photos.",
    inputSchema: {
      type: "object",
      properties: {
        token: { type: "string", description: "Post token or URL (e.g. gaGL4MVW or https://divar.ir/v/gaGL4MVW)" },
      },
      required: ["token"],
    },
  },
  {
    name: "divar_get_contact",
    description: "Extract seller phone numbers and call/chat availability for a post. Requires Divar authentication.",
    inputSchema: {
      type: "object",
      properties: {
        token: { type: "string", description: "Post token or URL" },
      },
      required: ["token"],
    },
  },
  {
    name: "divar_get_my_bookmarks",
    description: "Fetch list of saved/bookmarked ads for the authenticated user via gRPC.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "divar_bookmark_post",
    description: "Bookmark or remove an ad from the user's saved list via gRPC.",
    inputSchema: {
      type: "object",
      properties: {
        token: { type: "string", description: "Post token or URL" },
        bookmark: { type: "boolean", description: "true to bookmark, false to remove" },
      },
      required: ["token"],
    },
  },
  {
    name: "divar_get_my_notes",
    description: "Fetch personal notes written on Divar posts via gRPC Yaad service.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "divar_get_my_sessions",
    description: "Fetch active login sessions and connected devices for current user via gRPC.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "divar_get_blocked_users",
    description: "Fetch list of blocked chat users for current user via gRPC.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "divar_chat_conversations",
    description: "List active chat conversations for the logged in user.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "divar_chat_messages",
    description: "Fetch message history for a conversation.",
    inputSchema: {
      type: "object",
      properties: {
        conversation_id: { type: "string", description: "Conversation ID" },
      },
      required: ["conversation_id"],
    },
  },
  {
    name: "divar_list_cities",
    description: "Search Iranian cities and get their Divar city IDs and slugs.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "City name in Persian or English" },
      },
    },
  },
  {
    name: "divar_list_categories",
    description: "Search Divar categories and get their slugs and names.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Category name or slug" },
      },
    },
  },
  {
    name: "divar_status",
    description: "Check server reachability, active credentials and health.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

export async function executeTool(name: string, args: Record<string, any>, env: divar.Env): Promise<any> {
  switch (name) {
    case "divar_search":
      return await divar.search(args);

    case "divar_get_post":
      return await divar.getPost(args.token || args.post_token);

    case "divar_get_contact":
      return await divar.getContact(args.token || args.post_token, env);

    case "divar_get_my_bookmarks":
      return await divar.getMyBookmarks(env);

    case "divar_bookmark_post":
      return await divar.bookmarkPost(args.token || args.post_token, args.bookmark !== false, env);

    case "divar_get_my_notes":
      return await divar.getMyNotes(env);

    case "divar_get_my_sessions":
      return await divar.getMySessions(env);

    case "divar_get_blocked_users":
      return await divar.getBlockedUsers(env);

    case "divar_chat_conversations":
      return await divar.getConversations(env);

    case "divar_chat_messages":
      return await divar.getMessages(args.conversation_id, env);

    case "divar_list_cities":
      return divar.listCities(args.query);

    case "divar_list_categories":
      return divar.listCategories(args.query);

    case "divar_status":
      return {
        status: "online",
        platform: "Cloudflare Workers",
        tools_count: TOOLS.length,
        has_token: Boolean(env.DIVAR_TOKEN),
        has_cookies: Boolean(env.DIVAR_COOKIES),
        time: new Date().toISOString(),
      };

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}
