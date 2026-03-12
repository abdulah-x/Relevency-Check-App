import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAILS, MIN_SCORE, PKT


def _esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def create_relevancy_email_html(title, platform, matches):
    now = datetime.now(PKT).strftime("%Y-%m-%d %H:%M:%S")
    platform_color = "#0e7490" if platform == "BTG" else "#1a6b3c"

    consultant_blocks = ""
    for ev in matches:
        name    = ev.get("consultant", "Unknown")
        score   = ev.get("score", 0)
        reasons = ev.get("match_reasons", [])
        pars    = ev.get("top_pars", [])

        score_color = "#16a34a" if score >= 90 else ("#d97706" if score >= 70 else "#dc2626")

        reasons_html = "".join(
            f"<li style='margin-bottom:6px;color:#374151;'>{_esc(r)}</li>"
            for r in reasons
        )

        par_rows = ""
        for par in pars:
            rank    = par.get("rank", "")
            par_txt = _esc(par.get("par_text", ""))
            expl    = _esc(par.get("relevancy_explanation", ""))
            bg      = "#f9fafb" if int(rank or 0) % 2 == 0 else "#ffffff"
            par_rows += (
                f"<tr style='background:{bg};'>"
                f"<td style='padding:8px 12px;font-weight:bold;color:#6b7280;width:36px;"
                f"text-align:center;border-bottom:1px solid #e5e7eb;'>#{rank}</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;'>"
                f"<div style='font-weight:600;color:#1f2937;margin-bottom:4px;'>{par_txt}</div>"
                f"<div style='color:#6b7280;font-size:12px;font-style:italic;'>{expl}</div>"
                f"</td></tr>"
            )

        gaps = ev.get("low_score_reasons", []) if score < MIN_SCORE else []
        gaps_html = ""
        if gaps:
            gaps_list = "".join(f"<li style='margin-bottom:4px;color:#991b1b;'>{_esc(g)}</li>" for g in gaps)
            gaps_html = f"""
            <div style="background:#fef2f2;padding:12px 20px;border-bottom:1px solid #fee2e2;">
              <div style="font-size:11px;font-weight:bold;color:#991b1b;text-transform:uppercase;
                    letter-spacing:1px;margin-bottom:6px;">Gaps / Reasons for Lower Score</div>
              <ul style="margin:0;padding-left:18px;">{gaps_list}</ul>
            </div>"""

        consultant_blocks += f"""
        <div style="margin-bottom:28px;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
          <div style="background:#1e3a5f;padding:14px 20px;">
            <span style="color:#fff;font-size:17px;font-weight:700;">👤 {_esc(name)}</span>
            <span style="float:right;background:{score_color};color:#fff;padding:4px 14px;
                  border-radius:20px;font-size:15px;font-weight:bold;">{score}%</span>
          </div>
          <div style="padding:14px 20px;background:#f8fafc;border-bottom:1px solid #e5e7eb;">
            <div style="font-size:11px;font-weight:bold;color:#6b7280;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:8px;">Why this matches</div>
            <ul style="margin:0;padding-left:18px;">{reasons_html}</ul>
          </div>
          {gaps_html}
          <div>
            <div style="padding:10px 20px 6px;font-size:11px;font-weight:bold;color:#6b7280;
                  text-transform:uppercase;letter-spacing:1px;background:#fff;">Top 5 Relevant PARs</div>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">{par_rows}</table>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;color:#333;">
  <div style="max-width:750px;margin:30px auto;background:#fff;border-radius:10px;
       overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,0.12);">
    <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:24px 28px;">
      <p style="margin:0;color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;">
        Relevancy Evaluator &nbsp;|&nbsp;
        <span style="background:{platform_color};padding:2px 8px;border-radius:3px;">{platform}</span>
      </p>
      <h2 style="margin:8px 0 0;color:#fff;font-size:22px;font-weight:700;">🎯 Consultant Match Report</h2>
    </div>
    <div style="padding:20px 28px;border-bottom:2px solid #e5e7eb;background:#f8fafc;">
      <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Project</div>
      <div style="font-size:18px;font-weight:700;color:#1a252f;">{_esc(title)}</div>
      <div style="font-size:12px;color:#9ca3af;margin-top:6px;">
        Evaluated at {now} PKT &nbsp;|&nbsp; {len(matches)} consultant(s) matched (&ge;{MIN_SCORE}%)
      </div>
    </div>
    <div style="padding:24px 28px;">{consultant_blocks}</div>
    <div style="background:#f8f9fa;padding:14px 28px;border-top:1px solid #eee;
         font-size:12px;color:#999;text-align:center;">
      Relevancy Evaluator &nbsp;|&nbsp; Automated report &nbsp;|&nbsp; {now}
    </div>
  </div>
</body></html>"""


def send_relevancy_email(title, platform, matches):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎯 [{platform}] {title[:55]} — {len(matches)} Match(es)"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = ", ".join(RECIPIENT_EMAILS)
        msg.attach(MIMEText(create_relevancy_email_html(title, platform, matches), "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"  📧 Relevancy email sent — {len(matches)} match(es)")
        return True
    except Exception as e:
        print(f"  ❌ Email failed: {e}")
        return False
