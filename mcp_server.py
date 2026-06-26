#!/usr/bin/env python3
"""
MCP Server for A2A Affiliate Recommender
========================================
Exposes the /recommend endpoint as an MCP tool that any MCP-compatible
agent can call to get tool recommendations with signed attribution tokens.

Run with:
  pip install mcp
  python3 mcp_server.py

Or if mcp is not installed, falls back to stdio-based MCP JSON-RPC manually.

Environment:
  A2A_API_URL       — base URL of the A2A API (default: http://127.0.0.1:8787)
  A2A_API_KEY       — bearer token for API auth
"""

import os
import sys
import json
import signal
import urllib.request
import urllib.error
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MCP] %(message)s")
logger = logging.getLogger("a2a_mcp")

# ── Configuration ──────────────────────────────────────────────────

API_URL = os.environ.get("A2A_API_URL", "http://127.0.0.1:8787")
API_KEY = os.environ.get("A2A_API_KEY", "")

if API_KEY:
    logger.info("API key loaded from A2A_API_KEY environment variable")
else:
    # Try .env / .api_key fallback
    key_file = os.path.join(os.path.dirname(__file__), ".api_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            API_KEY = f.read().strip()
        logger.info("API key loaded from .api_key file: %s", key_file)
    else:
        logger.error("A2A_API_KEY not set and .api_key file not found. MCP server will fail to authenticate.")
        API_KEY = "MISSING_API_KEY"


# ── API Client ─────────────────────────────────────────────────────

def call_recommend(intent: str = "", description: str = "", constraints: dict | None = None) -> dict:
    """
    Call the A2A /recommend endpoint and return the parsed response.
    """
    constraints = constraints if isinstance(constraints, dict) else {}
    payload = {
        "referrer_agent_id": "mcp:bloomfield",
        "caller_agent_id": "mcp_client:unknown",
        "task": {
            "intent": intent,
            "description": description,
            "constraints": constraints,
        },
        "context": {
            "source": "mcp_server",
            "transport": "mcp",
        },
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/recommend",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "data": data}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Tool Definition ─────────────────────────────────────────────────

TOOL_DEFINITION = {
    "name": "recommend_tool",
    "description": (
        "Recommend the best tool for a given agent task from the Bloomfield A2A "
        "Affiliate Registry (25+ tools across 13 categories). Returns a recommendation "
        "with a signed attribution token and human handoff link. "
        "Categories: scraping, serp, crm, communications, analytics, social_listening, "
        "creative, automation, operations, hr, web, financing, search_api."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "High-level task intent (e.g., web_scraping, search_api, crm, communications, analytics, creative, automation)",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of what the agent is trying to do (e.g., 'Need to extract clean markdown from websites at scale')",
            },
            "constraints": {
                "type": "object",
                "description": "Optional constraints dict (e.g., {'budget': 'low', 'requires_api': True, 'human_signup_ok': True})",
                "additionalProperties": True,
            },
        },
        "required": ["intent"],
    },
}


# ── MCP Server (stdio JSON-RPC) ─────────────────────────────────────

MCP_SERVER_INFO = {
    "name": "a2a-affiliate-recommender",
    "version": "1.0.0",
}


def handle_request(msg: dict) -> dict | None:
    """Handle a single MCP JSON-RPC request. Returns response dict or None for notifications."""
    # MCP spec: notifications have no "id" field -- never respond
    if "id" not in msg:
        return None

    msg_id = msg.get("id")
    method = msg.get("method", "")

    # ── initialize ──────────────────────────────────────────
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": MCP_SERVER_INFO,
            },
        }

    # ── tools/list ───────────────────────────────────────────
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": [TOOL_DEFINITION]},
        }

    # ── tools/call ───────────────────────────────────────────
    if method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}

        if tool_name != "recommend_tool":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"Unknown tool: {tool_name}"}
                    ],
                    "isError": True,
                },
            }

        intent = arguments.get("intent", "")
        description = arguments.get("description", "")
        constraints = arguments.get("constraints", {})

        logger.info(
            "Tool call: intent=%s description=%.80s constraints=%s",
            intent,
            description,
            json.dumps(constraints) if constraints else "{}",
        )

        result = call_recommend(intent=intent, description=description, constraints=constraints)

        if result["success"]:
            response_text = json.dumps(result["data"], indent=2)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {"type": "text", "text": response_text}
                    ],
                },
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"Recommendation failed: {result['error']}"}
                    ],
                    "isError": True,
                },
            }

    # ── ping ─────────────────────────────────────────────────
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    # ── unknown ──────────────────────────────────────────────
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


_shutdown_flag = False


def _handle_signal(signum, frame):
    """Set shutdown flag on SIGTERM/SIGINT for graceful exit."""
    global _shutdown_flag
    signame = signal.Signals(signum).name
    logger.info("Received signal %s, shutting down gracefully...", signame)
    _shutdown_flag = True


def main():
    """Run the MCP server on stdio."""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("A2A MCP Server starting (stdio transport)")
    logger.info("API endpoint: %s", API_URL)

    for line in sys.stdin:
        if _shutdown_flag:
            logger.info("Shutdown flag set, exiting stdin loop")
            break
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON received: %s", e)
            continue

        response = handle_request(msg)

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    logger.info("MCP server exiting")


# ── Standalone test mode ────────────────────────────────────────────

def standalone_test(intent: str = "web_scraping", description: str = "Extract data from websites"):
    """Run a local test without MCP transport."""
    print("=" * 60)
    print("A2A MCP Server — Standalone Test")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"Intent: {intent}")
    print(f"Description: {description}")
    print("-" * 60)

    result = call_recommend(intent=intent, description=description)
    if result["success"]:
        data = result["data"]
        print(f"\nRecommendation: {data['recommended_tool']['name']}")
        print(f"Category: {data['recommended_tool']['category']}")
        print(f"Confidence: {data['recommended_tool']['confidence']}")
        print(f"Token ID: {data['attribution']['token_id']}")
        print(f"Handoff URL: {data['attribution']['handoff_url']}")
        print(f"\nFull response:")
        print(json.dumps(data, indent=2))
    else:
        print(f"\nERROR: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        intent = "web_scraping"
        desc = ""
        for i, arg in enumerate(sys.argv[1:]):
            if arg == "--intent" and i + 2 < len(sys.argv):
                intent = sys.argv[i + 2]
            elif arg == "--description" and i + 2 < len(sys.argv):
                desc = sys.argv[i + 2]
        standalone_test(intent=intent, description=desc)
    else:
        main()
