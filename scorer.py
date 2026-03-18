import json
import re
import time
import anthropic
from config import ANTHROPIC_API_KEY, CONSULTANTS


def get_active_prompt():
    """Fetch the latest prompt logic from MongoDB."""
    try:
        from db_logger import _get_collection
        db = _get_collection().database
        config = db["system_config"].find_one({"key": "active_relevancy_prompt"})
        if config and config.get("value"):
            return config["value"]
    except Exception as e:
        print(f"  ⚠️ Failed to fetch prompt from DB, using fallback: {e}")
    
    # Fallback to the original version if DB is down or empty
    return """You are an expert consultant-project matching engine.

PROJECT JD:
Title: {title}
Description:
{description}

{consultant_sections}

IMPORTANT: Read EVERY PAR entry in each consultant's PAR LIBRARY carefully before evaluating.
Your job is to identify which specific PARs are most relevant to THIS specific project JD.

Return ONLY a valid JSON object:
{
  "evaluations": [
    {
      "consultant": "Brendi",
      "score": 0,
      "match_reasons": ["reason 1", "reason 2", "reason 3"],
      "low_score_reasons": [],
      "top_pars": []
    },
    { "consultant": "Claireee", "score": 0, "match_reasons": [], "low_score_reasons": [], "top_pars": [] },
    { "consultant": "Jack", "score": 0, "match_reasons": [], "low_score_reasons": [], "top_pars": [] },
    { "consultant": "Richu", "score": 0, "match_reasons": [], "low_score_reasons": [], "top_pars": [] }
  ]
}"""

def score_project(title, description, par_libraries):
    """
    Send JD + all 4 PAR libraries to Claude in one call.
    Returns list of evaluation dicts.
    """
    if not ANTHROPIC_API_KEY:
        print("  ❌ Anthropic API Key not found in config")
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    consultant_sections = ""
    for name in CONSULTANTS:
        sep = "=" * 60
        consultant_sections += f"\n\n{sep}\nCONSULTANT: {name}\nPAR LIBRARY:\n{par_libraries[name]}\n{sep}"

    # FETCH DYNAMIC PROMPT FROM DB
    base_prompt = get_active_prompt()
    
    # Inject values safely using replace to avoid KeyError from JSON curly braces
    prompt = base_prompt.replace("{title}", title)\
                        .replace("{description}", description)\
                        .replace("{consultant_sections}", consultant_sections)

    print("  🤖 Calling Claude 3.5 Haiku (1 call, all 4 consultants)...")

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown code fences if Claude adds them despite instructions
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            data = json.loads(raw)
            evaluations = data.get("evaluations", [])

            # Validate and sanitize
            for ev in evaluations:
                score_val = ev.get("score", 0)
                if isinstance(score_val, str):
                    # Extract digits if it's a string like "85%"
                    digits = re.findall(r"\d+", score_val)
                    score_val = int(digits[0]) if digits else 0
                
                try:
                    ev["score"] = max(0, min(100, int(score_val or 0)))
                except:
                    ev["score"] = 0

                # Strip top_pars from low scorers and low_score_reasons from high scorers
                # to enforce the schema contract at the source
                MIN = 80
                if ev["score"] >= MIN:
                    ev["top_pars"] = (ev.get("top_pars") or [])[:5]
                    ev["low_score_reasons"] = []  # not needed for high scorers
                else:
                    ev["top_pars"] = []           # do not store top_pars for low scorers
                    ev["low_score_reasons"] = (ev.get("low_score_reasons") or [])[:3]

                ev["match_reasons"] = (ev.get("match_reasons") or [])[:3]
            print(f"  ✅ Scored {len(evaluations)} consultant(s)")
            return evaluations

        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON parse error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
        except Exception as e:
            print(f"  ⚠️  Claude error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    return []
