import os
import json
import numpy as np
import joblib
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
ML = HERE if os.path.isdir(os.path.join(HERE, "models")) else os.path.abspath(os.path.join(HERE, "..", "ml"))
if not os.path.isdir(os.path.join(ML, "models")):
    ML = os.path.abspath(os.path.join(HERE, "..", "..", "ml"))
DATA = os.path.join(ML, "data", "processed")
MODELS = os.path.join(ML, "models")
RESULTS = os.path.join(ML, "results")

THRESHOLDS = {"auto_close": 0.15, "review": 0.50, "urgent": 0.80}
HIGH_KEYWORDS = ["ddos", "dos", "bot", "infiltration", "heartbleed", "sql"]

rf = joblib.load(os.path.join(MODELS, "rf_binary.pkl"))
le = joblib.load(os.path.join(DATA, "label_encoder.pkl"))
X = np.load(os.path.join(DATA, "X_test.npy"))
y = np.load(os.path.join(DATA, "y_test_binary.npy"))
ym = np.load(os.path.join(DATA, "y_test_multi.npy"))
classes = [str(c) for c in le.classes_]

print(f"Test set: {len(y):,} luồng, {int(y.sum()):,} tấn công ({100*y.mean():.1f}%)")
print("Đang dự đoán xác suất...")
prob = rf.predict_proba(X)[:, 1]

out = {"n_test": int(len(y)), "n_attack": int(y.sum()),
       "pr_auc": round(float(average_precision_score(y, prob)), 4),
       "roc_auc": round(float(roc_auc_score(y, prob)), 4), "thresholds": {}, "zones": {}, "per_class": {}}
print(f"PR-AUC = {out['pr_auc']}   ROC-AUC = {out['roc_auc']}\n")


def conf(pred):
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0, "fpr": round(fp / (fp + tn), 5) if fp + tn else 0.0}


print(f"{'Ngưỡng':>8} {'Precision':>10} {'Recall':>8} {'F1':>8} {'FP':>8} {'FN':>8} {'FPR':>9}")
for name, t in THRESHOLDS.items():
    c = conf((prob >= t).astype(int))
    out["thresholds"][f"{t}"] = c
    print(f"{t:>8} {c['precision']:>10} {c['recall']:>8} {c['f1']:>8} {c['fp']:>8} {c['fn']:>8} {c['fpr']:>9}")

zone = np.where(prob < THRESHOLDS["auto_close"], "auto_close", np.where(prob < THRESHOLDS["urgent"], "review", "urgent"))
print("\nPhân vùng ba mức:")
print(f"{'Vùng':>11} {'Luồng':>9} {'% tổng':>8} {'Tấn công':>9} {'% tấn công trong vùng':>22}")
for z in ("auto_close", "review", "urgent"):
    m = zone == z
    n, a = int(m.sum()), int(y[m].sum())
    out["zones"][z] = {"flows": n, "pct_of_all": round(100 * n / len(y), 2), "attacks": a,
                       "attack_rate_in_zone_pct": round(100 * a / n, 2) if n else 0.0}
    print(f"{z:>11} {n:>9,} {100*n/len(y):>7.2f}% {a:>9,} {100*a/n if n else 0:>21.2f}%")
missed = int(y[zone == "auto_close"].sum())
benign_auto = int(((zone == "auto_close") & (y == 0)).sum())
out["safety"] = {"attacks_in_auto_close": missed, "pct_of_attacks_missed_by_auto_close": round(100 * missed / y.sum(), 3),
                 "benign_removed_from_analyst_queue_pct": round(100 * benign_auto / (y == 0).sum(), 2),
                 "analyst_workload_pct_of_all_flows": round(100 * (zone != "auto_close").mean(), 2)}
print(f"\nAn toàn: {missed} cuộc tấn công rơi vào vùng tự đóng ({out['safety']['pct_of_attacks_missed_by_auto_close']}% tổng số tấn công)")
print(f"Giảm tải: tự đóng {out['safety']['benign_removed_from_analyst_queue_pct']}% luồng lành tính; "
      f"analyst phải xem {out['safety']['analyst_workload_pct_of_all_flows']}% tổng luồng")

review_t = THRESHOLDS["review"]
print(f"\nRecall theo loại tấn công (ngưỡng {review_t}); * = nhóm mức độ cao theo từ khóa {HIGH_KEYWORDS}:")
print(f"{'Loại':36} {'n':>8} {'Recall':>8} {'Tự đóng nhầm':>13}")
high_mask = np.zeros(len(y), dtype=bool)
for idx, cname in enumerate(classes):
    if cname.upper() == "BENIGN":
        continue
    m = ym == idx
    n = int(m.sum())
    if n == 0:
        continue
    is_high = any(k in cname.lower() for k in HIGH_KEYWORDS)
    if is_high:
        high_mask |= m
    rec = float((prob[m] >= review_t).mean())
    miss = float((prob[m] < THRESHOLDS["auto_close"]).mean())
    out["per_class"][cname] = {"n": n, "recall": round(rec, 4), "auto_closed_pct": round(100 * miss, 2), "high_severity": is_high}
    print(f"{('* ' if is_high else '  ') + cname[:34]:36} {n:>8,} {rec:>8.4f} {100*miss:>12.2f}%")
if high_mask.any():
    out["high_severity_recall"] = round(float((prob[high_mask] >= review_t).mean()), 4)
    print(f"\nRecall nhóm mức độ cao (gộp): {out['high_severity_recall']}")

os.makedirs(RESULTS, exist_ok=True)
json.dump(out, open(os.path.join(RESULTS, "threshold_eval.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nĐã ghi {os.path.join(RESULTS, 'threshold_eval.json')}")
print("Lưu ý: tập test lấy từ chia ngẫu nhiên 80/20 trên CIC-IDS2017 (các luồng gần giống nhau có thể nằm ở cả hai tập), "
      "nên số liệu có thể cao hơn khi gặp lưu lượng của môi trường khác.")