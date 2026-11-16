import argparse
import glob
import json
import os
from collections import Counter

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "ids2018")
PROCESSED = os.path.join(HERE, "data", "ids", "processed")
MODELS = os.path.join(HERE, "models")

# Tên cột của mô hình (CIC-IDS2017) -> tên cột trong file CSE-CIC-IDS2018.
# Cột "Fwd Header Length.1" của 2017 là bản sao của "Fwd Header Length", nên cả hai lấy từ "Fwd Header Len".
# Cột "Protocol" của 2018 mô hình không dùng.
COLUMN_MAP = {
    "Destination Port": "Dst Port", "Flow Duration": "Flow Duration",
    "Total Fwd Packets": "Tot Fwd Pkts", "Total Backward Packets": "Tot Bwd Pkts",
    "Total Length of Fwd Packets": "TotLen Fwd Pkts", "Total Length of Bwd Packets": "TotLen Bwd Pkts",
    "Fwd Packet Length Max": "Fwd Pkt Len Max", "Fwd Packet Length Min": "Fwd Pkt Len Min",
    "Fwd Packet Length Mean": "Fwd Pkt Len Mean", "Fwd Packet Length Std": "Fwd Pkt Len Std",
    "Bwd Packet Length Max": "Bwd Pkt Len Max", "Bwd Packet Length Min": "Bwd Pkt Len Min",
    "Bwd Packet Length Mean": "Bwd Pkt Len Mean", "Bwd Packet Length Std": "Bwd Pkt Len Std",
    "Flow Bytes/s": "Flow Byts/s", "Flow Packets/s": "Flow Pkts/s",
    "Flow IAT Mean": "Flow IAT Mean", "Flow IAT Std": "Flow IAT Std",
    "Flow IAT Max": "Flow IAT Max", "Flow IAT Min": "Flow IAT Min",
    "Fwd IAT Total": "Fwd IAT Tot", "Fwd IAT Mean": "Fwd IAT Mean", "Fwd IAT Std": "Fwd IAT Std",
    "Fwd IAT Max": "Fwd IAT Max", "Fwd IAT Min": "Fwd IAT Min",
    "Bwd IAT Total": "Bwd IAT Tot", "Bwd IAT Mean": "Bwd IAT Mean", "Bwd IAT Std": "Bwd IAT Std",
    "Bwd IAT Max": "Bwd IAT Max", "Bwd IAT Min": "Bwd IAT Min",
    "Fwd PSH Flags": "Fwd PSH Flags", "Bwd PSH Flags": "Bwd PSH Flags",
    "Fwd URG Flags": "Fwd URG Flags", "Bwd URG Flags": "Bwd URG Flags",
    "Fwd Header Length": "Fwd Header Len", "Bwd Header Length": "Bwd Header Len",
    "Fwd Packets/s": "Fwd Pkts/s", "Bwd Packets/s": "Bwd Pkts/s",
    "Min Packet Length": "Pkt Len Min", "Max Packet Length": "Pkt Len Max",
    "Packet Length Mean": "Pkt Len Mean", "Packet Length Std": "Pkt Len Std",
    "Packet Length Variance": "Pkt Len Var",
    "FIN Flag Count": "FIN Flag Cnt", "SYN Flag Count": "SYN Flag Cnt", "RST Flag Count": "RST Flag Cnt",
    "PSH Flag Count": "PSH Flag Cnt", "ACK Flag Count": "ACK Flag Cnt", "URG Flag Count": "URG Flag Cnt",
    "CWE Flag Count": "CWE Flag Count", "ECE Flag Count": "ECE Flag Cnt",
    "Down/Up Ratio": "Down/Up Ratio", "Average Packet Size": "Pkt Size Avg",
    "Avg Fwd Segment Size": "Fwd Seg Size Avg", "Avg Bwd Segment Size": "Bwd Seg Size Avg",
    "Fwd Header Length.1": "Fwd Header Len",
    "Fwd Avg Bytes/Bulk": "Fwd Byts/b Avg", "Fwd Avg Packets/Bulk": "Fwd Pkts/b Avg",
    "Fwd Avg Bulk Rate": "Fwd Blk Rate Avg", "Bwd Avg Bytes/Bulk": "Bwd Byts/b Avg",
    "Bwd Avg Packets/Bulk": "Bwd Pkts/b Avg", "Bwd Avg Bulk Rate": "Bwd Blk Rate Avg",
    "Subflow Fwd Packets": "Subflow Fwd Pkts", "Subflow Fwd Bytes": "Subflow Fwd Byts",
    "Subflow Bwd Packets": "Subflow Bwd Pkts", "Subflow Bwd Bytes": "Subflow Bwd Byts",
    "Init_Win_bytes_forward": "Init Fwd Win Byts", "Init_Win_bytes_backward": "Init Bwd Win Byts",
    "act_data_pkt_fwd": "Fwd Act Data Pkts", "min_seg_size_forward": "Fwd Seg Size Min",
    "Active Mean": "Active Mean", "Active Std": "Active Std", "Active Max": "Active Max", "Active Min": "Active Min",
    "Idle Mean": "Idle Mean", "Idle Std": "Idle Std", "Idle Max": "Idle Max", "Idle Min": "Idle Min",
}

# Nhãn 2018 -> nhãn tương ứng của mô hình. None: không có lớp tương ứng, chỉ xem có bị báo là tấn công không.
# HOIC và LOIC-UDP là kiểu DDoS không có trong CIC-IDS2017 (chỉ có LOIC-HTTP) nên không gán vào lớp DDoS.
LABEL_MAP = {
    "Benign": "BENIGN", "Bot": "Bot", "Infilteration": "Infiltration",
    "Brute Force -Web": "Web Attack - Brute Force", "Brute Force -XSS": "Web Attack - XSS",
    "SQL Injection": "Web Attack - Sql Injection",
    "DoS attacks-Hulk": "DoS Hulk", "DoS attacks-GoldenEye": "DoS GoldenEye",
    "DoS attacks-SlowHTTPTest": "DoS Slowhttptest", "DoS attacks-Slowloris": "DoS slowloris",
    "FTP-BruteForce": "FTP-Patator", "SSH-Bruteforce": "SSH-Patator",
    "DDoS attacks-LOIC-HTTP": "DDoS", "DDOS attack-HOIC": None, "DDOS attack-LOIC-UDP": None,
}


def new_stats():
    return {"n": 0, "argmax_ok": 0, "a_any": 0, "a_ok": 0, "b_any": 0, "b_ok": 0}


def main():
    ap = argparse.ArgumentParser(description="Chấm mô hình CIC-IDS2017 trên CSE-CIC-IDS2018 (chỉ kiểm thử)")
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--chunk", type=int, default=300_000)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--out", default=os.path.join(HERE, "results", "ids2018_eval.json"))
    args = ap.parse_args()

    features = [str(c) for c in joblib.load(os.path.join(PROCESSED, "feature_cols.pkl"))]
    scaler = joblib.load(os.path.join(PROCESSED, "scaler.pkl"))
    rf = joblib.load(os.path.join(MODELS, "rf_multiclass.pkl"))
    labels = json.load(open(os.path.join(MODELS, "network_labels.json"), encoding="utf-8"))
    assert labels[0] == "BENIGN", "nhãn 0 phải là BENIGN"
    missing = [f for f in features if f not in COLUMN_MAP]
    if missing:
        raise SystemExit(f"Chưa có ánh xạ cho các cột của mô hình: {missing}")
    needed = [COLUMN_MAP[f] for f in features]
    classes = [int(c) for c in rf.classes_]
    assert classes == list(range(len(labels))), "mô hình thiếu lớp hoặc sai thứ tự"

    files = sorted(glob.glob(os.path.join(args.data, "*.csv")))
    if not files:
        raise SystemExit(f"Không thấy file CSV trong {args.data}")
    stats, fa_a, fa_b = {}, Counter(), Counter()
    skipped_header = non_finite = total = 0
    t = args.threshold

    for path in files:
        print(f"Đang chấm {os.path.basename(path)} ...", flush=True)
        for chunk in pd.read_csv(path, chunksize=args.chunk, low_memory=False):
            chunk.columns = chunk.columns.str.strip()
            lab = chunk["Label"].astype(str).str.strip()
            keep = (lab != "Label").to_numpy()          # một số file 2018 lặp lại dòng tiêu đề giữa file
            skipped_header += int((~keep).sum())
            chunk, lab = chunk[keep], lab[keep].to_numpy()
            if not len(chunk):
                continue
            miss = [c for c in needed if c not in chunk.columns]
            if miss:
                raise SystemExit(f"{os.path.basename(path)} thiếu cột {miss}")
            X = np.column_stack([pd.to_numeric(chunk[c], errors="coerce").to_numpy(dtype=np.float64) for c in needed])
            bad = ~np.isfinite(X)
            non_finite += int(bad.sum())
            X[bad] = 0.0                                 # giống dịch vụ AI: NaN/Infinity quy về 0
            P = rf.predict_proba(scaler.transform(X))
            arg, conf = P.argmax(1), P.max(1)
            Pa = P.copy()
            Pa[:, 0] = 0
            pred_b = Pa.argmax(1)
            alert_a = (arg != 0) & (conf >= t)
            alert_b = (1 - P[:, 0]) >= t
            total += len(lab)
            for L in np.unique(lab):
                m = lab == L
                s = stats.setdefault(L, new_stats())
                s["n"] += int(m.sum())
                s["a_any"] += int((alert_a & m).sum())
                s["b_any"] += int((alert_b & m).sum())
                exp = LABEL_MAP.get(L)
                if exp is not None and exp in labels:
                    e = labels.index(exp)
                    s["argmax_ok"] += int(((arg == e) & m).sum())
                    s["a_ok"] += int((alert_a & (arg == e) & m).sum())
                    s["b_ok"] += int((alert_b & (pred_b == e) & m).sum())
                if exp == "BENIGN":
                    fa_a.update({labels[i]: int(c) for i, c in enumerate(np.bincount(arg[m & alert_a], minlength=len(labels))) if c})
                    fa_b.update({labels[i]: int(c) for i, c in enumerate(np.bincount(pred_b[m & alert_b], minlength=len(labels))) if c})

    print(f"\nTổng {total:,} luồng | dòng tiêu đề lặp bị bỏ: {skipped_header:,} | ô NaN/Infinity quy về 0: {non_finite:,}")
    print(f"Ngưỡng {t}. A = nhãn dự đoán khác BENIGN và confidence >= ngưỡng; B = 1 - P(BENIGN) >= ngưỡng")
    print("'Báo động' = bị cảnh báo là một lớp tấn công bất kỳ; 'Đúng loại' = cảnh báo đúng lớp tương ứng của mô hình\n")
    print(f"{'Lớp 2018':<26}{'Tương ứng':<28}{'n':>10}{'Argmax đúng':>13}{'A báo':>9}{'A đúng':>9}{'B báo':>9}{'B đúng':>9}")
    report = {}
    for L, s in sorted(stats.items(), key=lambda kv: (kv[0] == "Benign", -kv[1]["n"])):
        exp = LABEL_MAP.get(L, "?")
        if exp == "BENIGN":
            continue
        n = s["n"]
        pct = lambda v: f"{100 * v / n:.1f}%"
        has = exp is not None and exp != "?"
        print(f"{L:<26}{str(exp or '(không có)'):<28}{n:>10,}{(pct(s['argmax_ok']) if has else '-'):>13}"
              f"{pct(s['a_any']):>9}{(pct(s['a_ok']) if has else '-'):>9}{pct(s['b_any']):>9}{(pct(s['b_ok']) if has else '-'):>9}")
        report[L] = {**s, "expected": exp}
    b = stats.get("Benign")
    if b:
        print(f"\nBenign: {b['n']:,} luồng")
        print(f"  Cảnh báo giả trên 1000 luồng: A = {1000 * b['a_any'] / b['n']:.2f}, B = {1000 * b['b_any'] / b['n']:.2f}")
        print(f"  Nhãn của cảnh báo giả (A): {fa_a.most_common(6)}")
        print(f"  Nhãn của cảnh báo giả (B): {fa_b.most_common(6)}")
        report["Benign"] = {**b, "false_alert_labels_A": dict(fa_a), "false_alert_labels_B": dict(fa_b)}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"threshold": t, "total": total, "skipped_header_rows": skipped_header,
                   "non_finite_cells": non_finite, "per_label": report}, f, ensure_ascii=False, indent=1)
    print(f"\nĐã ghi {args.out}")


if __name__ == "__main__":
    main()