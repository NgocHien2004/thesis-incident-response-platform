import argparse
import json
import os
import time
import warnings

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "processed")
MODELS = os.path.join(HERE, "models")
RESULTS = os.path.join(HERE, "results")

THRESHOLDS = {"auto_close": 0.15, "review": 0.50, "urgent": 0.80}
HIGH_KEYWORDS = ["ddos", "dos", "bot", "infiltration", "heartbleed", "sql"]
MISS_BUDGETS = [0.0002, 0.001, 0.005]


def fit_logistic(X, y, seed):
    model = LogisticRegression(class_weight="balanced", max_iter=500, random_state=seed)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        t0 = time.perf_counter()
        model.fit(X, y)
        seconds = time.perf_counter() - t0
    converged = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
    return model, seconds, {"iterations": int(np.max(model.n_iter_)), "converged": converged}


def fit_gradient_boosting(X, y, seed):
    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.1, max_leaf_nodes=63, class_weight="balanced",
        early_stopping=True, validation_fraction=0.1, n_iter_no_change=15, random_state=seed)
    t0 = time.perf_counter()
    model.fit(X, y)
    seconds = time.perf_counter() - t0
    return model, seconds, {"iterations": int(model.n_iter_), "early_stopped": bool(model.n_iter_ < 300)}


def confusion(y, pred):
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}


def evaluate(prob, y, ym, classes):
    out = {"pr_auc": round(float(average_precision_score(y, prob)), 5),
           "roc_auc": round(float(roc_auc_score(y, prob)), 5),
           "at_0.5": confusion(y, (prob >= THRESHOLDS["review"]).astype(int))}

    zone = np.where(prob < THRESHOLDS["auto_close"], "auto_close", np.where(prob < THRESHOLDS["urgent"], "review", "urgent"))
    benign, attack = (y == 0), (y == 1)
    urgent = zone == "urgent"
    out["policy_zones"] = {
        "attacks_in_auto_close": int((attack & (zone == "auto_close")).sum()),
        "pct_attacks_in_auto_close": round(100 * float((attack & (zone == "auto_close")).sum() / attack.sum()), 4),
        "pct_benign_auto_closed": round(100 * float((benign & (zone == "auto_close")).sum() / benign.sum()), 2),
        "pct_flows_for_analyst": round(100 * float((zone != "auto_close").mean()), 2),
        "urgent_flows": int(urgent.sum()),
        "urgent_precision": round(float(y[urgent].mean()), 4) if urgent.any() else None,
    }

    # ngưỡng chọn ngay trên tập kiểm thử (oracle): chỉ để so sánh giữa các mô hình, không dùng làm ngưỡng vận hành
    att_sorted = np.sort(prob[attack])
    oracle = {}
    for budget in MISS_BUDGETS:
        k = int(np.floor(budget * len(att_sorted)))
        t = float(att_sorted[k])
        oracle[f"{budget}"] = {"threshold": round(t, 5),
                               "attacks_missed": int((prob[attack] < t).sum()),
                               "pct_attacks_missed": round(100 * float((prob[attack] < t).mean()), 4),
                               "pct_benign_auto_closed": round(100 * float((prob[benign] < t).mean()), 2)}
    out["oracle_auto_close"] = oracle

    per_class, high = {}, np.zeros(len(y), dtype=bool)
    for idx, name in enumerate(classes):
        if name.upper() == "BENIGN":
            continue
        m = ym == idx
        if not m.any():
            continue
        is_high = any(k in name.lower() for k in HIGH_KEYWORDS)
        high |= m & is_high
        per_class[name] = {"n": int(m.sum()), "recall_0.5": round(float((prob[m] >= THRESHOLDS["review"]).mean()), 4),
                           "auto_closed_pct": round(100 * float((prob[m] < THRESHOLDS["auto_close"]).mean()), 2),
                           "high_severity": is_high}
    out["per_class"] = per_class
    if high.any():
        out["high_severity_recall_0.5"] = round(float((prob[high] >= THRESHOLDS["review"]).mean()), 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-train", type=int, default=0, help="chỉ dùng ngần này dòng huấn luyện (0 = toàn bộ); để chạy thử nhanh")
    ap.add_argument("--bootstrap", type=int, default=100, help="số lần lấy mẫu lại để tính khoảng tin cậy PR-AUC (0 = bỏ qua)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-save", action="store_true", help="không lưu mô hình đã huấn luyện")
    ap.add_argument("--out", default=os.path.join(RESULTS, "baseline_comparison.json"))
    args = ap.parse_args()

    X_train = np.load(os.path.join(DATA, "X_train.npy"))
    y_train = np.load(os.path.join(DATA, "y_train_binary.npy"))
    X_test = np.load(os.path.join(DATA, "X_test.npy"))
    y_test = np.load(os.path.join(DATA, "y_test_binary.npy"))
    ym_test = np.load(os.path.join(DATA, "y_test_multi.npy"))
    classes = [str(c).replace("\ufffd", "-") for c in joblib.load(os.path.join(DATA, "label_encoder.pkl")).classes_]

    if args.max_train and args.max_train < len(y_train):
        keep = np.random.default_rng(args.seed).choice(len(y_train), size=args.max_train, replace=False)
        X_train, y_train = X_train[keep], y_train[keep]
        print(f"Huấn luyện thử trên {args.max_train:,} dòng (không phải toàn bộ tập huấn luyện)")
    print(f"Huấn luyện: {len(y_train):,} luồng, {100 * y_train.mean():.1f}% tấn công | "
          f"Kiểm thử: {len(y_test):,} luồng, {100 * y_test.mean():.1f}% tấn công | {X_train.shape[1]} đặc trưng")

    models = {}
    rf_path = os.path.join(MODELS, "rf_binary.pkl")
    if os.path.isfile(rf_path):
        models["Random Forest"] = {"model": joblib.load(rf_path), "train_seconds": None, "fit": {"note": "mô hình đã huấn luyện sẵn (train.py)"}, "path": rf_path}
    else:
        print("Không thấy models/rf_binary.pkl: chỉ so sánh hai mô hình mới")

    print("\nHuấn luyện Logistic Regression...")
    lr, sec, info = fit_logistic(X_train, y_train, args.seed)
    print(f"  xong sau {sec:.1f}s, {info['iterations']} vòng lặp" + ("" if info["converged"] else " (CHƯA hội tụ)"))
    models["Logistic Regression"] = {"model": lr, "train_seconds": round(sec, 1), "fit": info, "path": os.path.join(MODELS, "lr_binary.pkl")}

    print("Huấn luyện Gradient Boosting (HistGradientBoosting)...")
    gb, sec, info = fit_gradient_boosting(X_train, y_train, args.seed)
    print(f"  xong sau {sec:.1f}s, {info['iterations']} cây")
    models["Gradient Boosting"] = {"model": gb, "train_seconds": round(sec, 1), "fit": info, "path": os.path.join(MODELS, "hgb_binary.pkl")}

    if not args.no_save:
        for key in ("Logistic Regression", "Gradient Boosting"):
            joblib.dump(models[key]["model"], models[key]["path"])

    probs, report = {}, {}
    for name, m in models.items():
        print(f"Dự đoán trên tập kiểm thử: {name}...")
        t0 = time.perf_counter()
        probs[name] = m["model"].predict_proba(X_test)[:, 1]
        predict_seconds = time.perf_counter() - t0
        res = evaluate(probs[name], y_test, ym_test, classes)
        res["train_seconds"] = m["train_seconds"]
        res["fit"] = m["fit"]
        res["predict_us_per_flow"] = round(1e6 * predict_seconds / len(y_test), 2)
        res["model_size_mb"] = round(os.path.getsize(m["path"]) / 1048576, 2) if os.path.isfile(m["path"]) else None
        report[name] = res

    if args.bootstrap:
        print(f"Lấy mẫu lại {args.bootstrap} lần để tính khoảng tin cậy PR-AUC...")
        rng = np.random.default_rng(args.seed)
        ap_samples = {n: [] for n in probs}
        for _ in range(args.bootstrap):
            idx = rng.integers(0, len(y_test), len(y_test))
            for n, p in probs.items():
                ap_samples[n].append(average_precision_score(y_test[idx], p[idx]))
        base = "Random Forest" if "Random Forest" in probs else None
        for n in probs:
            lo, hi = np.percentile(ap_samples[n], [2.5, 97.5])
            report[n]["pr_auc_ci95"] = [round(float(lo), 5), round(float(hi), 5)]
            if base and n != base:
                diff = np.array(ap_samples[n]) - np.array(ap_samples[base])
                dlo, dhi = np.percentile(diff, [2.5, 97.5])
                report[n]["pr_auc_diff_vs_rf_ci95"] = [round(float(dlo), 5), round(float(dhi), 5)]
                report[n]["pr_auc_diff_vs_rf_significant"] = bool(dlo > 0 or dhi < 0)

    names = list(report)
    print("\n" + "=" * 100)
    print(f"{'Mô hình':<22}{'PR-AUC':>9}{'ROC-AUC':>9}{'Prec@0.5':>10}{'Rec@0.5':>9}{'FP':>8}{'FN':>8}{'Huấn luyện':>12}{'µs/luồng':>10}{'MB':>9}")
    for n in names:
        r = report[n]
        c = r["at_0.5"]
        tr = f"{r['train_seconds']}s" if r["train_seconds"] is not None else "-"
        print(f"{n:<22}{r['pr_auc']:>9}{r['roc_auc']:>9}{c['precision']:>10}{c['recall']:>9}{c['fp']:>8,}{c['fn']:>8,}{tr:>12}{r['predict_us_per_flow']:>10}{str(r['model_size_mb']):>9}")
    if args.bootstrap:
        print("\nKhoảng tin cậy 95% của PR-AUC (lấy mẫu lại tập kiểm thử) và chênh lệch ghép cặp so với Random Forest:")
        for n in names:
            r = report[n]
            line = f"  {n:<22} PR-AUC {r['pr_auc_ci95']}"
            if "pr_auc_diff_vs_rf_ci95" in r:
                line += f" | chênh lệch so với RF {r['pr_auc_diff_vs_rf_ci95']} -> " + ("KHÁC biệt có ý nghĩa" if r["pr_auc_diff_vs_rf_significant"] else "không khác biệt rõ")
            print(line)

    print(f"\nChính sách ba vùng của hệ thống (tự đóng < {THRESHOLDS['auto_close']}, khẩn >= {THRESHOLDS['urgent']}); "
          "các ngưỡng này được chọn cho xác suất của Random Forest nên chưa chắc công bằng với mô hình khác:")
    print(f"{'Mô hình':<22}{'Tấn công lọt vào tự đóng':>26}{'% lành tính tự đóng':>21}{'% luồng analyst xem':>21}{'Precision vùng khẩn':>21}")
    for n in names:
        z = report[n]["policy_zones"]
        print(f"{n:<22}{z['attacks_in_auto_close']:>14,} ({z['pct_attacks_in_auto_close']}%){z['pct_benign_auto_closed']:>14}{z['pct_flows_for_analyst']:>21}{str(z['urgent_precision']):>21}")

    print("\nSo sánh ở cùng mức rủi ro (ngưỡng chọn ngay trên tập kiểm thử nên chỉ dùng để so giữa các mô hình, không phải ngưỡng vận hành):")
    print("Cho phép bỏ sót tối đa X% tấn công, % lành tính có thể tự đóng được:")
    print(f"{'Mô hình':<22}" + "".join(f"{f'<= {100 * b:g}%':>14}" for b in MISS_BUDGETS))
    for n in names:
        print(f"{n:<22}" + "".join(f"{report[n]['oracle_auto_close'][str(b)]['pct_benign_auto_closed']:>13}%" for b in MISS_BUDGETS))

    print(f"\nRecall theo lớp tấn công ở ngưỡng {THRESHOLDS['review']} (* = nhóm mức độ cao):")
    print(f"{'Lớp':<36}{'n':>8}" + "".join(f"{n:>22}" for n in names))
    first = report[names[0]]["per_class"]
    for cname, info in sorted(first.items(), key=lambda kv: kv[1]["recall_0.5"]):
        mark = "* " if info["high_severity"] else "  "
        print(f"{mark + cname[:33]:<36}{info['n']:>8,}" + "".join(f"{report[n]['per_class'][cname]['recall_0.5']:>22}" for n in names))
    if "high_severity_recall_0.5" in report[names[0]]:
        print(f"{'Nhóm mức độ cao (gộp)':<44}" + "".join(f"{report[n]['high_severity_recall_0.5']:>22}" for n in names))

    print("\nLưu ý: tập kiểm thử là chia ngẫu nhiên 80/20 trên CIC-IDS2017, các luồng gần giống nhau nằm ở cả hai tập nên mọi số liệu "
          "đều có thể cao hơn khi gặp lưu lượng môi trường khác; một lần huấn luyện với một hạt giống, chưa lặp lại; "
          "PR-AUC ở đây tính bằng average_precision_score (khác cách tính hình thang trong train.py).")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    meta = {"sklearn": sklearn.__version__, "numpy": np.__version__, "seed": args.seed, "n_train": int(len(y_train)),
            "n_test": int(len(y_test)), "attack_ratio_train": round(float(y_train.mean()), 4), "attack_ratio_test": round(float(y_test.mean()), 4),
            "max_train_limit": args.max_train or None, "bootstrap": args.bootstrap, "thresholds": THRESHOLDS,
            "pr_auc_method": "average_precision_score"}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "models": report}, f, ensure_ascii=False, indent=1)
    print(f"\nĐã ghi {args.out}")


if __name__ == "__main__":
    main()