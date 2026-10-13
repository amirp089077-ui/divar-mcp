"""
Basalam Model Context Protocol (MCP) Standard Server
Standard I/O JSON-RPC transport for Antigravity, Claude Desktop, and Gemini IDE.
"""

import io
import json
import logging
import sys
from typing import Any, Dict, Optional

from .tools import TOOLS, execute_tool

if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [basalam-mcp] %(message)s",
)
logger = logging.getLogger("basalam_mcp.server")


class BasalamMCPServer:
    """Production MCP Server for Basalam Social Marketplace."""

    def __init__(self):
        self.server_info = {
            "name": "basalam-mcp",
            "version": "1.0.0",
        }

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if not method:
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": self.server_info,
                },
            }

        elif method == "notifications/initialized":
            logger.info("Client completed initialization handshake.")
            return None

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result_data = execute_tool(tool_name, tool_args)
                text_content = json.dumps(result_data, ensure_ascii=False, indent=2)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": text_content}],
                        "isError": False,
                    },
                }
            except Exception as e:
                logger.error("Error executing %s: %s", tool_name, e, exc_info=True)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                        "isError": True,
                    },
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    def run(self):
        """Main stdio loop reading JSON-RPC messages line by line."""
        logger.info("Basalam MCP Server starting on stdio...")
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                req = json.loads(line_str)
                resp = self.handle_request(req)
                if resp is not None:
                    out = json.dumps(resp, ensure_ascii=False)
                    sys.stdout.write(out + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
            except Exception as e:
                logger.error("Unexpected error in main loop: %s", e)


def main():
    server = BasalamMCPServer()
    server.run()


if __name__ == "__main__":
    main()
