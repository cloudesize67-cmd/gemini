"""
NOESIS HTTP Server + MCP Bridge
FastAPI REST API | Cloudflare Tunnel compatible
Phone interface via ngrok/cloudflared
"""

import os
import json
import time
import logging
from fastapi import FastAPI, HTTPException, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from pipeline import run_analysis

log = logging.getLogger("NOESIS.server")

app = FastAPI(
    title="NOESIS Misinformation Detection API",
    description="5-agent swarm for counter-misinformation and market spoof detection",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response Models ──

class AnalysisRequest(BaseModel):
    content: str = Field(..., description="Raw news/claim content to analyze")
    source_url: str = Field("", description="URL of the source")
    market_id: str = Field("", description="Polymarket market ID if applicable")
    price_impact_claimed: float = Field(0.0, description="Claimed price impact 0-1")
    priority: int = Field(3, ge=1, le=5, description="Priority 1-5")


class BatchRequest(BaseModel):
    items: list[AnalysisRequest]


class AnalysisResponse(BaseModel):
    verdict: str
    confidence: float
    manipulation_score: float
    executive_summary: str
    key_findings: list[str]
    market_impact: str
    recommended_actions: list[str]
    spoof_pattern: Optional[str]
    cib_assessment: str
    sovereign_risk: bool
    task_id: str
    timestamp: float


# ── In-memory result store (replace with Redis in production) ──
_results: dict[str, dict] = {}


# ── Endpoints ──

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "system": "NOESIS",
        "agents": ["SUPERVISOR", "ARGUS", "ARBITER", "LOGOS", "DAEDALUS"],
        "timestamp": time.time()
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(req: AnalysisRequest):
    """
    Run full NOESIS pipeline on a single claim/article.
    Returns structured intelligence report.
    """
    try:
        result = run_analysis(
            content=req.content,
            source_url=req.source_url,
            market_id=req.market_id,
            price_impact=req.price_impact_claimed
        )
        _results[result["task_id"]] = result
        return result
    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/batch")
async def analyze_batch(req: BatchRequest, background_tasks: BackgroundTasks):
    """
    Submit a batch of claims for async processing.
    Returns job IDs — poll /results/{task_id} for each.
    """
    import hashlib
    job_ids = []

    for item in req.items:
        job_id = hashlib.sha256(
            (item.content[:100] + str(time.time())).encode()
        ).hexdigest()[:16]
        job_ids.append(job_id)

        async def _run(i=item, jid=job_id):
            try:
                result = run_analysis(
                    content=i.content,
                    source_url=i.source_url,
                    market_id=i.market_id,
                    price_impact=i.price_impact_claimed
                )
                _results[jid] = result
                _results[jid]["status"] = "complete"
            except Exception as e:
                _results[jid] = {"status": "error", "error": str(e)}

        background_tasks.add_task(_run)

    return {"job_ids": job_ids, "count": len(job_ids)}


@app.get("/results/{task_id}")
async def get_result(task_id: str):
    """Retrieve a completed analysis result."""
    if task_id not in _results:
        raise HTTPException(status_code=404, detail="Task not found or still processing")
    return _results[task_id]


@app.post("/mcp/analyze")
async def mcp_analyze(request: Request):
    """
    MCP tool endpoint — called by Claude or other MCP clients.
    Accepts MCP tool_use format and returns tool_result.
    """
    body = await request.json()
    tool_input = body.get("input", {})

    try:
        result = run_analysis(
            content=tool_input.get("content", ""),
            source_url=tool_input.get("source_url", ""),
            market_id=tool_input.get("market_id", ""),
            price_impact=float(tool_input.get("price_impact_claimed", 0))
        )
        return {
            "type": "tool_result",
            "content": json.dumps(result)
        }
    except Exception as e:
        return {
            "type": "tool_result",
            "is_error": True,
            "content": str(e)
        }


@app.get("/dashboard")
async def dashboard():
    """Quick stats dashboard for phone interface."""
    total = len(_results)
    verdicts = {}
    spoof_count = 0
    cib_count = 0

    for r in _results.values():
        v = r.get("verdict", "UNKNOWN")
        verdicts[v] = verdicts.get(v, 0) + 1
        if r.get("spoof_pattern"):
            spoof_count += 1
        if "coordinated" in r.get("cib_assessment", "").lower():
            cib_count += 1

    return {
        "total_analyzed": total,
        "verdict_distribution": verdicts,
        "spoof_detections": spoof_count,
        "cib_detections": cib_count,
        "system": "NOESIS v1.0",
        "agents_active": 5
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
