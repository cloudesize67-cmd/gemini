"""
NOESIS ARGUS — Beta tier structured extraction agent
Hopkins Specificity Rule: extract only falsifiable, quantified claims
Polymarket CLOB + news source ingestion
"""

import anthropic
import os
import json
import re
import time
import httpx
from dataclasses import dataclass, field
from typing import Optional


ARGUS_MODEL = "claude-haiku-4-5"
POLYMARKET_GAMMA = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB = "https://clob.polymarket.com"


@dataclass
class ExtractedSignal:
    """A falsifiable, Hopkins-specific claim extracted from raw input."""
    claim_text: str
    claim_type: str              # "price_move", "event_probability", "narrative"
    quantified_value: Optional[float]
    source_url: str
    source_domain: str
    source_velocity: int = 0     # How many outlets published same claim in 1h
    prc_origin_risk: bool = False
    polymarket_correlated: bool = False
    market_id: str = ""
    market_probability_before: float = 0.0
    market_probability_after: float = 0.0
    extraction_confidence: float = 0.0
    raw_snippet: str = ""


@dataclass
class MarketSignal:
    market_id: str
    question: str
    yes_price: float
    no_price: float
    volume_24h: float
    price_delta_1h: float = 0.0
    anomaly_flag: bool = False
    anomaly_reason: str = ""


class ARGUSAgent:
    """
    ARGUS — Beta tier extraction.
    Applies Hopkins Specificity Rule: only concrete, quantified, source-attributed claims
    advance in the pipeline. Vague narratives are flagged but not discarded.
    """

    EXTRACTION_PROMPT = """You are ARGUS, a structured signal extraction agent for the 
NOESIS counter-misinformation system. Apply Hopkins Specificity Rule:
extract ONLY falsifiable, specific, quantified claims. No vague narratives.

For each claim, extract:
- Exact claim text (verbatim)
- Claim type: price_move | event_probability | narrative_campaign | regulatory | geopolitical
- Quantified value if present (%, price, date)
- Source domain
- Estimated source velocity (how many outlets making same claim simultaneously)
- PRC origin risk: true if source has CCP-adjacent ownership/funding
- Polymarket market ID if claim maps to a market (or "NONE")

Return ONLY valid JSON array. No preamble.

Schema per item:
{
  "claim_text": string,
  "claim_type": string,
  "quantified_value": number | null,
  "source_url": string,
  "source_domain": string,
  "source_velocity": integer,
  "prc_origin_risk": boolean,
  "market_id": string,
  "extraction_confidence": float 0-1
}"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.http = httpx.Client(timeout=10.0)

    def extract_signals(self, raw_content: str, source_url: str = "") -> list[ExtractedSignal]:
        """Extract structured signals from raw news/social content."""

        response = self.client.messages.create(
            model=ARGUS_MODEL,
            max_tokens=2048,
            system=self.EXTRACTION_PROMPT,
            messages=[{
                "role": "user",
                "content": f"SOURCE: {source_url}\n\nCONTENT:\n{raw_content}"
            }]
        )

        raw_json = response.content[0].text
        # Strip markdown fences if present
        raw_json = re.sub(r"```json|```", "", raw_json).strip()

        items = json.loads(raw_json)
        signals = []

        for item in items:
            # Disqualify PRC-origin by sovereignty policy
            if item.get("prc_origin_risk"):
                item["extraction_confidence"] *= 0.0  # Hard disqualify
                item["claim_type"] = "PRC_DISQUALIFIED"

            signal = ExtractedSignal(
                claim_text=item["claim_text"],
                claim_type=item["claim_type"],
                quantified_value=item.get("quantified_value"),
                source_url=source_url,
                source_domain=item.get("source_domain", ""),
                source_velocity=item.get("source_velocity", 0),
                prc_origin_risk=item.get("prc_origin_risk", False),
                market_id=item.get("market_id", "NONE"),
                extraction_confidence=item.get("extraction_confidence", 0.5),
                raw_snippet=raw_content[:500]
            )
            signals.append(signal)

        return signals

    def fetch_polymarket_market(self, market_id: str) -> Optional[MarketSignal]:
        """Fetch live market data from Polymarket Gamma API (no auth required)."""
        try:
            resp = self.http.get(
                f"{POLYMARKET_GAMMA}/markets/{market_id}",
                headers={"Accept": "application/json"}
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            tokens = data.get("tokens", [])
            yes_price = next(
                (t["price"] for t in tokens if t.get("outcome") == "Yes"), 0.5
            )
            no_price = 1.0 - yes_price

            return MarketSignal(
                market_id=market_id,
                question=data.get("question", ""),
                yes_price=yes_price,
                no_price=no_price,
                volume_24h=float(data.get("volume24hr", 0)),
            )
        except Exception:
            return None

    def scan_market_anomalies(
        self,
        signals: list[ExtractedSignal]
    ) -> list[ExtractedSignal]:
        """Cross-reference extracted signals against live Polymarket prices."""

        for signal in signals:
            if signal.market_id and signal.market_id != "NONE":
                market = self.fetch_polymarket_market(signal.market_id)
                if market:
                    signal.polymarket_correlated = True
                    signal.market_probability_before = market.yes_price
                    # Flag: claim direction mismatches market price movement
                    if (
                        signal.quantified_value is not None
                        and signal.quantified_value > 0.7
                        and market.yes_price < 0.3
                    ):
                        signal.claim_type = "PRICE_SPOOF_CANDIDATE"

        return signals
