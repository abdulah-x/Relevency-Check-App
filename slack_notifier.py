"""
slack_notifier.py  (Relevancy Evaluator)
Sends an interactive Slack message for high-scoring consultant matches.
The message includes a "Approve & Draft Pitch" button per consultant.
"""

import json
import os
from dotenv import load_dotenv

# Load the same .env as the rest of the evaluator
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL   = os.getenv("SLACK_CHANNEL", "#project-approvals")


def send_slack_approval(project_title: str, platform: str, matches: list):
    """
    Posts one Slack message per consultant match.
    Each message has an 'Approve & Draft Pitch' button.
    The button value carries all data needed by slack_listener to generate the pitch.
    """
    if not SLACK_BOT_TOKEN:
        print("  ⚠️  SLACK_BOT_TOKEN not set — skipping Slack notification.")
        return

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        print("  ⚠️  slack-sdk not installed. Run: pip install slack-sdk")
        return

    client = WebClient(token=SLACK_BOT_TOKEN)

    for ev in matches:
        consultant_name = ev.get("consultant", "Unknown")
        score           = ev.get("score", 0)
        match_reasons   = ev.get("match_reasons", [])
        top_pars        = ev.get("top_pars", [])
        project_jd      = ev.get("project_jd", "")

        # Encode button payload — the Listener will unpack this
        button_value = json.dumps({
            "project_title":   project_title,
            "project_jd":      project_jd,
            "consultant_name": consultant_name,
            "top_pars":        top_pars,
        })

        score_emoji = "🟢" if score >= 90 else ("🟡" if score >= 70 else "🔴")
        reasons_text = "\n".join(f"• {r}" for r in match_reasons[:3])

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🎯 New Project Match — {platform}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Project:*\n{project_title}"},
                    {"type": "mrkdwn", "text": f"*Consultant:*\n{consultant_name}"},
                    {"type": "mrkdwn", "text": f"*Score:*\n{score_emoji} {score}%"},
                    {"type": "mrkdwn", "text": f"*Platform:*\n{platform}"},
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Why it matches:*\n{reasons_text}"}
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve & Draft Pitch"},
                        "style": "primary",
                        "action_id": "approve_pitch",
                        "value": button_value,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Dismiss"},
                        "style": "danger",
                        "action_id": "dismiss_pitch",
                        "value": project_title,
                    }
                ]
            }
        ]

        try:
            client.chat_postMessage(channel=SLACK_CHANNEL, blocks=blocks, text=f"New match: {project_title}")
            print(f"  📣 Slack message sent for {consultant_name} ({score}%)")
        except SlackApiError as e:
            print(f"  ❌ Slack API error: {e.response['error']}")
