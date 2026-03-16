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

IMPORTANT: Read EVERY PAR entry in each consultant's PAR LIBRARY carefully before evaluating.
Your job is to identify which specific PARs (from the actual text provided above) are most relevant to THIS specific project JD.
The top_pars must change for every different project JD — they must reflect the actual content of the PAR library.

Return ONLY a valid JSON object — no markdown, no explanation, no code fences:
{{
  "evaluations": [
    {{
      "consultant": "Brendi",
      "score": 0,
      "match_reasons": ["reason 1", "reason 2", "reason 3"],
      "low_score_reasons": ["only if score < 70: list specific gaps here"],
      "top_pars": [
        {{"rank": 1, "par_text": "COPY the exact project/PAR title or first sentence directly from the consultant's PAR LIBRARY above", "relevancy_explanation": "why this specific PAR is relevant to THIS project JD"}},
        {{"rank": 2, "par_text": "...", "relevancy_explanation": "..."}},
        {{"rank": 3, "par_text": "...", "relevancy_explanation": "..."}},
        {{"rank": 4, "par_text": "...", "relevancy_explanation": "..."}},
        {{"rank": 5, "par_text": "...", "relevancy_explanation": "..."}}
      ]
    }},
    {{ "consultant": "Claireee", "score": 0, "match_reasons": [], "low_score_reasons": [], "top_pars": [] }},
    {{ "consultant": "Jack", "score": 0, "match_reasons": [], "low_score_reasons": [], "top_pars": [] }},
    {{ "consultant": "Richu", "score": 0, "match_reasons": [], "low_score_reasons": [], "top_pars": [] }}
  ]
}}

Scoring guide:
- 90-100: Near-perfect match — consultant has done nearly identical work
- 80-89:  Strong match — clear overlap in domain, skills, and seniority level
- 50-79:  Moderate match — some relevant experience but notable gaps
- 0-49:   Weak match — limited or unrelated experience

Rules:
- score must be an integer between 0 and 100
- provide exactly 3 match_reasons per consultant (brief phrases highlighting alignment with THIS project)
- top_pars: ONLY if score >= 80 — provide exactly 5 top PARs, selected from the actual PAR LIBRARY text above. If score < 80, set top_pars to an empty array []
- low_score_reasons: ONLY if score < 80 — list 2-3 specific reasons why the score is low (missing skills, wrong industry, seniority mismatch, etc). If score >= 80, set low_score_reasons to an empty array []
- par_text: MUST be copied verbatim — copy the project name or opening sentence of the PAR entry DIRECTLY from the consultant's PAR LIBRARY — do NOT paraphrase or invent content
- relevancy_explanation: explain specifically why that particular PAR entry relates to THIS specific project JD
- The top_pars MUST differ between consultants and MUST reflect the actual PAR library content provided"""

    print("  🤖 Calling Claude 3.5 Haiku (1 call, all 4 consultants)...")

    for attempt in range(3):
        try:
            # Using the latest Claude 3.5 Haiku model
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
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
