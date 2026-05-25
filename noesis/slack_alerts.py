"""
NOESIS Slack Alert Integration
Sends real-time misinformation and market spoof alerts to Slack channel
"""

import os
import json
import httpx
from datetime import datetime

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")


VERDICT_EMOJI = {
    "CLEAN": ":white_check_mark:",
    "SUSPICIOUS": ":warning:",
    "MISINFORMATION": ":x:",
    "MARKET_SPOOF": ":rotating_light:",
    "PRC_DISQUALIFIED": ":shield:"
}


def send_alert(report: dict) -> bool:
    """
    Send NOESIS analysis result to Slack.
    Called automatically by server.py after every analysis.
    """
    if not SLACK_WEBHOOK:
        return False

    verdict = report.get("verdict", "UNKNOWN")
    confidence = report.get("confidence", 0)
    score = report.get("manipulation_score", 0)
    emoji = VERDICT_EMOJI.get(verdict, ":question:")

    # Only alert on non-clean verdicts
    if verdict == "CLEAN" and score < 0.3:
        return False

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} NOESIS Alert: {verdict}"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Manipulation Score:*\n{score:.0%}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence:*\n{confidence:.0%}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{report.get('executive_summary', 'N/A')[:300]}"
            }
        }
    ]

    # Add spoof pattern if detected
    if report.get("spoof_pattern"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":mag: *Spoof Pattern:* {report['spoof_pattern']}"
            }
        })

    # Add sovereign risk warning
    if report.get("sovereign_risk"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":shield: *SOVEREIGNTY RISK: PRC-origin source detected and disqualified*"
            }
        })

    # Add recommended actions
    actions = report.get("recommended_actions", [])
    if actions:
        action_text = "\n".join(f"• {a}" for a in actions[:3])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Actions:*\n{action_text}"
            }
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    f"Task: `{report.get('task_id', 'N/A')}` | "
                    f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                )
            }
        ]
    })

    try:
        resp = httpx.post(
            SLACK_WEBHOOK,
            json={"blocks": blocks},
            timeout=5.0
        )
        return resp.status_code == 200
    except Exception:
        return False


def send_startup_message(railway_url: str = "") -> bool:
    """Send startup notification when NOESIS comes online."""
    if not SLACK_WEBHOOK:
        return False

    text = (
        f":rocket: *NOESIS is online*\n"
        f"5-agent swarm active: SUPERVISOR → ARGUS → ARBITER → LOGOS → DAEDALUS\n"
    )
    if railway_url:
        text += f"API: {railway_url}/analyze\nDashboard: {railway_url}/dashboard"

    try:
        resp = httpx.post(SLACK_WEBHOOK, json={"text": text}, timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
