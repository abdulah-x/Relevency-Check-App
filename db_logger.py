from datetime import datetime
import re
from pymongo import MongoClient
from config import MONGO_URI, PKT, MIN_SCORE

_client = None
_collection = None

def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = MongoClient(MONGO_URI)
        _collection = _client["office_monitor"]["evaluations"]
    return _collection


def _make_project_id(title: str) -> str:
    """Generate a stable project_id slug from the title for cross-collection linking."""
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80]


def log_evaluation(title, platform, evaluations, project_id: str = None):
    """
    Save a project + all consultant scores to MongoDB in one unified document.
    project_id links back to the `projects` collection.
    """

    # Use provided project_id or derive one from the title
    pid = project_id or _make_project_id(title)

    # Process evaluations to include the email_sent flag
    processed_evals = []
    for ev in evaluations:
        score = ev.get("score", 0)
        email_sent = score >= MIN_SCORE

        processed_ev = {
            "consultant":    ev.get("consultant", "Unknown"),
            "score":         score,
            "email_sent":    email_sent,
            "match_reasons": ev.get("match_reasons", [])
        }

        if email_sent:
            processed_ev["top_pars"] = ev.get("top_pars", [])
        else:
            processed_ev["low_score_reasons"] = ev.get("low_score_reasons", [])

        processed_evals.append(processed_ev)

    doc = {
        "project_id":        pid,           # FK → projects.project_id
        "title":             title,
        "platform":          platform,
        "evaluated_at":      datetime.now(PKT),
        "consultant_scores": processed_evals,
    }

    try:
        col = _get_collection()
        result = col.insert_one(doc)
        print(f"  💾 Saved to evaluations — id: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        print(f"  ⚠️  DB save failed: {e}")
        return None
