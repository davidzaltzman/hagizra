import requests
import os
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

API_URL = "https://hagizra.news/api/v2/messages"
LIMIT = 20
LAST_ID_FILE = "last_id.txt"


# ---------------------------
# LAST ID
# ---------------------------
def load_last_id():
    if not os.path.exists(LAST_ID_FILE):
        return None
    with open(LAST_ID_FILE, "r", encoding="utf-8") as f:
        return f.read().strip() or None


def save_last_id(last_id):
    with open(LAST_ID_FILE, "w", encoding="utf-8") as f:
        f.write(str(last_id))


# ---------------------------
# MAIN
# ---------------------------
def main():
    last_id = load_last_id()
    offset = 0

    new_messages = []
    max_seen_id = None

    while True:
        res = requests.get(API_URL, params={
            "offset": offset,
            "limit": LIMIT,
            "direction": "desc"
        })

        data = res.json().get("messages", [])
        if not data:
            break

        stop = False

        for m in data:
            msg_id = str(m["id"])

            # שומרים תמיד את הכי חדש שראינו בפועל
            if max_seen_id is None:
                max_seen_id = msg_id

            # אם הגענו להודעה שכבר ראינו בעבר → לא עוצרים מיד
            # אלא רק מסמנים
            if last_id and msg_id == last_id:
                stop = True
                break

            new_messages.append(m)

        if stop:
            break

        offset += LIMIT

    new_messages.reverse()

    # שליחה
    send_email(new_messages)

    # 🔥 כאן התיקון הקריטי:
    # אם לא מצאנו כלום חדש → לא מעדכנים
    # אחרת שומרים את הכי חדש שראינו בפועל מה-API
    if max_seen_id:
        save_last_id(max_seen_id)

    print(f"Sent {len(new_messages)} messages")


# ---------------------------
# EMAIL (שמור אצלך כמו שהיה)
# ---------------------------
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

    body = "<html><body style='font-family:Arial;direction:rtl;'>"

    for m in messages:
        text = m["text"]

        body += f"""
        <div style="border:1px solid #ccc;padding:10px;margin-bottom:10px">
            {text}
        </div>
        """

    body += "</body></html>"

    msg.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)


if __name__ == "__main__":
    main()
