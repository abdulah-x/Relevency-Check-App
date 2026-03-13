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

print(f"DEBUG: SLACK_CHANNEL is '{SLACK_CHANNEL}'")
if SLACK_BOT_TOKEN:
    print(f"DEBUG: SLACK_BOT_TOKEN is set (starts with {SLACK_BOT_TOKEN[:10]}...)")
else:
    print("DEBUG: SLACK_BOT_TOKEN is MISSING")


def send_slack_approval(project_title: str, platform: str, matches: list):
    """
    Posts one Slack message per consultant match.
    Each message has an 'Approve & Draft Pitch' button.
    The button value carries all data needed by slack_listener to generate the pitch.
    """
    if not SLACK_BOT_TOKEN:
        print("  ⚠️  SLACK_BOT_TOKEN not set — skipping Slack notification.")
        return

    print(f"DEBUG: Preparing Slack messages for {len(matches)} matches...")

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        print("  ⚠️  slack-sdk not installed. Run: pip install slack-sdk")
        return

    client = WebClient(token=SLACK_BOT_TOKEN)

    # -------------------------------------------------------------------------
    # MONGODB HANDOFF (The "Locker")
    # -------------------------------------------------------------------------
    lookup_ids = []
    try:
        from pymongo import MongoClient
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        db_client = MongoClient(mongo_uri)
        # Use a specific database name to avoid "No default database" error
        db = db_client["evaluator_db"] 
        approvals_col = db["pending_approvals"]
        
        for ev in matches:
            # Save the full "Key" data to MongoDB
            doc = {
                "project_title":   project_title,
                "project_jd":      ev.get("project_jd", ""),
                "consultant_name": ev.get("consultant", "Unknown"),
                "score":           ev.get("score", 0),
                "top_pars":        ev.get("top_pars", []),
                "platform":        platform,
                "created_at":      os.getenv("PKT_TIME_STRING") or "" # Not strictly needed but helpful
            }
            res = approvals_col.insert_one(doc)
            lookup_ids.append(str(res.inserted_id))
            
    except Exception as e:
        print(f"  ❌ MongoDB Handoff Error: {e}")
        # If Mongo fails, we fallback to the old way (truncated) for safety
        lookup_ids = [None] * len(matches)

    for i, ev in enumerate(matches):
        consultant_name = ev.get("consultant", "Unknown")
        score           = ev.get("score", 0)
        match_reasons   = ev.get("match_reasons", [])
        
        lookup_id = lookup_ids[i]
        
        if lookup_id:
            # The "Key" approach (Small, safe payload)
            button_value = json.dumps({"lookup_id": lookup_id})
        else:
            # Fallback to truncated payload if Mongo is down
            button_value = json.dumps({
                "project_title":   project_title[:50],
                "project_jd":      ev.get("project_jd", "")[:200],
                "consultant_name": consultant_name,
                "top_pars":        ev.get("top_pars", [])[:2],
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
            print(f"DEBUG: Attempting chat_postMessage for {consultant_name} to {SLACK_CHANNEL}...")
            response = client.chat_postMessage(
                channel=SLACK_CHANNEL, 
                blocks=blocks, 
                text=f"New match: {project_title}"
            )
            if response.get("ok"):
                print(f"  📣 Slack message sent SUCCESSFULLY for {consultant_name} ({score}%)")
            else:
                print(f"  ❌ Slack message FAILED for {consultant_name}: {response.get('error')}")

        except SlackApiError as e:
            print(f"  ❌ Slack API Error for {consultant_name}: {e.response['error']}")
            # Debug: print the first block to see if it looks okay
            print(f"DEBUG: Failed blocks (sample): {json.dumps(blocks[0], indent=2)}")
        except Exception as e:
            print(f"  ❌ Unexpected Slack Error for {consultant_name}: {e}")
