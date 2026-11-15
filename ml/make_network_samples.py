import glob
import json
import os

import joblib
import numpy as np
import pandas as pd

THRESHOLD = 0.80          # ngưỡng sinh cảnh báo mặc định (threshold_network); đổi nếu bạn đã chỉnh ở trang Cấu hình
CANDIDATES = 300          # số luồng thử mỗi loại nhãn, mỗi file CSV gốc
MAX_ALERT_PER_LABEL = 30  # tối đa số luồng "chắc chắn ra cảnh báo" cho mỗi nhãn
N_BENIGN, N_BELOW = 40, 30

# ---- nạp mô hình y như serve.py ----
scaler = joblib.load("data/ids/processed/scaler.pkl")
features = [str(c) for c in joblib.load("data/ids/processed/feature_cols.pkl")]
if os.path.isfile("models/rf_multiclass.pkl") and os.path.isfile("models/network_labels.json"):
    model = joblib.load("models/rf_multiclass.pkl")
    labels = json.load(open("models/network_labels.json", encoding="utf-8"))
    classes = [labels[int(c)] for c in model.classes_]
else:
    model = joblib.load("models/rf_binary.pkl")
    classes = ["BENIGN", "ATTACK"]
print("Mô hình:", "nhiều lớp" if len(classes) > 2 else "nhị phân", "-", len(classes), "nhãn")

# ---- lấy ứng viên từ dữ liệu gốc ----
frames = []
for f in sorted(glob.glob("data/ids/raw/*.csv")):
    d = pd.read_csv(f, low_memory=False)
    d.columns = d.columns.str.strip()              # giống preprocess.py (cột trùng tên thành ".1")
    for _, g in d.groupby("Label"):
        frames.append(g.sample(min(len(g), CANDIDATES), random_state=1))
cand = pd.concat(frames, ignore_index=True)
missing = [c for c in features if c not in cand.columns]
assert not missing, f"Thiếu cột so với feature_cols.pkl: {missing[:5]}"
cand[features] = cand[features].replace([np.inf, -np.inf], np.nan).fillna(0)   # giống cách hệ thống xử lý Infinity/NaN

# ---- chạy mô hình, ghi nhãn và confidence dự đoán ----
proba = model.predict_proba(scaler.transform(cand[features].to_numpy(dtype=float)))
best = proba.argmax(axis=1)
cand["pred"] = [classes[b] for b in best]
cand["conf"] = proba.max(axis=1).round(4)
dangerous = cand["pred"] != "BENIGN"                # mặc định mọi nhãn khác BENIGN là lớp nguy hiểm

alerts = pd.concat([g.sort_values("conf", ascending=False).head(MAX_ALERT_PER_LABEL)
                    for _, g in cand[dangerous & (cand["conf"] >= THRESHOLD)].groupby("pred")])
benign = cand[(cand["pred"] == "BENIGN") & (cand["Label"] == "BENIGN")].sample(frac=1, random_state=1).head(N_BENIGN)
below = cand[dangerous & (cand["conf"] < THRESHOLD)].sample(frac=1, random_state=1).head(N_BELOW)

def save(df, name, as_json=False):
    out = df[features + ["Label"]].sample(frac=1, random_state=2).reset_index(drop=True)
    if as_json:
        out.to_json(name, orient="records", force_ascii=False, indent=1)
    else:
        out.to_csv(name, index=False)

# 1) nhiều cảnh báo: để thử phân trang, lọc, xác minh hàng loạt, chuyển/gỡ
save(pd.concat([alerts, benign]), "mau_nhieu_canh_bao.csv")
# 2) nhỏ: mỗi nhãn một luồng cảnh báo (tối đa 6) cộng 6 luồng bình thường, để thử nhanh
small = pd.concat([alerts.groupby("pred").head(1).head(6), benign.head(6)])
save(small, "mau_nho.json", as_json=True)
# 3) dưới ngưỡng: được phân loại nguy hiểm nhưng confidence < ngưỡng, nên không ra cảnh báo
save(below, "mau_duoi_nguong.csv")

print(f"\nKỳ vọng khi tải lên (ngưỡng {THRESHOLD}, mô hình hiện tại):")
print(f"  mau_nhieu_canh_bao.csv : {len(alerts) + len(benign)} dòng -> {len(alerts)} cảnh báo")
print(f"  mau_nho.json           : {len(small)} dòng -> {int(small['pred'].ne('BENIGN').sum())} cảnh báo")
print(f"  mau_duoi_nguong.csv    : {len(below)} dòng -> 0 cảnh báo (hạ ngưỡng xuống {'<= ' + str(below['conf'].min()) if len(below) else 'n/a'} thì cả {len(below)} dòng đều ra cảnh báo)")
print("\nCảnh báo mong đợi theo nhãn trong mau_nhieu_canh_bao.csv:")
print(alerts["pred"].value_counts().to_string())