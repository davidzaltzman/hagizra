import requests
import os
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

API_URL = "https://hagizra.news/api/v2/messages"
LIMIT = 20
LAST_ID_FILE = "last_id.txt"


# =========================
# ניקוי טקסט בסיסי
# =========================
def clean_text(text: str) -> str:
    text = re.sub(r"\*\*", "", text)  # כוכביות
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # לינקים
    text = re.sub(r"\[video-embedded.*?\]", "", text)  # וידאו
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# =========================
# חילוץ ציטוטים אם קיימים
# =========================
def parse_message(msg: dict) -> str:
    raw = msg.get("text", "")

    # אם יש quote embedded
    if "quote-embedded" in raw or "ציטוט" in raw:
        parts = raw.split("\n", 1)

        quote_part = parts[0].strip()
        reply_part = parts[1].strip() if len(parts) > 1 else ""

        return (
            "↩️ ציטוט:\n"
            f"> {clean_text(quote_part)}\n\n"
            "🗨️ תגובה:\n"
            f"{clean_text(reply_part)}"
        ).strip()

    # הודעה רגילה
    return "🗨️ הודעה:\n" + clean_text(raw)


# =========================
# קריאת ID אחרון
# =========================
def load_last_id():
    if not os.path.exists(LAST_ID_FILE):
        return None
    with open(LAST_ID_FILE, "r", encoding="utf-8") as f:
        return f.read().strip() or None


# =========================
# שמירת ID אחרון (נוצר לבד)
# =========================
def save_last_id(last_id):
    with open(LAST_ID_FILE, "w", encoding="utf-8") as f:
        f.write(str(last_id))


# =========================
# שליחת מייל
# =========================
def send_email(messages):
    if not messages:
        return

    EMAIL_FROM = os.getenv("EMAIL_FROM")
    EMAIL_TO = os.getenv("EMAIL_TO")
    EMAIL_PASS = os.getenv("EMAIL_PASSWORD")

    msg = MIMEMultipart()
    msg["Subject"] = f"📬 {len(messages)} הודעות חדשות"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    body = ""

    for m in messages:
        formatted = parse_message(m)
        body += f"\n\n---\nID: {m['id']}\n\n{formatted}\n"

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)


# =========================
# לוגיקה ראשית
# =========================
def main():

    last_id = load_last_id()
    offset = 0

    new_messages = []
    newest_id = None
    stop = False

    while True:

        res = requests.get(API_URL, params={
            "offset": offset,
            "limit": LIMIT,
            "direction": "desc"
        })

        data = res.json().get("messages", [])

        if not data:
            break

        for m in data:
            msg_id = str(m["id"])

            if newest_id is None:
                newest_id = msg_id

            if last_id and msg_id == last_id:
                stop = True
                break

            new_messages.append(m)

        if stop:
            break

        offset += LIMIT

    # ישן → חדש
    new_messages.reverse()

    # שליחה
    send_email(new_messages)

    # שמירת ID אחרון
    if newest_id:
        save_last_id(newest_id)

    print(f"Sent {len(new_messages)} new messages")


if __name__ == "__main__":
    main()
