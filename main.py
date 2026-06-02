import requests
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

API_URL = "https://hagizra.news/api/v2/messages"

LIMIT = 20
RAW_FILE = "messages_raw.json"
IDS_FILE = "last_ids.txt"


def load_sent_ids():
    if not os.path.exists(IDS_FILE):
        return set()

    with open(IDS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())


def save_sent_ids(ids):
    with open(IDS_FILE, "w", encoding="utf-8") as f:
        for i in ids:
            f.write(str(i) + "\n")


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


def main():

    sent_ids = load_sent_ids()
    offset = 0

    new_messages = []
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

            # אם כבר ראינו את ההודעה הזו → עוצרים הכל
            if msg_id in sent_ids:
                stop = True
                break

            new_messages.append(m)
            sent_ids.add(msg_id)

        if stop:
            break

        offset += LIMIT

    # הופכים לישן → חדש
    new_messages.reverse()

    send_email(new_messages)
    save_sent_ids(sent_ids)

    print(f"Sent {len(new_messages)} new messages")


if __name__ == "__main__":
    main()
