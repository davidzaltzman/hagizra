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
# טקסט אמיתי
# ---------------------------
def has_real_text(text: str) -> bool:
    return bool(re.search(r"[a-zA-Z\u0590-\u05FF]", text))


def is_noise_only(text: str) -> bool:
    cleaned = re.sub(r"[\s\|\*\-_:•]", "", text)
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", cleaned)
    return cleaned == ""


def has_media(text: str) -> bool:
    return ("video-embedded#" in text or "image-embedded#" in text)


# ---------------------------
# ניקוי
# ---------------------------
def clean_text(text: str, media_mode: bool = False) -> str:
    text = re.sub(r"\[video-embedded#\]\([^)]+\)", "", text)
    text = re.sub(r"\[image-embedded#\]\([^)]+\)", "", text)
    text = re.sub(r"\[quote-embedded#\]", "", text)

    text = re.sub(r"<span.*?>.*?</span>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)

    text = re.sub(r"https?://\S+", "", text)

    if media_mode:
        text = re.sub(r"[\U00010000-\U0010ffff]", "", text)

    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------
# ציטוט
# ---------------------------
def parse_quote(text: str):
    match = re.search(r"\[quote-embedded#\]\((\d+)@(.*?)\)\s*(.*)", text, re.DOTALL)
    if not match:
        return None, text

    return match.group(2).strip(), match.group(3).strip()


# ---------------------------
# HTML
# ---------------------------
def format_message_html(raw_text: str):
    media = has_media(raw_text)
    quote, reply = parse_quote(raw_text)

    parts = []

    if quote:
        q = clean_text(quote, media_mode=media)
        if has_real_text(q) and not is_noise_only(q):
            parts.append(f"""
            <div style="border:1px solid #99d6ff;padding:10px;border-radius:10px;background:#eaf6ff;">
            🌟 <b>ציטוט:</b><br><i>{q}</i>
            </div>
            """)

    if reply:
        r = clean_text(reply, media_mode=media)

        if not has_real_text(r) or is_noise_only(r):
            return ""

        parts.append(f"""
        <div style="border:1px solid #a9dfbf;padding:10px;border-radius:10px;background:#eafaf1;">
        {r}
        </div>
        """)

    return "\n".join(parts) if parts else ""


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

    body = "<html><body style='font-family:Arial;direction:rtl;'>"

    valid = False

    for m in messages:
        html = format_message_html(m["text"])
        if not html:
            continue

        valid = True
        body += f"<div style='border:1px solid #ccc;padding:10px;margin-bottom:15px'>{html}</div>"

    body += "</body></html>"

    if not valid:
        return

    msg.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)


# ---------------------------
# MAIN
# ---------------------------
def main():
    last_id = load_last_id()
    offset = 0

    new_messages = []
    max_seen_id = None  # 🔥 זה התיקון האמיתי

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

            # 🔥 תמיד שומרים את המקסימום
            if max_seen_id is None:
                max_seen_id = msg_id
            else:
                max_seen_id = max(max_seen_id, msg_id)

            if last_id and msg_id == last_id:
                stop = True
                break

            new_messages.append(m)

        if stop:
            break

        offset += LIMIT

    new_messages.reverse()

    send_email(new_messages)

    # 🔥 קריטי: שומרים את הכי גבוה באמת
    if max_seen_id:
        save_last_id(max_seen_id)

    print(f"Sent {len(new_messages)} messages")


if __name__ == "__main__":
    main()
