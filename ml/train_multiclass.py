import argparse
import json
import os
import time
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

ap = argparse.ArgumentParser()
ap.add_argument("--trees", type=int, default=100)
ap.add_argument("--max-depth", type=int, default=20)
ap.add_argument("--sample", type=float, default=1.0, help="tỉ lệ dữ liệu train để chạy thử nhanh, ví dụ 0.1")
args = ap.parse_args()

DATA_DIR = "data/ids/processed"
MODEL_DIR = "models"
RESULT_DIR = "results"
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

X_train = np.load(os.path.join(DATA_DIR, "X_train.npy"))
X_test = np.load(os.path.join(DATA_DIR, "X_test.npy"))
y_train = np.load(os.path.join(DATA_DIR, "y_train_multi.npy"))
y_test = np.load(os.path.join(DATA_DIR, "y_test_multi.npy"))
le = joblib.load(os.path.join(DATA_DIR, "label_encoder.pkl"))


def clean(name):
    # CSV gốc của CIC-IDS2017 có ký tự lạ trong "Web Attack – ..."; chuẩn hóa về dấu gạch ngang thường
    name = str(name).replace("\ufffd", "-").replace("\u2013", "-")
    return " ".join(name.replace(" - ", " - ").split())


# labels[i] là tên nhãn của lớp có mã i; backend và dịch vụ AI dùng chung danh sách này
if args.sample < 1.0:
    rng = np.random.default_rng(42)
    keep = rng.random(len(y_train)) < args.sample
    X_train, y_train = X_train[keep], y_train[keep]
    print(f"Chạy thử với {keep.sum()} dòng ({args.sample:.0%}); mô hình này chỉ để kiểm tra, không dùng cho luận văn")

labels = [clean(c) for c in le.classes_]
print(f"{len(labels)} lớp: {labels}")
print(f"Train: {X_train.shape} | Test: {X_test.shape}")

t0 = time.time()
rf = RandomForestClassifier(n_estimators=args.trees, max_depth=args.max_depth, class_weight="balanced_subsample",
                            random_state=42, n_jobs=-1, verbose=1)
rf.fit(X_train, y_train)
print(f"Huấn luyện xong sau {time.time() - t0:.0f}s")

pred = rf.predict(X_test)
present = sorted(set(y_test) | set(pred))
report = classification_report(y_test, pred, labels=present, target_names=[labels[i] for i in present],
                               output_dict=True, zero_division=0)
print(classification_report(y_test, pred, labels=present, target_names=[labels[i] for i in present], zero_division=0))

joblib.dump(rf, os.path.join(MODEL_DIR, "rf_multiclass.pkl"), compress=3)
with open(os.path.join(MODEL_DIR, "network_labels.json"), "w", encoding="utf-8") as f:
    json.dump(labels, f, ensure_ascii=False, indent=1)
with open(os.path.join(RESULT_DIR, "multiclass_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("Đã lưu models/rf_multiclass.pkl, models/network_labels.json, results/multiclass_report.json")
print("Lưu ý: chia 80/20 ngẫu nhiên; các lớp rất ít mẫu (Heartbleed, Infiltration, SQL Injection) cho số liệu kém ổn định.")
