import argparse
import hashlib
import os
import re

import pandas as pd

from email_features import html_to_text

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "data", "email", "kaggle")
OUT = os.path.join(HERE, "data", "email", "prepared")

HTML_HINT = re.compile(r"<\s*(html|body|head|div|table|tr|td|p|br|a|font|span|img|style)\b", re.I)
MAX_SUBJECT, MAX_BODY = 500, 30000      # cùng giới hạn với serve.py


def read_csv(path):
    try:
        df = pd.read_csv(path, low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in ("subject", "body", "label") if c not in df.columns]
    if missing:
        raise SystemExit(f"{os.path.basename(path)} thiếu cột {missing}; cột hiện có: {list(df.columns)}")
    return df


def clean(df):
    subject = df["subject"].fillna("").astype(str).str.slice(0, MAX_SUBJECT)
    body = df["body"].fillna("").astype(str)
    body = [html_to_text(b) if HTML_HINT.search(b) else b for b in body]       # thư HTML thô → chữ, như lúc phục vụ
    body = [b[:MAX_BODY] for b in body]
    label = pd.to_numeric(df["label"], errors="coerce")
    out = pd.DataFrame({"subject": subject.values, "body": body, "label": label.values})
    out = out[out["label"].isin([0, 1])].copy()
    out["label"] = out["label"].astype(int)
    out = out[(out["subject"].str.strip() != "") | (out["body"].str.strip() != "")]
    return out.reset_index(drop=True)


def digest(subject, body):
    return hashlib.sha1(re.sub(r"\s+", " ", f"{subject} {body}".lower()).strip().encode("utf-8", "ignore")).hexdigest()


def dedupe(df, seen):
    """Bỏ dòng trùng nội dung trong chính tập này và dòng đã xuất hiện ở tập trước (seen)."""
    keep, local = [], set()
    for s, b in zip(df["subject"], df["body"]):
        h = digest(s, b)
        ok = h not in seen and h not in local
        local.add(h)
        keep.append(ok)
    df = df[keep].reset_index(drop=True)
    return df, local


def main():
    ap = argparse.ArgumentParser(description="Làm sạch, loại trùng và chia dữ liệu email Kaggle thành tập huấn luyện và tập kiểm thử ngoài")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--train", default="ceas_08,enron,ling", help="tên file (không đuôi .csv, không phân biệt hoa thường), cách nhau bằng dấu phẩy")
    ap.add_argument("--test", default="spamassasin,nazario,nigerian_fraud")
    args = ap.parse_args()

    files = {os.path.splitext(f)[0].lower(): os.path.join(args.src, f)
             for f in os.listdir(args.src) if f.lower().endswith(".csv")}
    files.pop("phishing_email", None)     # bản gộp của các file còn lại, không dùng
    train_names = [s.strip().lower() for s in args.train.split(",") if s.strip()]
    test_names = [s.strip().lower() for s in args.test.split(",") if s.strip()]
    for n in train_names + test_names:
        if n not in files:
            raise SystemExit(f"Không thấy {n}.csv trong {args.src}. Các file có: {sorted(files)}")
    both = set(train_names) & set(test_names)
    if both:
        raise SystemExit(f"Nguồn không được vừa huấn luyện vừa kiểm thử: {sorted(both)}")

    os.makedirs(args.out, exist_ok=True)
    seen, report = set(), []

    # tập kiểm thử trước: giữ nguyên, chỉ loại trùng trong chính nó và giữa các tập kiểm thử
    for n in test_names:
        raw = read_csv(files[n])
        df = clean(raw)
        n_clean = len(df)
        df, hashes = dedupe(df, seen)
        seen |= hashes
        df.to_csv(os.path.join(args.out, f"test_{n}.csv"), index=False)
        report.append((f"kiểm thử: {n}", len(raw), n_clean, len(df), df))

    # tập huấn luyện: loại mọi thư đã có trong tập kiểm thử, để kiểm thử không bị rò rỉ
    parts = []
    for n in train_names:
        raw = read_csv(files[n])
        df = clean(raw)
        n_clean = len(df)
        df, hashes = dedupe(df, seen)
        seen |= hashes
        df.insert(0, "source", n)
        parts.append(df)
        report.append((f"huấn luyện: {n}", len(raw), n_clean, len(df), df))
    train = pd.concat(parts, ignore_index=True)
    train.to_csv(os.path.join(args.out, "train.csv"), index=False)

    print(f"{'Tập':<28}{'Dòng gốc':>10}{'Sau làm sạch':>14}{'Sau loại trùng':>16}{'Nhãn 1':>9}{'Nhãn 0':>9}")
    for name, n_raw, n_clean, n_final, df in report:
        print(f"{name:<28}{n_raw:>10,}{n_clean:>14,}{n_final:>16,}{int((df['label'] == 1).sum()):>9,}{int((df['label'] == 0).sum()):>9,}")
    print(f"\nTổng huấn luyện: {len(train):,} thư, nhãn 1 = {train['label'].mean():.1%}")
    for name, _, _, _, df in report:
        if name.startswith("kiểm thử") and df["label"].nunique() < 2:
            print(f"Lưu ý: {name.split(': ')[1]} chỉ có một loại nhãn, chỉ đo được recall, không đo được báo nhầm.")
    print(f"Đã ghi vào {args.out}")


if __name__ == "__main__":
    main()