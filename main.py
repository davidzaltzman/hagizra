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
# זיהוי האם יש מדיה
# ---------------------------
def has_media(text: str) -> bool:
    return (
        "[video-embedded#]" in text or
        "[image-embedded#]" in text
    )


# ---------------------------
# ניקוי טקסט בסיסי
# ---------------------------
def clean_text(text: str, media_mode: bool = False) -> str:

    # הסרת embeds
    text = re.sub(r"\[video-embedded#\]\([^)]+\)", "", text)
    text = re.sub(r"\[image-embedded#\]\([^)]+\)", "", text)

    # הסרת quote marker
    text = re.sub(r"\[quote-embedded#\]", "", text)

    # הסרת HTML spans (פרסומות)
    text = re.sub(r"<span.*?>.*?</span>", "", text, flags=re.DOTALL)

    # הסרת HTML
    text = re.sub(r"<[^>]+>", "", text)

    # הסרת קישורים markdown
    text = re.sub(r"https?://\S+", "", text)

    # הסרת אימוג'ים (במצב מדיה בלבד)
    if media_mode:
        text = re.sub(r"[\U00010000-\U0010ffff]", "", text)

    # ניקוי כוכביות ורווחים
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------
# זיהוי ציטוט
# ---------------------------
def parse_quote(text: str):
    match = re.search(
        r"\[quote-embedded#\]\((\d+)@(.*?)\)\s*(.*)",
        text,
        re.DOTALL
    )

    if not match:
        return None, text

    quote_text = match.group(2).strip()
    reply_text = match.group(3).strip()

    return quote_text, reply_text


# ---------------------------
# עיצוב הודעה
# ---------------------------
def format_message_html(raw_text: str):

    media = has_media(raw_text)

    quote, reply = parse_quote(raw_text)

    html_parts = []

    # ---------------- ציטוט ----------------
    if quote:
        html_parts.append(f"""
        <div style="
            border:1px solid #99d6ff;
            border-radius:10px;
            padding:10px;
            margin-bottom:10px;
            background:#eaf6ff;">
            🌟 <b>ציטוט:</b><br>
            <i>{clean_text(quote, media_mode=media)}</i>
        </div>
        """)

    # ---------------- תגובה ----------------
    if reply:

        safe_reply = clean_text(reply, media_mode=media)

        if safe_reply:

            html_parts.append(f"""
            <div style="
                border:1px solid #a9dfbf;
                border-radius:10px;
                padding:10px;
                background:#eafaf1;">
                {safe_reply}
            </div>
            """)

    return "\n".join(html_parts)


# ---------------------------
# ID אחרון
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

    body = "<html><body style='font-family:Arial; direction:rtl;'>"

    for m in messages:
        formatted = format_message_html(m["text"])

        body += """
        <div style="
            border:1px solid #ccc;
            border-radius:10px;
            padding:10px;
            margin-bottom:15px;">
        """
        body += formatted
        body += "</div>"

    body += "</body></html>"

    msg.attach(MIMEText(body, "html", "utf-8"))

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

            if newest_id is None:
                newest_id = msg_id

            if last_id is not None and msg_id == last_id:
                stop = True
                break

            new_messages.append(m)

        if stop:
            break

        offset += LIMIT

    new_messages.reverse()

    send_email(new_messages)

    if newest_id:
        save_last_id(newest_id)

    print(f"Sent {len(new_messages)} messages")


if __name__ == "__main__":
    main()
