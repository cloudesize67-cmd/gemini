"""
NOESIS HTTP Server + MCP Bridge + Slack Alerts
FastAPI REST API | Railway deployment | Cloudflare Tunnel compatible
"""

import os
import json
import time
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from pipeline import run_analysis
from slack_alerts import send_alert, send_startup_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("NOESIS.server")

app = FastAPI(
    title="NOESIS Misinformation Detection API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_results: dict = {}


class AnalysisRequest(BaseModel):
    content: str
    source_url: str = ""
    market_id: str = ""
    price_impact_claimed: float = 0.0
    priority: int = Field(3, ge=1, le=5)


class BatchRequest(BaseModel):
    items: list[AnalysisRequest]


@app.on_event("startup")
async def on_startup():
    railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if railway_url:
        railway_url = f"https://{railway_url}"
    send_startup_message(railway_url)
    log.info("NOESIS online — Slack startup alert sent")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "system": "NOESIS",
        "agents": ["SUPERVISOR", "ARGUS", "ARBITER", "LOGOS", "DAEDALUS"],
        "timestamp": time.time()
    }


@app.post("/analyze")
async def analyze(req: AnalysisRequest, background_tasks: BackgroundTasks):
    try:
        result = run_analysis(
            content=req.content,
            source_url=req.source_url,
            market_id=req.market_id,
            price_impact=req.price_impact_claimed
        )
        _results[result["task_id"]] = result
        # Send Slack alert in background
        background_tasks.add_task(send_alert, result)
        return result
    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/batch")
async def analyze_batch(req: BatchRequest, background_tasks: BackgroundTasks):
    import hashlib
    job_ids = []
    for item in req.items:
        job_id = hashlib.sha256(
            (item.content[:100] + str(time.time())).encode()
        ).hexdigest()[:16]
        job_ids.append(job_id)

        async def _run(i=item, jid=job_id):
            result = run_analysis(
                content=i.content,
                source_url=i.source_url,
                market_id=i.market_id,
                price_impact=i.price_impact_claimed
            )
            _results[jid] = result
            send_alert(result)

        background_tasks.add_task(_run)
    return {"job_ids": job_ids, "count": len(job_ids)}


@app.get("/results/{task_id}")
async def get_result(task_id: str):
    if task_id not in _results:
        raise HTTPException(status_code=404, detail="Not found or still processing")
    return _results[task_id]


@app.post("/mcp/analyze")
async def mcp_analyze(request: dict):
    tool_input = request.get("input", {})
    try:
        result = run_analysis(
            content=tool_input.get("content", ""),
            source_url=tool_input.get("source_url", ""),
            market_id=tool_input.get("market_id", ""),
            price_impact=float(tool_input.get("price_impact_claimed", 0))
        )
        return {"type": "tool_result", "content": json.dumps(result)}
    except Exception as e:
        return {"type": "tool_result", "is_error": True, "content": str(e)}


@app.get("/dashboard")
async def dashboard():
    total = len(_results)
    verdicts = {}
    spoof_count = 0
    for r in _results.values():
        v = r.get("verdict", "UNKNOWN")
        verdicts[v] = verdicts.get(v, 0) + 1
        if r.get("spoof_pattern"):
            spoof_count += 1
    return {
        "total_analyzed": total,
        "verdict_distribution": verdicts,
        "spoof_detections": spoof_count,
        "system": "NOESIS v1.0",
        "agents_active": 5
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
