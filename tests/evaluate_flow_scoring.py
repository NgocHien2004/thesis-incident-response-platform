import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

import joblib
import numpy as np
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.scenarios.base import login_all

DEFAULT_DATA = os.path.join(ROOT, "ml", "data", "processed")
OUT_FILE = os.path.join(ROOT, "tests", "results", "flow_scoring_results.json")
ZONES = ["urgent", "review", "auto_close"]


RELOGINS = 0


def post_alert(runner, payload):
    """Gửi cảnh báo; token hết hạn khi chạy lâu thì đăng nhập lại rồi gửi lại một lần."""
    global RELOGINS
    r = runner.raw("POST", "/alerts/webhook", payload)
    if r.status_code == 401:
        RELOGINS += 1
        runner.login()
        r = runner.raw("POST", "/alerts/webhook", payload)
    return r


def main(args):
    X = np.load(os.path.join(args.data, "X_test.npy"))
    y = np.load(os.path.join(args.data, "y_test_binary.npy"))
    ym = np.load(os.path.join(args.data, "y_test_multi.npy"))
    scaler = joblib.load(os.path.join(args.data, "scaler.pkl"))
    cols = joblib.load(os.path.join(args.data, "feature_cols.pkl"))
    try:
        # CSV gốc của CIC-IDS2017 không phải UTF-8 nên dấu gạch ở "Web Attack – XSS" thành \ufffd
        names = [str(n).replace("\ufffd", "-") for n in joblib.load(os.path.join(args.data, "label_encoder.pkl")).classes_]
    except Exception:  # noqa: BLE001
        names = None

    rng = np.random.default_rng(args.seed)
    if args.per_class:
        att_pool = np.where(y == 1)[0]
        parts = []
        for c in np.unique(ym[att_pool]):
            pool = att_pool[ym[att_pool] == c]
            parts.append(rng.choice(pool, size=min(args.per_class, len(pool)), replace=False))
        att = np.concatenate(parts)
    else:
        att = rng.choice(np.where(y == 1)[0], size=min(args.attacks, int((y == 1).sum())), replace=False)
    ben = rng.choice(np.where(y == 0)[0], size=min(args.benign, int((y == 0).sum())), replace=False)
    idx = rng.permutation(np.concatenate([att, ben]))
    raw = scaler.inverse_transform(X[idx])
    kind_of = lambda i: (names[int(ym[i])] if names is not None else str(int(ym[i])))
    print(f"Mẫu: {len(att)} luồng tấn công + {len(ben)} lành tính" + (f" (tối thiểu mỗi lớp {args.per_class}, lớp ít hơn lấy hết)" if args.per_class else ""))
    for k_, v_ in sorted(Counter(kind_of(i) for i in att).items()):
        print(f"  {k_:<34}{v_:>5}")

    try:
        u = login_all()
    except requests.exceptions.ConnectionError:
        print("Không kết nối được backend ở cổng 8000.")
        print("Cần đang chạy: backend (cổng 8000) và AI service (cổng 8001), rồi chạy lại lệnh này.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"Đăng nhập thất bại (HTTP {e.response.status_code}).")
        print("Cần nạp dữ liệu demo trước để có các tài khoản analyst01, analyst02, it01, stakeholder01.")
        sys.exit(1)
    it, analyst = u["it"], u["analyst"]
    assets = [a for a in analyst.raw("GET", "/assets/").json()]
    if not assets:
        print("Chưa có tài sản nào để gắn cảnh báo. Hãy nạp dữ liệu demo trước.")
        sys.exit(1)

    rows = []
    total = len(idx)
    started = time.perf_counter()
    for k, (i, vec) in enumerate(zip(idx, raw)):
        if k and k % 25 == 0:
            elapsed = time.perf_counter() - started
            print(f"  đã gửi {k}/{total} | {elapsed:.0f}s | còn khoảng {elapsed / k * (total - k):.0f}s")
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
        r = post_alert(it, payload)
        if r.status_code != 200:
            print(f"Lỗi nhập cảnh báo {k + 1}: {r.status_code} {r.text[:120]}")
            continue
        a = r.json()
        m = a.get("ml_result") or {}
        rows.append({"id": a["id"], "label": label, "attack_type": kind, "zone": a.get("ml_zone"),
                     "priority": a.get("ml_priority"), "probability": m.get("probability"),
                     "p_source": m.get("probability_source"), "asset_criticality": asset["criticality"],
                     "alert_source": a.get("source")})

    per_alert = (time.perf_counter() - started) / max(len(idx), 1)
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

    by_class = {}
    for r in rows:
        c = by_class.setdefault(r["attack_type"], {"label": "attack" if r["label"] else "benign", "n": 0, **{z: 0 for z in ZONES}})
        c["n"] += 1
        if r["zone"] in ZONES:
            c[r["zone"]] += 1
    for c in by_class.values():
        if c["label"] == "attack":
            c["bi_de_xuat_dong"] = round(c["auto_close"] / c["n"], 4)
            # quy tắc 3/n: nếu 0 bỏ sót trong n mẫu thì tỷ lệ bỏ sót thật có thể tới khoảng 3/n (tin cậy 95%)
            c["can_tren_95_neu_0_bo_sot"] = round(min(1.0, 3 / c["n"]), 4) if c["auto_close"] == 0 else None

    attack_missed = table["auto_close"]["attack"]
    summary = {
        "n_alerts": n, "n_attack": n_att, "n_benign": n_ben,
        "from_rf": sum(1 for r in rows if r["p_source"] == "rf"),
        "zone_by_label": table,
        "zone_by_asset_criticality": {k: dict(v) for k, v in by_crit.items()},
        "zone_by_class": dict(sorted(by_class.items(), key=lambda kv: (kv[1]["label"] == "benign", kv[0]))),
        "alert_source": dict(Counter(r["alert_source"] for r in rows)),
        "sampling": {"mode": "per_class" if args.per_class else "random", "per_class": args.per_class or None},
        "attack_in_auto_close": attack_missed,
        "attack_recall_urgent_or_review": round(1 - attack_missed / n_att, 4) if n_att else None,
        "benign_auto_close_rate": round(table["auto_close"]["benign"] / n_ben, 4) if n_ben else None,
        "benign_urgent_rate": round(table["urgent"]["benign"] / n_ben, 4) if n_ben else None,
        "analyst_workload_share": round((table["urgent"]["attack"] + table["urgent"]["benign"]
                                         + table["review"]["attack"] + table["review"]["benign"]) / n, 4) if n else None,
        "seed": args.seed,
        "seconds_per_alert": round(per_alert, 3),
        "relogins": RELOGINS,
        "note": ("Cảnh báo mẫu được gắn lần lượt vào các tài sản hiện có nên vùng phụ thuộc cả mức quan trọng của tài sản. "
                 + ("Mẫu lấy tối thiểu mỗi lớp tấn công một số luồng cố định nên tỷ lệ tấn công trong mẫu không phản ánh tập kiểm thử; "
                    "chỉ đọc kết quả theo từng lớp, không đọc các tỷ lệ gộp. " if args.per_class else "")
                 + "Trọng số và ngưỡng chấm điểm không được chỉnh theo mẫu này."),
    }

    print("\n" + "=" * 64)
    print(f"Đã chấm điểm {n} luồng ({n_att} tấn công, {n_ben} lành tính), {summary['from_rf']} luồng dùng mô hình RF")
    print(f"{'Vùng':<14}{'Tấn công':>10}{'Lành tính':>12}")
    for z in ZONES:
        print(f"{z:<14}{table[z]['attack']:>10}{table[z]['benign']:>12}")
    print(f"\n{'Lớp':<34}{'n':>5}{'khẩn':>7}{'xem':>6}{'tự đóng':>9}  ghi chú")
    for name, c in summary["zone_by_class"].items():
        note = ""
        if c["label"] == "attack":
            note = f"bỏ sót 0, cận trên 95% ≈ {c['can_tren_95_neu_0_bo_sot']:.0%}" if c["auto_close"] == 0 else f"BỊ ĐỀ XUẤT ĐÓNG {c['bi_de_xuat_dong']:.0%}"
        print(f"{name:<34}{c['n']:>5}{c['urgent']:>7}{c['review']:>6}{c['auto_close']:>9}  {note}")
    print()
    print(f"Tấn công bị đề xuất tự đóng: {attack_missed}  |  recall (khẩn hoặc cần xem): {summary['attack_recall_urgent_or_review']}")
    print(f"Lành tính được đề xuất tự đóng: {summary['benign_auto_close_rate']}  |  lành tính ở vùng khẩn: {summary['benign_urgent_rate']}")
    print(f"Tỷ lệ cảnh báo analyst phải xem: {summary['analyst_workload_share']}")
    print("=" * 64)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"Thời gian trung bình mỗi cảnh báo: {per_alert:.2f}s" + (f" | đã đăng nhập lại {RELOGINS} lần vì token hết hạn" if RELOGINS else ""))
    if per_alert > 1.0:
        print("Chậm bất thường. Trên Windows, địa chỉ localhost có thể bị trễ vài giây mỗi kết nối: "
              "kiểm tra backend và AI service đang chạy ở 127.0.0.1.")
    print(f"Kết quả lưu tại {os.path.relpath(args.out, ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Đánh giá chấm điểm và chia vùng trên luồng mạng của tập kiểm thử")
    ap.add_argument("--attacks", type=int, default=100, help="số luồng tấn công")
    ap.add_argument("--benign", type=int, default=200, help="số luồng lành tính")
    ap.add_argument("--per-class", type=int, default=0, dest="per_class",
                    help="lấy tối thiểu số luồng này cho mỗi lớp tấn công (lớp ít hơn lấy hết); thay cho --attacks")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--data", default=DEFAULT_DATA, help="thư mục data/processed của mô hình")
    ap.add_argument("--out", default=OUT_FILE)
    main(ap.parse_args())
