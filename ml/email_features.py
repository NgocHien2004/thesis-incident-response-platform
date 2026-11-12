import email
import email.policy
import re
from html.parser import HTMLParser

TOKEN = r"(?u)\b[^\W\d_]{2,}\b"                    # chỉ lấy từ gồm chữ, bỏ số (tránh học năm hay mã số của bộ dữ liệu)
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html):
    p = _Text()
    try:
        p.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    return " ".join(p.parts)


def parse_message(raw):
    """Tách tiêu đề, nội dung chữ, URL và tên tệp đính kèm từ một thư; chỉ dùng tiêu đề và nội dung để huấn luyện."""
    msg = email.message_from_bytes(raw, policy=email.policy.default) if isinstance(raw, bytes) \
        else email.message_from_string(raw, policy=email.policy.default)
    subject = str(msg.get("Subject", "") or "")
    texts, has_html, attachments = [], False, []
    for part in msg.walk():
        if part.is_multipart():
            continue
        name = part.get_filename()
        if name:
            attachments.append(name)
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_content()
        except Exception:
            continue
        if not isinstance(payload, str):
            continue
        if ctype == "text/html":
            has_html = True
            texts.append(html_to_text(payload))
        else:
            texts.append(payload)
    body = "\n".join(texts)
    urls = URL_RE.findall(body)
    return {"subject": subject, "body": body, "urls": urls, "has_html": has_html, "attachments": attachments}


def to_text(m):
    """Chuỗi đưa vào TF-IDF: tiêu đề, nội dung và vài token cấu trúc (có HTML, số URL, có tệp đính kèm)."""
    marks = []
    if m["has_html"]:
        marks.append("zzhtml")
    marks.append(f"zzurls{min(len(m['urls']), 5)}")
    if m["attachments"]:
        marks.append("zzattach")
    return f"{m['subject']}\n{m['body']}\n{' '.join(marks)}"
