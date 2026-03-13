import imaplib
import email as email_lib
import email.header
from datetime import datetime, timedelta
from config import (
    IMAP_HOST,
    IMAP_PORT,
    IMAP_EMAIL,
    IMAP_PASSWORD,
    WATCH_FROM_EMAILS,
    IMAP_LOOKBACK_DAYS,
    MAX_EMAILS_PER_CHECK,
)


def fetch_new_project_emails():
    """
    Connect to IMAP_EMAIL inbox and return list of (uid, subject, html_body)
    for unread project alert emails.
    If WATCH_FROM_EMAILS is set, only those senders are accepted.
    Non-project emails are left unread.
    """
    results = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        mail.select("INBOX")

        # Restrict to recent unread emails to avoid backlogs from old alerts.
        since_date = (datetime.now() - timedelta(days=IMAP_LOOKBACK_DAYS)).strftime("%d-%b-%Y")
        criteria = f'(UNSEEN SINCE "{since_date}")'
        _, data = mail.uid("SEARCH", None, criteria)
        uids = [u for u in data[0].split() if u]

        if not uids:
            mail.logout()
            return []

        # Process newest emails first and cap work per cycle.
        uids = sorted(uids, key=lambda u: int(u.decode() if isinstance(u, bytes) else u))
        if MAX_EMAILS_PER_CHECK > 0:
            uids = uids[-MAX_EMAILS_PER_CHECK:]

        print(
            f"  📬 {len(uids)} recent unread candidate email(s) "
            f"(lookback {IMAP_LOOKBACK_DAYS}d, max {MAX_EMAILS_PER_CHECK}/check)"
        )

        for uid in reversed(uids):
            _, msg_data = mail.uid("FETCH", uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            # Decode subject
            subject = ""
            import email.header
            for part, enc in email.header.decode_header(msg.get("Subject", "")):
                if isinstance(part, bytes):
                    subject += part.decode(enc or "utf-8", errors="replace")
                else:
                    subject += str(part)

            from_addr = (msg.get("From", "") or "").lower()
            print(f"    🔍 Inspecting: {subject[:70]} (from: {from_addr})")

            # Sender Filter Check
            if WATCH_FROM_EMAILS:
                matched_sender = any(addr in from_addr for addr in WATCH_FROM_EMAILS)
                if not matched_sender:
                    print(f"      ⏭️  Skipping sender (not in WATCH_FROM_EMAILS: {WATCH_FROM_EMAILS})")
                    continue
            
            # Subject Filter Check
            is_project = (
                "🔔" in subject
                or "btg" in subject.lower()
                or "catalant" in subject.lower()
                or "project" in subject.lower()
                or "match" in subject.lower()
                or "new solicitation" in subject.lower()
            )
            
            if not is_project:
                print("      ⏭️  Skipping subject (doesn't match project keywords)")
                continue

            # Extract HTML body
            html_body = None
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
            elif msg.get_content_type() == "text/html":
                html_body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            if html_body:
                results.append((uid, subject, html_body))
                mail.uid("STORE", uid, "+FLAGS", "\\Seen")  # mark as read

        mail.logout()

    except Exception as e:
        print(f"  ❌ IMAP error: {e}")

    return results
