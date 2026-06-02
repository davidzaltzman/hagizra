import requests
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

API_URL = "https://hagizra.news/api/v2/messages"

LIMIT = 20
LAST_ID_FILE = "last_id.txt"


# ---------------------------
# קריאת ID אחרון
# ---------------------------
def load_last_id():
    if not os.path.exists(LAST_ID_FILE):
        return None

    with open(LAST_ID_FILE, "r", encoding="utf-8") as f:
        return f.read().strip() or None


# ---------------------------
# שמירת ID אחרון
# ---------------------------
def save_last_id(last_id):
    with open(LAST_ID_FILE, "w", encoding="utf-8") as f:
        f.write(str(last_id))


# ---------------------------
# שליחת מייל
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

    body = ""
    for m in messages:
        body += f"\n\n---\nID: {m['id']}\n\n{m['text']}\n"

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)


# ---------------------------
# לוגיקה ראשית
# ---------------------------
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

            # שומר את הכי חדש שנמצא
            if newest_id is None:
                newest_id = msg_id

            # אם הגענו להודעה שכבר ראינו → עצירה
            if last_id is not None and msg_id == last_id:
                stop = True
                break

            new_messages.append(m)

        if stop:
            break

        offset += LIMIT

    # להפוך לישן → חדש
    new_messages.reverse()

    # שליחת מייל
    send_email(new_messages)

    # שמירת ID אחרון
    if newest_id:
        save_last_id(newest_id)

    print(f"Sent {len(new_messages)} new messages")


if __name__ == "__main__":
    main()
