import { Hono } from "hono";
import { cors } from "hono/cors";
import { streamSSE } from "hono/streaming";
import { Env } from "./divar";
import { TOOLS, executeTool } from "./tools";

const app = new Hono<{ Bindings: Env }>();

// Enable CORS for web-based MCP clients
app.use(
  "*",
  cors({
    origin: "*",
    allowMethods: ["GET", "POST", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
  })
);

// Map of active SSE session controllers
const sessions = new Map<string, (data: any) => Promise<void>>();

// ---------------------------------------------------------------------------
// Landing Page & Status
// ---------------------------------------------------------------------------

app.get("/", (c) => {
  const host = new URL(c.req.url).host;
  const protocol = new URL(c.req.url).protocol;
  const sseUrl = `${protocol}//${host}/sse`;
  const mcpUrl = `${protocol}//${host}/mcp`;

  return c.html(`<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>سرور Cloudflare MCP دیوار</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 40px 20px; line-height: 1.6; }
    .container { max-width: 800px; margin: 0 auto; background: #1e293b; padding: 32px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border: 1px solid #334155; }
    h1 { color: #38bdf8; margin-top: 0; }
    .badge { display: inline-block; padding: 4px 12px; background: #059669; color: #fff; border-radius: 999px; font-size: 14px; margin-bottom: 20px; }
    .card { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin: 16px 0; font-family: monospace; font-size: 14px; word-break: break-all; color: #a5f3fc; }
    h2 { color: #94a3b8; font-size: 18px; margin-top: 28px; }
    ul { padding-right: 20px; }
    li { margin: 8px 0; }
  </style>
</head>
<body>
  <div class="container">
    <div class="badge">● آنلاین روی سرورهای Cloudflare Workers</div>
    <h1>سرور هوش مصنوعی دیوار (Divar Remote MCP)</h1>
    <p>این سرور ارائه‌دهنده پروتکل رسمی Model Context Protocol برای جستجو، استخراج اطلاعات و مدیریت حساب دیوار است.</p>

    <h2>🔗 آدرس اتصال SSE (Server-Sent Events)</h2>
    <div class="card">${sseUrl}</div>

    <h2>⚡ آدرس اتصال مستقیم HTTP MCP</h2>
    <div class="card">${mcpUrl}</div>

    <h2>🛠 نحوه اتصال در Claude Desktop یا Cursor:</h2>
    <p>در فایل <code>claude_desktop_config.json</code> خود این را قرار دهید:</p>
    <div class="card">{
  "mcpServers": {
    "divar-cloud": {
      "url": "${sseUrl}"
    }
  }
}</div>

    <h2>📋 ابزارهای فعال (${TOOLS.length} ابزار):</h2>
    <ul>
      ${TOOLS.map((t) => `<li><strong>${t.name}</strong>: ${t.description}</li>`).join("")}
    </ul>
  </div>
</body>
</html>`);
});

// ---------------------------------------------------------------------------
// MCP Server-Sent Events (SSE) Transport
// ---------------------------------------------------------------------------

app.get("/sse", async (c) => {
  const sessionId = crypto.randomUUID();
  const url = new URL(c.req.url);
  const endpointUrl = `${url.pathname.replace(/\/sse$/, "")}/messages?sessionId=${sessionId}`;

  return streamSSE(c, async (stream) => {
    // Send endpoint URI to client
    await stream.writeSSE({
      event: "endpoint",
      data: endpointUrl,
    });

    // Register session sender
    sessions.set(sessionId, async (data: any) => {
      try {
        await stream.writeSSE({
          event: "message",
          data: JSON.stringify(data),
        });
      } catch (err) {
        sessions.delete(sessionId);
      }
    });

    // Keep-alive heartbeat loop
    while (!stream.aborted) {
      await stream.sleep(25000);
      try {
        await stream.writeSSE({
          event: "ping",
          data: "{}",
        });
      } catch {
        break;
      }
    }

    sessions.delete(sessionId);
  });
});

// ---------------------------------------------------------------------------
// MCP Messages Handler (POST /messages)
// ---------------------------------------------------------------------------

async function handleMcpRpc(req: any, env: Env): Promise<any> {
  const { id, method, params } = req;

  if (method === "initialize") {
    return {
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: {
          tools: {},
        },
        serverInfo: {
          name: "divar-mcp-cloudflare",
          version: "1.0.0",
        },
      },
    };
  }

  if (method === "notifications/initialized") {
    return null; // Notification, no response needed
  }

  if (method === "ping") {
    return { jsonrpc: "2.0", id, result: {} };
  }

  if (method === "tools/list") {
    return {
      jsonrpc: "2.0",
      id,
      result: {
        tools: TOOLS,
      },
    };
  }

  if (method === "tools/call") {
    const { name, arguments: args } = params || {};
    try {
      const res = await executeTool(name, args || {}, env);
      return {
        jsonrpc: "2.0",
        id,
        result: {
          content: [
            {
              type: "text",
              text: typeof res === "string" ? res : JSON.stringify(res, null, 2),
            },
          ],
        },
      };
    } catch (err: any) {
      return {
        jsonrpc: "2.0",
        id,
        result: {
          isError: true,
          content: [
            {
              type: "text",
              text: `Error executing tool ${name}: ${err.message || String(err)}`,
            },
          ],
        },
      };
    }
  }

  return {
    jsonrpc: "2.0",
    id,
    error: {
      code: -32601,
      message: `Method not found: ${method}`,
    },
  };
}

app.post("/messages", async (c) => {
  const sessionId = c.req.query("sessionId");
  const body = await c.req.json();
  const send = sessionId ? sessions.get(sessionId) : null;

  const response = await handleMcpRpc(body, c.env);

  if (response && send) {
    await send(response);
    return c.text("Accepted", 202);
  }

  if (response) {
    return c.json(response);
  }

  return c.text("Accepted", 202);
});

// ---------------------------------------------------------------------------
// Direct Stateless MCP Endpoint (POST /mcp)
// ---------------------------------------------------------------------------

app.post("/mcp", async (c) => {
  const body = await c.req.json();
  const response = await handleMcpRpc(body, c.env);
  return c.json(response || { jsonrpc: "2.0", result: null });
});

export default app;
