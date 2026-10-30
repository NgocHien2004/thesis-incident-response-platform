import argparse
import json
import os
import sys
from collections import Counter, defaultdict

import joblib
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.scenarios.base import login_all

DEFAULT_DATA = os.path.join(ROOT, "ml", "data", "processed")
OUT_FILE = os.path.join(ROOT, "tests", "flow_scoring_results.json")
ZONES = ["urgent", "review", "auto_close"]


def main(args):
    X = np.load(os.path.join(args.data, "X_test.npy"))
    y = np.load(os.path.join(args.data, "y_test_binary.npy"))
    ym = np.load(os.path.join(args.data, "y_test_multi.npy"))
    scaler = joblib.load(os.path.join(args.data, "scaler.pkl"))
    cols = joblib.load(os.path.join(args.data, "feature_cols.pkl"))
    try:
        names = list(joblib.load(os.path.join(args.data, "label_encoder.pkl")).classes_)
    except Exception:  # noqa: BLE001
        names = None

    rng = np.random.default_rng(args.seed)
    att = rng.choice(np.where(y == 1)[0], size=min(args.attacks, int((y == 1).sum())), replace=False)
    ben = rng.choice(np.where(y == 0)[0], size=min(args.benign, int((y == 0).sum())), replace=False)
    idx = rng.permutation(np.concatenate([att, ben]))
    raw = scaler.inverse_transform(X[idx])

    u = login_all()
    it, analyst = u["it"], u["analyst"]
    assets = [a for a in analyst.raw("GET", "/assets/").json()]
    if not assets:
        print("Chưa có tài sản nào để gắn cảnh báo. Hãy nạp dữ liệu demo trước.")
        sys.exit(1)

    rows = []
    for k, (i, vec) in enumerate(zip(idx, raw)):
        asset = assets[k % len(assets)]
        label = int(y[i])
        kind = (names[int(ym[i])] if names is not None else str(int(ym[i])))
        payload = {
            "title": f"Luồng mạng nghi ngờ #{k + 1} (mẫu kiểm thử)",
            "description": "Luồng lấy từ tập kiểm thử CIC-IDS2017 để đánh giá chấm điểm",
            "source": "ids_ips", "severity": "medium",
            "ioc": f"198.18.{(k // 250) % 250}.{k % 250 + 1}",
            "affected_asset": asset["id"],
            "label": "attack" if label else "benign", "attack_type": kind,
            "flow_features": {str(c): float(v) for c, v in zip(cols, vec)},
        }
        r = it.raw("POST", "/alerts/webhook", payload)
        if r.status_code != 200:
            print(f"Lỗi nhập cảnh báo {k + 1}: {r.status_code} {r.text[:120]}")
            continue
        a = r.json()
        m = a.get("ml_result") or {}
        rows.append({"id": a["id"], "label": label, "attack_type": kind, "zone": a.get("ml_zone"),
                     "priority": a.get("ml_priority"), "probability": m.get("probability"),
                     "p_source": m.get("probability_source"), "asset_criticality": asset["criticality"]})

    n = len(rows)
    n_att = sum(r["label"] for r in rows)
    n_ben = n - n_att
    table = {z: {"attack": 0, "benign": 0} for z in ZONES}
    for r in rows:
        if r["zone"] in table:
            table[r["zone"]]["attack" if r["label"] else "benign"] += 1
    by_crit = defaultdict(Counter)
    for r in rows:
        by_crit[r["asset_criticality"]][r["zone"]] += 1

    attack_missed = table["auto_close"]["attack"]
    summary = {
        "n_alerts": n, "n_attack": n_att, "n_benign": n_ben,
        "from_rf": sum(1 for r in rows if r["p_source"] == "rf"),
        "zone_by_label": table,
        "zone_by_asset_criticality": {k: dict(v) for k, v in by_crit.items()},
        "attack_in_auto_close": attack_missed,
        "attack_recall_urgent_or_review": round(1 - attack_missed / n_att, 4) if n_att else None,
        "benign_auto_close_rate": round(table["auto_close"]["benign"] / n_ben, 4) if n_ben else None,
        "benign_urgent_rate": round(table["urgent"]["benign"] / n_ben, 4) if n_ben else None,
        "analyst_workload_share": round((table["urgent"]["attack"] + table["urgent"]["benign"]
                                         + table["review"]["attack"] + table["review"]["benign"]) / n, 4) if n else None,
        "seed": args.seed,
        "note": "Cảnh báo mẫu được gắn lần lượt vào các tài sản hiện có nên vùng phụ thuộc cả mức quan trọng của tài sản.",
    }

    print("\n" + "=" * 64)
    print(f"Đã chấm điểm {n} luồng ({n_att} tấn công, {n_ben} lành tính), {summary['from_rf']} luồng dùng mô hình RF")
    print(f"{'Vùng':<14}{'Tấn công':>10}{'Lành tính':>12}")
    for z in ZONES:
        print(f"{z:<14}{table[z]['attack']:>10}{table[z]['benign']:>12}")
    print(f"Tấn công bị đề xuất tự đóng: {attack_missed}  |  recall (khẩn hoặc cần xem): {summary['attack_recall_urgent_or_review']}")
    print(f"Lành tính được đề xuất tự đóng: {summary['benign_auto_close_rate']}  |  lành tính ở vùng khẩn: {summary['benign_urgent_rate']}")
    print(f"Tỷ lệ cảnh báo analyst phải xem: {summary['analyst_workload_share']}")
    print("=" * 64)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"Kết quả lưu tại {os.path.relpath(args.out, ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Đánh giá chấm điểm và chia vùng trên luồng mạng của tập kiểm thử")
    ap.add_argument("--attacks", type=int, default=100, help="số luồng tấn công")
    ap.add_argument("--benign", type=int, default=200, help="số luồng lành tính")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--data", default=DEFAULT_DATA, help="thư mục data/processed của mô hình")
    ap.add_argument("--out", default=OUT_FILE)
    main(ap.parse_args())
