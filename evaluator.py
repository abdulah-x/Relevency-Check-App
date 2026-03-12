import time
import sys
from datetime import datetime

from config import MIN_SCORE, CHECK_INTERVAL, TEST_MODE, PKT, SEND_TEST_EMAILS
from loader import load_par_libraries
from watcher import fetch_new_project_emails
from extractor import extract_jd
from scorer import score_project
from notifier import send_relevancy_email
from db_logger import log_evaluation, log_below_threshold


def main():
    print("=" * 50)
    print("🎯 Project Relevancy Evaluator")
    print("=" * 50)

    from config import IMAP_EMAIL, SENDER_EMAIL, RECIPIENT_EMAILS, HEARTBEAT_INTERVAL
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

    check_count = 0
    while True:
        try:
            check_count += 1
            
            # Heartbeat logging
            if check_count == 1 or check_count % HEARTBEAT_INTERVAL == 0:
                print(f"\n💓 HEARTBEAT — Evaluator is running (Check #{check_count} — {datetime.now(PKT).strftime('%Y-%m-%d %H:%M:%S')} PKT)")

            print(f"🔄 Check #{check_count} — {datetime.now(PKT).strftime('%H:%M:%S')} PKT")

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
                            print("  ❌ Scoring failed — skipping")
                            continue

                        scores_str = ", ".join(f"{e['consultant']}: {e['score']}%" for e in evaluations)
                        print(f"  📊 Scores — {scores_str}")

                        matches = [e for e in evaluations if e["score"] >= MIN_SCORE]
                        if matches:
                            print(f"  🎯 {len(matches)} consultant(s) ≥{MIN_SCORE}% — sending email")
                            send_relevancy_email(title, platform, matches)
                        else:
                            print(f"  ⏭️  No matches ≥{MIN_SCORE}% — no email sent")

                        log_evaluation(title, platform, evaluations)
                        low_relevancy = [e for e in evaluations if e.get("score", 0) < MIN_SCORE]
                        if low_relevancy:
                            log_below_threshold(title, platform, low_relevancy)
                    
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


def run_test_scenario(par_libraries):
    print("🧪 TEST MODE — using sample JD, skipping IMAP\n")
    test_title = "Interim CFO / Finance Transformation"
    test_desc  = (
        "We are looking for a senior finance executive to lead a full finance transformation "
        "for a mid-market private equity-backed company. Scope includes FP&A redesign, ERP "
        "selection, building out a high-performing finance team, and board-level reporting. "
        "6-month engagement, part-time fractional, remote with occasional travel."
    )
    print(f"  Title: {test_title}")
    print(f"  Description: {test_desc[:80]}...\n")
    evaluations = score_project(test_title, test_desc, par_libraries)
    if not evaluations:
        print("❌ Scoring failed")
        return
    print("\n  Score summary:")
    for ev in evaluations:
        print(f"    {ev['consultant']}: {ev['score']}%")
    matches = [e for e in evaluations if e["score"] >= MIN_SCORE]
    if matches:
        if SEND_TEST_EMAILS:
            print(f"\n  🎯 {len(matches)} consultant(s) ≥{MIN_SCORE}% — sending test email")
            send_relevancy_email(test_title, "BTG", matches)
        else:
            print(f"\n  🎯 {len(matches)} consultant(s) ≥{MIN_SCORE}% — test mode, email sending disabled")
    else:
        print(f"\n  ⏭️  No consultants ≥{MIN_SCORE}% — no email sent")
    log_evaluation(test_title, "BTG", evaluations)
    low_relevancy = [e for e in evaluations if e.get("score", 0) < MIN_SCORE]
    if low_relevancy:
        log_below_threshold(test_title, "BTG", low_relevancy)


if __name__ == "__main__":
    while True:
        try:
            main()
            if TEST_MODE:
                break
            print("⚠️  Monitor exited — restarting in 30s...")
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n⏹️  Gracefully stopped")
            break
        except Exception as e:
            print(f"💥 Fatal: {e} — restarting in 60s...")
            time.sleep(60)
