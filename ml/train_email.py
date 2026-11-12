import argparse
import glob
import json
import os
import re
import time

import joblib
import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from email_features import TOKEN, parse_message, to_text

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "email")
MODELS = os.path.join(HERE, "models")
RESULTS = os.path.join(HERE, "results")
THRESHOLDS = {"auto_close": 0.15, "review": 0.50, "urgent": 0.80}
EARLY_GROUPS = {"easy_ham", "hard_ham", "spam"}          # bộ thu thập 10/2002
def load_dir(root):
    rows = []
    for gdir in sorted(d for d in glob.glob(os.path.join(root, "*")) if os.path.isdir(d)):
        group = re.sub(r"^\d{8}_", "", os.path.basename(gdir)).replace("-", "_")   # bỏ tiền tố ngày của tên tệp nén
        for f in sorted(glob.glob(os.path.join(gdir, "*"))):
            if os.path.isfile(f) and not os.path.basename(f).startswith("cmds"):
                with open(f, "rb") as fh:
                    rows.append((group, fh.read()))
    return rows


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            g = d["group"].replace("-", "_")
            g = {"easy_ham_1": "easy_ham", "hard_ham_1": "hard_ham", "spam_1": "spam"}.get(g, g)
            rows.append((g, d["text"]))
    return rows


def metrics(y, prob, groups):
    pred = (prob >= THRESHOLDS["review"]).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    ham, spam = y == 0, y == 1
    zone = np.where(prob < THRESHOLDS["auto_close"], 0, np.where(prob < THRESHOLDS["urgent"], 1, 2))
    urg = zone == 2
    hard = np.array([g == "hard_ham" for g in groups])
    return {"n": int(len(y)), "spam_ratio": round(float(y.mean()), 3),
            "pr_auc": round(float(average_precision_score(y, prob)), 5), "roc_auc": round(float(roc_auc_score(y, prob)), 5),
            "at_0.5": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(p, 4), "recall": round(r, 4),
                       "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0},
            "policy_zones": {"spam_in_auto_close": int((spam & (zone == 0)).sum()),
                             "pct_spam_in_auto_close": round(100 * float((spam & (zone == 0)).sum() / max(spam.sum(), 1)), 3),
                             "pct_ham_auto_closed": round(100 * float((ham & (zone == 0)).sum() / max(ham.sum(), 1)), 2),
                             "urgent_precision": round(float(y[urg].mean()), 4) if urg.any() else None},
            "hard_ham": {"n": int(hard.sum()), "false_positive_rate_at_0.5": round(float((prob[hard] >= 0.5).mean()), 4) if hard.any() else None}}


def fit_models(Xtr_text, ytr, seed):
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.9, sublinear_tf=True, max_features=200000,
                          lowercase=True, strip_accents="unicode", token_pattern=TOKEN)
    svm = CalibratedClassifierCV(LinearSVC(C=1.0, class_weight="balanced", random_state=seed), method="sigmoid", cv=5)
    t0 = time.perf_counter()
    pipe_svm = make_pipeline(vec, svm).fit(Xtr_text, ytr)
    t_svm = time.perf_counter() - t0
    vec_lr = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.9, sublinear_tf=True, max_features=200000,
                             lowercase=True, strip_accents="unicode", token_pattern=TOKEN)
    t0 = time.perf_counter()
    pipe_lr = make_pipeline(vec_lr, LogisticRegression(C=10, class_weight="balanced", max_iter=2000, random_state=seed)).fit(Xtr_text, ytr)
    return {"Linear SVM (hiệu chỉnh)": (pipe_svm, round(t_svm, 1)), "Logistic Regression": (pipe_lr, round(time.perf_counter() - t0, 1))}


def top_terms(pipe, k=15):
    vec, cal = pipe.steps[0][1], pipe.steps[1][1]
    coef = np.mean([c.estimator.coef_[0] for c in cal.calibrated_classifiers_], axis=0)
    names = np.array(vec.get_feature_names_out())
    order = np.argsort(coef)
    return {"spam": [(str(names[i]), round(float(coef[i]), 3)) for i in order[::-1][:k]],
            "ham": [(str(names[i]), round(float(coef[i]), 3)) for i in order[:k]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA, help="thư mục chứa các thư mục con easy_ham, easy_ham_2, hard_ham, spam, spam_2")
    ap.add_argument("--jsonl", default=None, help="đọc từ file JSON Lines (id, group, text) thay cho thư mục")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bootstrap", type=int, default=100)
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESULTS, "email_eval.json"))
    args = ap.parse_args()
    if args.jsonl is None:
        auto = os.path.join(DATA, "spamassassin.jsonl")
        if os.path.isfile(auto):
            args.jsonl = auto

    rows = load_jsonl(args.jsonl) if args.jsonl else load_dir(args.data)
    if not rows:
        raise SystemExit(f"Không đọc được thư nào từ {args.jsonl or args.data}")
    texts, y, groups = [], [], []
    for g, raw in rows:
        texts.append(to_text(parse_message(raw)))
        y.append(1 if g.startswith("spam") else 0)
        groups.append(g)
    y, groups = np.array(y), np.array(groups)
    print(f"Đọc {len(y)} thư: spam {int(y.sum())} ({100 * y.mean():.1f}%), nhóm {dict(zip(*np.unique(groups, return_counts=True)))}")

    report = {"meta": {"sklearn": sklearn.__version__, "n": int(len(y)), "seed": args.seed, "thresholds": THRESHOLDS,
                       "groups": {k: int(v) for k, v in zip(*np.unique(groups, return_counts=True))},
                       "features": "tiêu đề và nội dung (HTML đổi sang chữ), thêm 3 token cấu trúc; không dùng các tiêu đề kỹ thuật như Received"},
              "evaluations": {}}
    tr_idx_all = np.arange(len(y))
    early = np.array([g in EARLY_GROUPS for g in groups])
    splits = {}
    a, b = train_test_split(tr_idx_all, test_size=0.2, stratify=y, random_state=args.seed)
    splits["Chia ngẫu nhiên 80/20"] = (a, b)
    if early.any() and (~early).any():
        splits["Huấn luyện bộ 10/2002, thử bộ thu thập sau đó"] = (tr_idx_all[early], tr_idx_all[~early])

    trained = {}
    for sname, (tr, te) in splits.items():
        print(f"\n== {sname}: huấn luyện {len(tr)} thư, thử {len(te)} thư ==")
        models = fit_models([texts[i] for i in tr], y[tr], args.seed)
        entry = {"n_train": int(len(tr)), "n_test": int(len(te)), "models": {}}
        probs = {}
        for mname, (pipe, secs) in models.items():
            prob = pipe.predict_proba([texts[i] for i in te])[:, 1]
            probs[mname] = prob
            m = metrics(y[te], prob, groups[te]); m["train_seconds"] = secs
            entry["models"][mname] = m
        if args.bootstrap:
            rng = np.random.default_rng(args.seed); samples = {n: [] for n in probs}
            for _ in range(args.bootstrap):
                idx = rng.integers(0, len(te), len(te))
                for n, p in probs.items():
                    if y[te][idx].min() != y[te][idx].max():
                        samples[n].append(average_precision_score(y[te][idx], p[idx]))
            for n in probs:
                lo, hi = np.percentile(samples[n], [2.5, 97.5]); entry["models"][n]["pr_auc_ci95"] = [round(float(lo), 5), round(float(hi), 5)]
        report["evaluations"][sname] = entry
        for n, m in entry["models"].items():
            c, z = m["at_0.5"], m["policy_zones"]
            print(f"  {n:<26} PR-AUC {m['pr_auc']} {m.get('pr_auc_ci95','')} | P {c['precision']} R {c['recall']} FP {c['fp']} FN {c['fn']} | "
                  f"spam lọt vào tự đóng {z['spam_in_auto_close']} ({z['pct_spam_in_auto_close']}%) | ham tự đóng {z['pct_ham_auto_closed']}% | "
                  f"hard_ham FP {m['hard_ham']['false_positive_rate_at_0.5']}")
        trained[sname] = models

    # mô hình phục vụ: huấn luyện trên toàn bộ dữ liệu
    print("\nHuấn luyện mô hình phục vụ trên toàn bộ dữ liệu...")
    final = fit_models(texts, y, args.seed)["Linear SVM (hiệu chỉnh)"][0]
    report["top_terms"] = top_terms(final)
    print("Từ nghiêng về spam:", ", ".join(t for t, _ in report["top_terms"]["spam"][:12]))
    print("Từ nghiêng về ham :", ", ".join(t for t, _ in report["top_terms"]["ham"][:12]))
    if not args.no_save:
        os.makedirs(MODELS, exist_ok=True)
        joblib.dump(final, os.path.join(MODELS, "email_svm.pkl"))
        print(f"Đã lưu {os.path.join(MODELS, 'email_svm.pkl')}")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"Đã ghi {args.out}")
    print("\nLưu ý: bộ SpamAssassin là thư spam và thư thường thu thập năm 2002 đến 2005, không phải thư phishing hiện đại; "
          "kết quả cho biết khả năng phân biệt spam theo nội dung, không chứng minh phát hiện được phishing ngày nay.")


if __name__ == "__main__":
    main()
