import json
import re
import time
import anthropic
from config import ANTHROPIC_API_KEY, CONSULTANTS


def score_project(title, description, par_libraries):
    """
    Send JD + all 4 PAR libraries to Claude Haiku in one call.
    Returns list of evaluation dicts with keys: consultant, score, match_reasons, top_pars.
    """
    if not ANTHROPIC_API_KEY:
        print("  ❌ Anthropic API Key not found in config")
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    consultant_sections = ""
    for name in CONSULTANTS:
        sep = "=" * 60
        consultant_sections += (
            f"\n\n{sep}\n"
            f"CONSULTANT: {name}\n"
            f"PAR LIBRARY:\n{par_libraries[name]}\n"
            f"{sep}"
        )

    prompt = f"""You are an expert consultant-project matching engine.

PROJECT JD:
Title: {title}
Description:
{description}

{consultant_sections}

Evaluate how relevant this project is for each consultant based on their PAR (Project, Action, Result) library.

Return ONLY a valid JSON object — no markdown, no explanation, no code fences:
{{
  "evaluations": [
    {{
      "consultant": "Brendi",
      "score": 0,
      "match_reasons": ["reason 1", "reason 2", "reason 3"],
      "low_score_reasons": ["if score < 70, list specific gaps/missing skills here"],
      "top_pars": [
        {{"rank": 1, "par_text": "brief PAR summary", "relevancy_explanation": "why this PAR is relevant"}},
        {{"rank": 2, "par_text": "...", "relevancy_explanation": "..."}},
        {{"rank": 3, "par_text": "...", "relevancy_explanation": "..."}},
        {{"rank": 4, "par_text": "...", "relevancy_explanation": "..."}},
        {{"rank": 5, "par_text": "...", "relevancy_explanation": "..."}}
      ]
    }},
    {{ "consultant": "Claireee", ... }},
    {{ "consultant": "Jack", ... }},
    {{ "consultant": "Richu", ... }}
  ]
}}

Scoring guide:
- 90-100: Near-perfect match — consultant has done nearly identical work
- 70-89:  Strong match — clear overlap in domain, skills, and seniority level
- 50-69:  Moderate match — some relevant experience but notable gaps
- 0-49:   Weak match — limited or unrelated experience

Rules:
- score must be an integer between 0 and 100
- provide exactly 3 match_reasons per consultant (highlighting alignment)
- low_score_reasons: IF score < 70, provide 2-3 specific reasons WHY the match is low (e.g. missing skills, unrelated industry). if score >= 70, this can be an empty array.
- provide exactly 5 top_pars per consultant, ranked by relevancy (rank 1 = most relevant)
- par_text should be a concise one-sentence summary of what the consultant did
- relevancy_explanation should explain specifically why that PAR relates to this JD"""

    print("  🤖 Calling Claude Haiku (1 call, all 4 consultants)...")

    for attempt in range(3):
        try:
            # Using the original model name from the user's codebase
            response = client.messages.create(
                model="claude-haiku-4-5",
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
                ev["score"] = max(0, min(100, int(ev.get("score", 0))))
                ev["top_pars"] = (ev.get("top_pars") or [])[:5]
                ev["match_reasons"] = (ev.get("match_reasons") or [])[:3]
                ev["low_score_reasons"] = (ev.get("low_score_reasons") or [])[:3]
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
