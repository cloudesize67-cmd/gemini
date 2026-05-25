"""
NOESIS MCP Server
Exposes NOESIS pipeline as MCP tools callable by Claude or any MCP client.
Compatible with transcriptapi.com/mcp and standard MCP protocol.
"""

import json
import asyncio
import logging
from pipeline import run_analysis

log = logging.getLogger("NOESIS.mcp")


# MCP Tool Definitions — register these with your MCP host
NOESIS_TOOLS = [
    {
        "name": "noesis_analyze",
        "description": (
            "Analyze a news article, claim, or market signal for misinformation, "
            "manipulation, and price spoofing. Returns verdict, confidence score, "
            "manipulation analysis, and recommended actions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The text content to analyze (article, headline, claim)"
                },
                "source_url": {
                    "type": "string",
                    "description": "URL of the source"
                },
                "market_id": {
                    "type": "string",
                    "description": "Polymarket market ID if claim relates to a prediction market"
                },
                "price_impact_claimed": {
                    "type": "number",
                    "description": "Claimed price impact as decimal (e.g., 0.15 = 15%)"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "noesis_batch_analyze",
        "description": "Analyze multiple claims simultaneously for coordinated campaign detection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "source_url": {"type": "string"}
                        },
                        "required": ["content"]
                    },
                    "description": "List of claims to analyze together"
                }
            },
            "required": ["claims"]
        }
    },
    {
        "name": "noesis_market_spoof_check",
        "description": (
            "Check if a specific claim appears designed to move a Polymarket prediction "
            "market price. Detects CLOB manipulation, fake volume signals, and "
            "narrative-price divergence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "market_id": {"type": "string"},
                "claimed_direction": {
                    "type": "string",
                    "enum": ["bullish", "bearish", "neutral"],
                    "description": "Direction the claim is pushing"
                }
            },
            "required": ["claim", "market_id"]
        }
    }
]


def handle_tool_call(tool_name: str, tool_input: dict) -> dict:
    """
    Synchronous MCP tool handler.
    Called by MCP host when Claude invokes a NOESIS tool.
    """

    if tool_name == "noesis_analyze":
        result = run_analysis(
            content=tool_input["content"],
            source_url=tool_input.get("source_url", ""),
            market_id=tool_input.get("market_id", ""),
            price_impact=float(tool_input.get("price_impact_claimed", 0))
        )
        return {"type": "tool_result", "content": json.dumps(result, indent=2)}

    elif tool_name == "noesis_batch_analyze":
        results = []
        for claim in tool_input.get("claims", []):
            r = run_analysis(
                content=claim["content"],
                source_url=claim.get("source_url", "")
            )
            results.append(r)
        # Aggregate CIB analysis
        spoof_count = sum(1 for r in results if r.get("spoof_pattern"))
        return {
            "type": "tool_result",
            "content": json.dumps({
                "total_claims": len(results),
                "spoof_detections": spoof_count,
                "coordinated_campaign_likelihood": spoof_count / max(len(results), 1),
                "results": results
            }, indent=2)
        }

    elif tool_name == "noesis_market_spoof_check":
        claim = tool_input["claim"]
        market_id = tool_input["market_id"]
        direction = tool_input.get("claimed_direction", "neutral")

        result = run_analysis(
            content=f"[{direction.upper()} SIGNAL] {claim}",
            market_id=market_id,
            price_impact=0.5 if direction != "neutral" else 0.0
        )
        return {
            "type": "tool_result",
            "content": json.dumps({
                "spoof_detected": result.get("spoof_pattern") is not None,
                "spoof_pattern": result.get("spoof_pattern"),
                "manipulation_score": result.get("manipulation_score"),
                "confidence": result.get("confidence"),
                "verdict": result.get("verdict"),
                "market_id": market_id
            }, indent=2)
        }

    else:
        return {
            "type": "tool_result",
            "is_error": True,
            "content": f"Unknown tool: {tool_name}"
        }


# MCP stdio transport (for use with Claude Code or direct MCP host)
async def mcp_stdio_loop():
    """
    MCP stdio transport loop.
    Run this as: python mcp_server.py
    Connect via Claude Code or any MCP host.
    """
    import sys

    while True:
        line = await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline
        )
        if not line:
            break
        try:
            request = json.loads(line.strip())
            method = request.get("method")

            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"tools": NOESIS_TOOLS}
                }
            elif method == "tools/call":
                tool_name = request["params"]["name"]
                tool_input = request["params"].get("arguments", {})
                result = handle_tool_call(tool_name, tool_input)
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": result
                }
            elif method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "noesis-mcp", "version": "1.0.0"}
                    }
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

            print(json.dumps(response), flush=True)

        except Exception as e:
            log.error(f"MCP loop error: {e}")


if __name__ == "__main__":
    asyncio.run(mcp_stdio_loop())
