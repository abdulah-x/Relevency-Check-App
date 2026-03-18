import time
import sys
import os
from datetime import datetime

from config import MIN_SCORE, CHECK_INTERVAL, TEST_MODE, PKT, SEND_TEST_EMAILS
from loader import load_par_libraries
from watcher import fetch_new_project_emails
from extractor import extract_jd
from scorer import score_project
from notifier import send_relevancy_email
from slack_notifier import send_slack_approval
from db_logger import log_evaluation, log_heartbeat


def main():
    # Force unbuffered output so logs appear instantly on Railway
    import functools
    global print
    print = functools.partial(print, flush=True)

    print(">>> EVALUATOR STARTING UP...", flush=True)
    print("=" * 50, flush=True)
    print("🎯 Project Relevancy Evaluator", flush=True)
    print("=" * 50, flush=True)

    from config import IMAP_EMAIL, SENDER_EMAIL, RECIPIENT_EMAILS, HEARTBEAT_INTERVAL, SLACK_BOT_TOKEN, ANTHROPIC_API_KEY
    
    # CRITICAL VARIABLE CHECK
    missing = []
    if not SLACK_BOT_TOKEN: missing.append("SLACK_BOT_TOKEN")
    if not ANTHROPIC_API_KEY: missing.append("ANTHROPIC_API_KEY")
    if not IMAP_EMAIL: missing.append("IMAP_EMAIL")
    if not RECIPIENT_EMAILS: missing.append("RECIPIENT_EMAILS")
    if not os.getenv("MONGO_URI"): missing.append("MONGO_URI")
    
    if missing:
        print(f"❌ CRITICAL ERROR: The following variables are MISSING in Railway: {', '.join(missing)}")
        print("Please add them to the Variables tab in Railway and redeploy.")
        # We continue so we can at least see the other logs
    else:
        print("✅ All critical variables detected.")

    print(f"  Watching inbox : {IMAP_EMAIL}")
    print(f"  Monitor sender : {SENDER_EMAIL}")
    print(f"  Min score      : {MIN_SCORE}%")
    print(f"  Check interval : {CHECK_INTERVAL}s")
    print(f"  Recipients     : {', '.join(RECIPIENT_EMAILS)}")
    print()

    print("📚 Loading PAR libraries...")
    try:
        par_libraries = load_par_libraries()
        print(f"  ✅ All {len(par_libraries)} libraries loaded\n")
    except Exception as e:
        print(f"  ❌ Failed to load libraries: {e}")
        return

    if TEST_MODE:
        run_test_scenario(par_libraries)
        return

    # User requested to remove Slack heartbeat to keep channel clean.
    # We still print to logs for Railway monitoring.
    print("📡 Evaluator is ONLINE and monitoring...")

    print("✅ System ready. Entering production monitoring loop...")

    check_count = 0
    while True:
        try:
            check_count += 1
            
            # Heartbeat logging
            if check_count == 1 or check_count % HEARTBEAT_INTERVAL == 0:
                print(f"\n💓 HEARTBEAT — Evaluator is running (Check #{check_count} — {datetime.now(PKT).strftime('%Y-%m-%d %H:%M:%S')} PKT)")

            print(f"🔄 Check #{check_count} — {datetime.now(PKT).strftime('%H:%M:%S')} PKT")

            log_heartbeat()
            emails = fetch_new_project_emails()

            if not emails:
                # print(f"  No new project emails. Next check in {CHECK_INTERVAL}s...")
                pass
            else:
                for uid, subject, html_body in emails:
                    try:
                        print(f"\n  📩 Processing: {subject[:70]}")

                        title, description, platform = extract_jd(subject, html_body)

                        if not description or len(description) < 50:
                            print(f"  ⚠️  Description too short ({len(description)} chars) — skipping")
                            continue

                        print(f"  📝 Title      : {title[:60]}")
                        print(f"  📄 Description: {len(description)} chars")

                        evaluations = score_project(title, description, par_libraries)
                        if not evaluations:
                            print("  ❌ Scoring failed — logging failure to DB")
                            log_evaluation(title, platform, [{"consultant": "SYSTEM", "score": 0, "match_reasons": ["AI SCORING FAILED"]}])
                            continue

                        scores_str = ", ".join(f"{e['consultant']}: {e['score']}%" for e in evaluations)
                        print(f"  📊 Scores — {scores_str}")

                        matches = [e for e in evaluations if e["score"] >= MIN_SCORE]
                        if matches:
                            # Inject the JD into each match so Slack button can carry it
                            for m in matches:
                                m["project_jd"] = description
                            print(f"  🎯 {len(matches)} consultant(s) ≥{MIN_SCORE}% — sending email + Slack")
                            send_relevancy_email(title, platform, matches)
                            send_slack_approval(title, platform, matches)
                        else:
                            print(f"  ⏭️  No matches ≥{MIN_SCORE}% — no email sent")

                        log_evaluation(title, platform, evaluations)
                    
                    except Exception as e:
                        print(f"  ⚠️  Error processing email {uid}: {e}")
                        continue

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n⏹️  Stopping...")
            break
        except Exception as e:
            print(f"  ⚠️  Runtime error: {e}")
            print(f"  Retrying in {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)




if __name__ == "__main__":
    while True:
        try:
            main()
            print("⚠️  Monitor exited — restarting in 30s...")
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n⏹️  Gracefully stopped")
            break
        except Exception as e:
            print(f"💥 Fatal: {e} — restarting in 60s...")
            time.sleep(60)
