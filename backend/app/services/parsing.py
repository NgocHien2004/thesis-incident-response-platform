import csv
import email
import email.policy
import json
import math
import re
import zipfile
import zlib
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Iterator, Optional

class ValidationError(Exception):
    pass

EMAIL_COLUMNS = ("subject", "body", "sender", "urls")
MAX_BODY_CHARS = 20000
URL_SPLIT = re.compile(r"[\s,;|]+")
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
# Giới hạn khi đọc thư thô (.eml, .zip); đặt thấp để file ZIP nén cực mạnh không làm cạn bộ nhớ
MAX_EML_BYTES = 5 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 500 * 1024 * 1024
MAX_ATTACHMENTS = 20

def _key(name) -> str:
    return str(name).strip().casefold()

def _dedupe_headers(headers: list) -> list:
    # CIC-IDS2017 có hai cột cùng tên "Fwd Header Length": đặt tên như pandas (.1, .2)
    seen, out = {}, []
    for h in headers:
        h = str(h).strip()
        if h in seen:
            seen[h] += 1
            out.append(f"{h}.{seen[h]}")
        else:
            seen[h] = 0
            out.append(h)
    return out

def _sniff_delimiter(first_line: str) -> str:
    counts = {d: first_line.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","

def _iter_csv(path: str) -> Iterator[dict]:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            first = f.readline()
            if not first.strip():
                raise ValidationError("File CSV rỗng hoặc dòng tiêu đề trống")
            f.seek(0)
            reader = csv.reader(f, delimiter=_sniff_delimiter(first))
            header = _dedupe_headers(next(reader))
            if not any(header):
                raise ValidationError("Dòng tiêu đề của file CSV trống")
            n = 0
            for row in reader:
                if not row or all(c.strip() == "" for c in row):
                    continue
                n += 1
                if len(row) != len(header):
                    raise ValidationError(f"Dòng dữ liệu {n}: có {len(row)} cột, tiêu đề có {len(header)} cột")
                yield dict(zip(header, row))
    except UnicodeDecodeError:
        raise ValidationError("File CSV phải được lưu bằng UTF-8")
    except csv.Error as e:
        raise ValidationError(f"File CSV sai cấu trúc: {e}")

def _iter_json(path: str) -> Iterator[dict]:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except UnicodeDecodeError:
        raise ValidationError("File JSON phải được lưu bằng UTF-8")
    except json.JSONDecodeError as e:
        raise ValidationError(f"File JSON không hợp lệ (dòng {e.lineno}, cột {e.colno})")
    if isinstance(data, dict):
        data = data.get("rows", data.get("data"))
    if not isinstance(data, list):
        raise ValidationError("File JSON phải là một mảng đối tượng, hoặc đối tượng có khóa \"rows\"")
    for i, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValidationError(f"Phần tử {i} của file JSON không phải đối tượng")
        yield {str(k).strip(): v for k, v in item.items()}

# ---------- thư thô: .eml và .zip chứa nhiều .eml ----------
class _Html(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "a":
            for k, v in attrs:
                if k == "href" and v and v.strip().lower().startswith(("http://", "https://")):
                    self.links.append(v.strip())

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

def _html_to_text(html: str) -> tuple:
    # Trả về (chữ hiển thị, các liên kết trong thẻ href); liên kết ẩn sau chữ hiển thị là dấu hiệu phishing hay gặp
    p = _Html()
    try:
        p.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html), []
    return " ".join(p.parts), p.links

def _part_text(part) -> Optional[str]:
    try:
        text = part.get_content()
        if isinstance(text, str):
            return text
    except Exception:
        pass
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        return None
    if not isinstance(payload, bytes):
        return None
    for enc in (part.get_content_charset() or "utf-8", "utf-8"):
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            continue
    return None

def parse_eml(raw: bytes, name: str = "") -> dict:
    """Đọc một thư .eml thành {subject, body, sender, urls, has_html, attachments}.
    Nội dung ưu tiên phần văn bản thuần; chỉ dùng phần HTML khi phần thuần trống hoặc quá ngắn.
    Tệp đính kèm chỉ ghi tên, không đọc nội dung."""
    label = f'Thư "{name}"' if name else "File .eml"
    try:
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        has_headers = any(msg.get(h) for h in ("From", "Subject", "To", "Date", "Message-ID"))
        subject = str(msg.get("Subject", "") or "").strip()
        from_raw = str(msg.get("From", "") or "").strip()
        plain, html, links, attachments = [], [], [], []
        for part in msg.walk():
            if part.is_multipart():
                continue
            try:
                fname = part.get_filename()
            except Exception:
                fname = None
            if fname:
                if len(attachments) < MAX_ATTACHMENTS:
                    attachments.append(str(fname)[:255])
                continue
            ctype = part.get_content_type()
            if ctype not in ("text/plain", "text/html"):
                continue
            text = _part_text(part)
            if text is None:
                continue
            if ctype == "text/html":
                t, l = _html_to_text(text)
                html.append(t)
                links += l
            else:
                plain.append(text)
    except Exception:
        raise ValidationError(f"{label}: không đọc được, có thể không phải file thư hợp lệ")
    if not has_headers:
        raise ValidationError(f"{label}: không thấy tiêu đề thư (From, Subject...), có thể không phải file .eml")
    plain_text, html_text = "\n".join(plain), "\n".join(html)
    body = plain_text if len(plain_text.strip()) >= 20 or not html_text.strip() else html_text
    urls, seen = [], set()
    for u in URL_RE.findall(body) + links:
        u = u.rstrip(".,;:!?")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    sender = (parseaddr(from_raw)[1] or from_raw)[:320]
    if not subject and not body.strip():
        raise ValidationError(f"{label}: không có tiêu đề và nội dung")
    return {"subject": subject, "body": body, "sender": sender, "urls": urls[:50],
            "has_html": bool(html), "attachments": attachments}

def _iter_eml(path: str) -> Iterator[dict]:
    try:
        with open(path, "rb") as f:
            raw = f.read(MAX_EML_BYTES + 1)
    except OSError:
        raise ValidationError("Không đọc được file .eml")
    if len(raw) > MAX_EML_BYTES:
        raise ValidationError(f"File .eml lớn hơn {MAX_EML_BYTES // (1024 * 1024)} MB")
    yield parse_eml(raw)

def _is_eml_member(filename: str) -> bool:
    name = filename.replace("\\", "/")
    base = name.rsplit("/", 1)[-1]
    return name.lower().endswith(".eml") and not name.startswith("__MACOSX/") and not base.startswith("._")

def _iter_zip(path: str) -> Iterator[dict]:
    # Mỗi file .eml trong ZIP là một dòng; thứ tự theo tên file. Bỏ qua thư mục, file ngoài .eml và rác của macOS.
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise ValidationError("File ZIP hỏng hoặc không phải file ZIP")
    with zf:
        members = sorted((i for i in zf.infolist() if not i.is_dir() and _is_eml_member(i.filename)),
                         key=lambda i: i.filename)
        if not members:
            raise ValidationError("File ZIP không chứa file .eml nào")
        total = 0
        for info in members:
            name = info.filename.replace("\\", "/")[:255]
            try:
                with zf.open(info) as f:
                    raw = f.read(MAX_EML_BYTES + 1)
            except (RuntimeError, NotImplementedError, zipfile.BadZipFile, zlib.error, EOFError):
                raise ValidationError(f'Không đọc được "{name}" trong ZIP (file bị mã hóa hoặc hỏng)')
            if len(raw) > MAX_EML_BYTES:
                raise ValidationError(f'"{name}" lớn hơn {MAX_EML_BYTES // (1024 * 1024)} MB')
            total += len(raw)
            if total > MAX_ZIP_TOTAL_BYTES:
                raise ValidationError(f"Tổng dung lượng sau giải nén vượt {MAX_ZIP_TOTAL_BYTES // (1024 * 1024)} MB")
            row = parse_eml(raw, name)
            row["source_file"] = name
            yield row

def iter_raw(path: str, fmt: str) -> Iterator[dict]:
    if fmt == "csv":
        return _iter_csv(path)
    if fmt == "json":
        return _iter_json(path)
    if fmt == "eml":
        return _iter_eml(path)
    if fmt == "zip":
        return _iter_zip(path)
    raise ValidationError("Định dạng file không được hỗ trợ")

def _to_float(value, row_no: int, col: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValidationError(f"Dòng {row_no}, cột \"{col}\": giá trị không phải số")
    try:
        x = float(str(value).strip()) if not isinstance(value, (int, float)) else float(value)
    except ValueError:
        raise ValidationError(f"Dòng {row_no}, cột \"{col}\": \"{str(value)[:30]}\" không phải số")
    # Infinity/NaN có sẵn trong CIC-IDS2017: quy về 0, giống dịch vụ AI
    return x if math.isfinite(x) else 0.0

def _urls(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        items = [str(v).strip() for v in value]
    else:
        items = URL_SPLIT.split(str(value).strip())
    return [u for u in items if u][:50]

def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in ("1", "true", "yes")

def _names(value) -> list:
    if value is None:
        return []
    items = value if isinstance(value, list) else re.split(r"[;|]", str(value))
    return [s for s in (str(v).strip()[:255] for v in items) if s][:MAX_ATTACHMENTS]

class Schema:
    # features: danh sách cột bắt buộc của mô hình luồng mạng (None với email)
    def __init__(self, data_type: str, features: Optional[list] = None):
        self.data_type = data_type
        self.features = features
        if data_type == "network":
            if not features:
                raise ValidationError("Chưa có danh sách cột đặc trưng của mô hình luồng mạng")
            self.lookup = {_key(f): f for f in features}
        else:
            self.lookup = {c: c for c in EMAIL_COLUMNS}

    def check_columns(self, present: list):
        keys = {_key(c) for c in present}
        missing = [orig for k, orig in self.lookup.items() if k not in keys]
        if missing:
            if self.data_type == "network":
                shown = ", ".join(str(m).strip() for m in missing[:8])
                more = f" (và {len(missing) - 8} cột khác)" if len(missing) > 8 else ""
                raise ValidationError(f"Thiếu {len(missing)}/{len(self.lookup)} cột đặc trưng CIC-IDS2017: {shown}{more}")
            raise ValidationError("File email phải có đủ các cột: subject, body, sender, urls. Thiếu: " + ", ".join(missing))

    def convert(self, raw: dict, row_no: int) -> dict:
        by_key = {_key(k): v for k, v in raw.items()}
        if self.data_type == "network":
            return {orig: _to_float(by_key.get(k), row_no, str(orig).strip()) for k, orig in self.lookup.items()}
        subject = str(by_key.get("subject") or "")
        body = str(by_key.get("body") or "")
        if not subject.strip() and not body.strip():
            raise ValidationError(f"Dòng {row_no}: subject và body đều trống")
        out = {"subject": subject[:500], "body": body[:MAX_BODY_CHARS],
               "sender": str(by_key.get("sender") or "")[:320], "urls": _urls(by_key.get("urls")),
               "has_html": _truthy(by_key.get("has_html")), "attachments": _names(by_key.get("attachments"))}
        if by_key.get("source_file"):
            out["source_file"] = str(by_key["source_file"])[:255]
        return out

def validate_file(path: str, fmt: str, schema: Schema, max_rows: int) -> int:
    # Quét toàn bộ file một lần: kiểm tra cột và từng ô, trả về số dòng dữ liệu
    count = 0
    checked_columns = False
    for raw in iter_raw(path, fmt):
        if not checked_columns:
            schema.check_columns(list(raw.keys()))
            checked_columns = True
        count += 1
        if count > max_rows:
            raise ValidationError(f"File vượt quá {max_rows} dòng dữ liệu cho phép")
        schema.convert(raw, count)
    if count == 0:
        raise ValidationError("File không có dòng dữ liệu nào")
    return count

def iter_rows(path: str, fmt: str, schema: Schema) -> Iterator[tuple]:
    # Trả về (số thứ tự dòng dữ liệu tính từ 1, dòng đã chuẩn hóa)
    for i, raw in enumerate(iter_raw(path, fmt), 1):
        yield i, schema.convert(raw, i)