import csv
import json
import math
import re
from typing import Iterator, Optional

class ValidationError(Exception):
    pass

EMAIL_COLUMNS = ("subject", "body", "sender", "urls")
MAX_BODY_CHARS = 20000
URL_SPLIT = re.compile(r"[\s,;|]+")

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

def iter_raw(path: str, fmt: str) -> Iterator[dict]:
    return _iter_csv(path) if fmt == "csv" else _iter_json(path)

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
        return {"subject": subject[:500], "body": body[:MAX_BODY_CHARS],
                "sender": str(by_key.get("sender") or "")[:320], "urls": _urls(by_key.get("urls"))}

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
