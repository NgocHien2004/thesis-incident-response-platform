import argparse
import hashlib
import json
import os
import re
import time
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from email_features import TOKEN, URL_RE, html_to_text, to_text

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "data", "email", "kaggle")
MODELS = os.path.join(HERE, "models")
RESULTS = os.path.join(HERE, "results")

# thứ tự này quyết định nguồn nào giữ lại khi hai nguồn có cùng một thư
SOURCES = ["ceas_08", "enron", "ling", "spamassasin", "nazario", "nigerian_fraud"]
THRESHOLDS = {"auto_close": 0.15, "review": 0.50, "alert": 0.80}   # 0.80 = ngưỡng sinh cảnh báo mặc định của hệ thống
HTML_HINT = re.compile(r"<\s*(html|body|head|div|table|tr|td|p|br|a|font|span|img|style)\b", re.I)
MAX_SUBJECT, MAX_BODY = 500, 30000      # cùng giới hạn với serve.py


# ---------- đọc và làm sạch ----------
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


def load_source(path, name):
    df = read_csv(path)
    year = pd.Series(np.nan, index=df.index)
    if name == "nazario" and "date" in df.columns:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            year = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.year
    subject = df["subject"].fillna("").astype(str).str.slice(0, MAX_SUBJECT)
    body = df["body"].fillna("").astype(str)
    body = [(html_to_text(b) if HTML_HINT.search(b) else b)[:MAX_BODY] for b in body]   # thư HTML thô → chữ, như lúc phục vụ
    out = pd.DataFrame({"source": name, "subject": subject.values, "body": body,
                        "label": pd.to_numeric(df["label"], errors="coerce").values, "year": year.values})
    out = out[out["label"].isin([0, 1])]
    out = out[(out["subject"].str.strip() != "") | (out["body"].str.strip() != "")]
    out["label"] = out["label"].astype(int)
    return out.reset_index(drop=True)


def digest(subject, body):
    return hashlib.sha1(re.sub(r"\s+", " ", f"{subject} {body}".lower()).strip().encode("utf-8", "ignore")).hexdigest()


def load_all(src_dir):
    files = {os.path.splitext(f)[0].lower(): os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.lower().endswith(".csv")}
    names = [n for n in SOURCES if n in files]
    if len(names) < 2:
        raise SystemExit(f"Cần ít nhất hai nguồn trong {src_dir}; các file có: {sorted(files)}")
    parts, seen, rows = [], set(), []
    for n in names:                         # loại trùng nguyên văn trên toàn bộ, để thư giống hệt không nằm ở cả hai phía
        df = load_source(files[n], n)
        keep, n_raw = [], len(df)
        for s, b in zip(df["subject"], df["body"]):
            h = digest(s, b)
            keep.append(h not in seen)
            seen.add(h)
        df = df[keep].reset_index(drop=True)
        parts.append(df)
        rows.append((n, n_raw, len(df), int((df["label"] == 1).sum()), int((df["label"] == 0).sum())))
    print(f"{'Nguồn':<18}{'Sau làm sạch':>13}{'Sau loại trùng':>16}{'Nhãn 1':>9}{'Nhãn 0':>9}")
    for n, a, b, p, q in rows:
        print(f"{n:<18}{a:>13,}{b:>16,}{p:>9,}{q:>9,}")
    return pd.concat(parts, ignore_index=True)


# ---------- mô hình ----------
def make_texts(df):
    # đúng cách serve.py dựng chuỗi đầu vào: URL lấy từ nội dung, không có tệp đính kèm
    return [to_text({"subject": s, "body": b, "urls": URL_RE.findall(b), "has_html": False, "attachments": []})
            for s, b in zip(df["subject"], df["body"])]


def fit_svm(texts, y, seed):
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.9, sublinear_tf=True, max_features=200000,
                          lowercase=True, strip_accents="unicode", token_pattern=TOKEN)
    svm = CalibratedClassifierCV(LinearSVC(C=1.0, class_weight="balanced", random_state=seed), method="sigmoid", cv=5)
    return make_pipeline(vec, svm).fit(texts, y)


def top_terms(pipe, k=20):
    vec, cal = pipe.steps[0][1], pipe.steps[1][1]
    coef = np.mean([c.estimator.coef_[0] for c in cal.calibrated_classifiers_], axis=0)
    names = np.array(vec.get_feature_names_out())
    order = np.argsort(coef)
    return {"spam": [(str(names[i]), round(float(coef[i]), 3)) for i in order[::-1][:k]],
            "ham": [(str(names[i]), round(float(coef[i]), 3)) for i in order[:k]]}


# ---------- số đo ----------
def at(y, prob, t):
    pred = prob >= t
    tp, fp = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    return {"recall": round(tp / (tp + fn), 4) if tp + fn else None,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None, "fp": fp, "fn": fn}


def metrics(y, prob):
    spam, ham = y == 1, y == 0
    close = prob < THRESHOLDS["auto_close"]
    out = {"n": int(len(y)), "spam": int(spam.sum()), "ham": int(ham.sum()),
           "at_0.5": at(y, prob, THRESHOLDS["review"]), "at_0.8": at(y, prob, THRESHOLDS["alert"]),
           "spam_in_auto_close": int((spam & close).sum())}
    if spam.any() and ham.any():
        out["pr_auc"] = round(float(average_precision_score(y, prob)), 5)
        out["roc_auc"] = round(float(roc_auc_score(y, prob)), 5)
        out["pct_ham_auto_closed"] = round(100 * float((ham & close).sum() / ham.sum()), 2)
    return out


def fmt(v):
    return "  -  " if v is None else f"{v:.3f}"


def show(name, m):
    a, b = m["at_0.5"], m["at_0.8"]
    ham_part = f"PR-AUC {m['pr_auc']:.4f}" if "pr_auc" in m else "chỉ có spam"
    print(f"  {name:<24}n={m['n']:<6} spam={m['spam']:<6}| @0.5 recall {fmt(a['recall'])} prec {fmt(a['precision'])} FP {a['fp']:<5}"
          f"| @0.8 recall {fmt(b['recall'])} prec {fmt(b['precision'])} FP {b['fp']:<5}| {ham_part}")


def main():
    ap = argparse.ArgumentParser(description="Huấn luyện mô hình email; đánh giá bằng cách bỏ lần lượt từng nguồn ra")
    ap.add_argument("--src", default=SRC, help="thư mục chứa các CSV Kaggle đã giải nén")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-eval", action="store_true", help="bỏ bước đánh giá, chỉ huấn luyện và lưu mô hình (nhanh)")
    ap.add_argument("--no-save", action="store_true", help="không ghi email_svm.pkl")
    ap.add_argument("--out", default=os.path.join(RESULTS, "email_eval.json"))
    args = ap.parse_args()

    t_start = time.perf_counter()
    df = load_all(args.src)
    y, src = df["label"].to_numpy(), df["source"].to_numpy()
    texts = np.array(make_texts(df), dtype=object)
    print(f"\nTổng: {len(y):,} thư, spam {100 * y.mean():.1f}%")
    names = [n for n in SOURCES if n in set(src)]

    report = {"meta": {"sklearn": sklearn.__version__, "seed": args.seed, "n": int(len(y)), "thresholds": THRESHOLDS,
                       "sources": {n: int((src == n).sum()) for n in names},
                       "method": "bỏ lần lượt từng nguồn: huấn luyện trên các nguồn còn lại, đo trên nguồn bị bỏ",
                       "features": "TF-IDF 1-2 gram trên tiêu đề và nội dung (HTML đổi sang chữ) cộng token số URL và tệp đính kèm; Linear SVM hiệu chỉnh"}}

    if not args.skip_eval:
        print("\n== Đánh giá: mỗi lần bỏ một nguồn ra, huấn luyện trên các nguồn còn lại ==")
        print("   (@0.5 = ngưỡng phân loại; @0.8 = ngưỡng sinh cảnh báo của hệ thống)")
        oof = np.full(len(y), np.nan)
        report["per_source"] = {}
        for n in names:
            te = src == n
            t0 = time.perf_counter()
            pipe = fit_svm(list(texts[~te]), y[~te], args.seed)
            prob = pipe.predict_proba(list(texts[te]))[:, 1]
            oof[te] = prob
            m = metrics(y[te], prob)
            m["seconds"] = round(time.perf_counter() - t0, 1)
            report["per_source"][n] = m
            show(n, m)
            if n == "nazario":            # tách theo thời gian thư: có bắt được phishing mới hơn không
                yr = df.loc[te, "year"].to_numpy()
                period = np.where(np.isnan(yr), "không rõ ngày", np.where(yr < 2020, "trước 2020", "từ 2020"))
                report["nazario_by_period"] = {}
                for g in ("trước 2020", "từ 2020", "không rõ ngày"):
                    sel = period == g
                    if sel.any():
                        mg = metrics(y[te][sel], prob[sel])
                        report["nazario_by_period"][g] = mg
                        show(f"  nazario {g}", mg)
        ok = ~np.isnan(oof)
        pooled = metrics(y[ok], oof[ok])
        report["pooled_out_of_source"] = pooled
        print("\n  Gộp tất cả dự đoán ngoài nguồn (mỗi thư được dự đoán bởi mô hình chưa thấy nguồn của nó):")
        show("gộp", pooled)

    print("\nHuấn luyện mô hình phục vụ trên toàn bộ dữ liệu...")
    final = fit_svm(list(texts), y, args.seed)
    report["top_terms"] = top_terms(final)
    print("Từ nghiêng về spam:", ", ".join(t for t, _ in report["top_terms"]["spam"][:15]))
    print("Từ nghiêng về ham :", ", ".join(t for t, _ in report["top_terms"]["ham"][:15]))
    if not args.no_save:
        os.makedirs(MODELS, exist_ok=True)
        joblib.dump(final, os.path.join(MODELS, "email_svm.pkl"))
        print(f"Đã lưu {os.path.join(MODELS, 'email_svm.pkl')}")
    if not args.skip_eval:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"Đã ghi {args.out}")
    print(f"Tổng thời gian: {(time.perf_counter() - t_start) / 60:.1f} phút")
    print("\nLưu ý: dữ liệu là thư khoảng 2000 đến 2022, thư hợp lệ đều là thư cũ; kết quả cho biết khả năng phân biệt "
          "spam và phishing trên các nguồn cũ, không chứng minh bắt được phishing hay tránh báo nhầm thư hợp lệ ngày nay.")


if __name__ == "__main__":
    main()